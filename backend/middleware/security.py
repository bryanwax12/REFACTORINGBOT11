"""
Security Middleware
Centralized security system for the application
"""
import logging
import time
from typing import Optional, Dict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import re
import os

logger = logging.getLogger(__name__)


# ============================================================
# RATE LIMITING
# ============================================================

class RateLimiter:
    """
    Rate limiter to prevent brute-force and DDoS attacks
    """
    
    def __init__(self):
        # Store: {ip: {endpoint: [(timestamp, count)]}}
        self.requests: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self.cleanup_interval = 300  # Clean every 5 minutes
        self.last_cleanup = time.time()
    
    def is_rate_limited(
        self,
        client_ip: str,
        endpoint: str,
        limit: int = 100,
        window: int = 60
    ) -> tuple[bool, Optional[int]]:
        """
        Check if request should be rate limited
        
        Args:
            client_ip: Client IP address
            endpoint: API endpoint
            limit: Maximum requests allowed
            window: Time window in seconds
        
        Returns:
            Tuple of (is_limited, retry_after_seconds)
        """
        now = time.time()
        
        # Cleanup old entries periodically
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup()
            self.last_cleanup = now
        
        # Get requests for this IP and endpoint
        requests = self.requests[client_ip][endpoint]
        
        # Remove old requests outside window
        requests[:] = [req for req in requests if now - req < window]
        
        # Check if limit exceeded
        if len(requests) >= limit:
            # Calculate retry after
            oldest_request = min(requests)
            retry_after = int(window - (now - oldest_request))
            return True, retry_after
        
        # Add current request
        requests.append(now)
        return False, None
    
    def _cleanup(self):
        """Clean up old entries"""
        now = time.time()
        for ip in list(self.requests.keys()):
            for endpoint in list(self.requests[ip].keys()):
                self.requests[ip][endpoint] = [
                    req for req in self.requests[ip][endpoint]
                    if now - req < 3600  # Keep last hour
                ]
                if not self.requests[ip][endpoint]:
                    del self.requests[ip][endpoint]
            if not self.requests[ip]:
                del self.requests[ip]


# Global rate limiter instance
rate_limiter = RateLimiter()


# ============================================================
# AUTHENTICATION
# ============================================================

class SecurityManager:
    """
    Centralized security manager
    """
    
    @staticmethod
    def verify_admin_api_key(api_key: Optional[str]) -> bool:
        """
        Verify admin API key
        
        Args:
            api_key: API key from header
        
        Returns:
            True if valid, raises HTTPException otherwise
        """
        admin_key = os.environ.get('ADMIN_API_KEY')
        
        # CRITICAL: If no admin key set, DENY access
        if not admin_key:
            logger.critical("🚨 ADMIN_API_KEY not set - admin endpoints are DISABLED for security!")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin API is not configured. Set ADMIN_API_KEY environment variable."
            )
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "ApiKey"}
            )
        
        if api_key != admin_key:
            # Log failed attempt
            logger.warning(f"🚨 Failed admin authentication attempt with key: {api_key[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key"
            )
        
        return True
    
    @staticmethod
    def sanitize_input(value: str, max_length: int = 500) -> str:
        """
        Sanitize user input to prevent injection attacks
        
        Args:
            value: Input string
            max_length: Maximum allowed length
        
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        
        # Truncate
        value = value[:max_length]
        
        # Remove control characters
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
        
        # Escape HTML
        value = value.replace('<', '&lt;').replace('>', '&gt;')
        
        return value.strip()
    
    @staticmethod
    def validate_mongodb_query(query: dict) -> dict:
        """
        Validate MongoDB query to prevent NoSQL injection
        
        Args:
            query: MongoDB query dict
        
        Returns:
            Validated query
        
        Raises:
            ValueError if query contains dangerous operators
        """
        dangerous_operators = ['$where', '$function', '$accumulator']
        
        def check_dict(d: dict):
            for key, value in d.items():
                # Check for dangerous operators
                if key in dangerous_operators:
                    raise ValueError(f"Dangerous operator '{key}' not allowed in queries")
                
                # Recursively check nested dicts
                if isinstance(value, dict):
                    check_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            check_dict(item)
        
        check_dict(query)
        return query
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """
        Get real client IP address (handles proxies)
        
        Args:
            request: FastAPI request
        
        Returns:
            Client IP address
        """
        # Check X-Forwarded-For header (from proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP (client IP)
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        return request.client.host if request.client else "unknown"


# Global security manager
security_manager = SecurityManager()


# ============================================================
# SECURITY MIDDLEWARE
# ============================================================

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for all requests
    """
    
    # Rate limits for different endpoint types
    RATE_LIMITS = {
        "/api/admin": (20, 60),      # 20 requests per minute
        "/api/monitoring": (60, 60),  # 60 requests per minute
        "/api/alerts": (30, 60),      # 30 requests per minute
        "/api/telegram": (100, 60),   # 100 requests per minute
        "default": (120, 60)          # 120 requests per minute
    }
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request through security checks
        """
        start_time = time.time()
        
        # Get client IP
        client_ip = security_manager.get_client_ip(request)
        
        # Skip security for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            response = await call_next(request)
            return response
        
        # Rate limiting
        endpoint_base = self._get_endpoint_base(request.url.path)
        limit, window = self.RATE_LIMITS.get(endpoint_base, self.RATE_LIMITS["default"])
        
        is_limited, retry_after = rate_limiter.is_rate_limited(
            client_ip,
            endpoint_base,
            limit,
            window
        )
        
        if is_limited:
            logger.warning(f"🚨 Rate limit exceeded for {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self'"
            
            # Add timing header (for monitoring)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
        
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            raise
    
    @staticmethod
    def _get_endpoint_base(path: str) -> str:
        """Get base endpoint for rate limiting"""
        for prefix in SecurityMiddleware.RATE_LIMITS.keys():
            if path.startswith(prefix):
                return prefix
        return "default"


# ============================================================
# AUDIT LOGGING
# ============================================================

class AuditLogger:
    """
    Audit logging for critical operations
    """
    
    @staticmethod
    async def log_admin_action(
        action: str,
        user: Optional[str],
        details: dict,
        ip_address: str,
        success: bool = True
    ):
        """
        Log admin actions for audit trail
        
        Args:
            action: Action performed
            user: User/admin identifier
            details: Additional details
            ip_address: Client IP
            success: Whether action succeeded
        """
        from server import db
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "user": user,
            "details": details,
            "ip_address": ip_address,
            "success": success,
            "type": "admin_action"
        }
        
        try:
            await db.audit_logs.insert_one(log_entry)
            logger.info(f"📝 Audit: {action} by {user} - {'Success' if success else 'Failed'}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    @staticmethod
    async def log_security_event(
        event_type: str,
        severity: str,
        details: dict,
        ip_address: str
    ):
        """
        Log security events
        
        Args:
            event_type: Type of security event
            severity: Severity (low, medium, high, critical)
            details: Event details
            ip_address: Client IP
        """
        from server import db
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "details": details,
            "ip_address": ip_address,
            "type": "security_event"
        }
        
        try:
            await db.security_logs.insert_one(log_entry)
            logger.warning(f"🔒 Security Event [{severity}]: {event_type} from {ip_address}")
        except Exception as e:
            logger.error(f"Failed to write security log: {e}")


# Global audit logger
audit_logger = AuditLogger()


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'SecurityMiddleware',
    'SecurityManager',
    'RateLimiter',
    'AuditLogger',
    'security_manager',
    'rate_limiter',
    'audit_logger'
]
