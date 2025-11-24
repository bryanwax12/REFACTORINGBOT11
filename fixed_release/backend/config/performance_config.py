"""
Performance Configuration for Production Bot
Optimized settings for fast response times and stability
"""
import httpx


class BotPerformanceConfig:
    """
    Optimized settings for fast, stable bot performance
    """
    
    # Telegram API Settings - Optimized for speed without getting banned
    TELEGRAM_TIMEOUTS = {
        'read_timeout': 15.0,      # Fast read timeout
        'write_timeout': 20.0,     # Write timeout for file uploads
        'connect_timeout': 10.0,   # Quick connection timeout
        'pool_timeout': 15.0,      # Connection pool timeout
    }
    
    # HTTP Client Settings - Aggressive but safe
    HTTP_CLIENT_CONFIG = {
        'timeout': 15.0,           # Fast timeout for external APIs
        'limits': httpx.Limits(
            max_keepalive_connections=20,  # Keep connections alive
            max_connections=100,           # Allow many concurrent connections
        ),
        'retries': 2,              # Quick retries
    }
    
    # Database Connection Settings
    MONGODB_CONFIG = {
        'serverSelectionTimeoutMS': 5000,  # 5 sec server selection
        'connectTimeoutMS': 10000,          # 10 sec connection timeout
        'socketTimeoutMS': 15000,           # 15 sec socket timeout
        'maxPoolSize': 50,                  # Connection pool size
        'minPoolSize': 5,                   # Minimum connections
        'maxIdleTimeMS': 30000,             # 30 sec idle time
    }
    
    # External API Timeouts - Fast but reliable
    EXTERNAL_API_TIMEOUTS = {
        'shipstation': 12.0,       # ShipStation API timeout
        'oxapay': 10.0,           # Oxapay API timeout
        'webhook_delivery': 8.0,   # Webhook delivery timeout
    }
    
    # Rate Limiting - Prevent Telegram bans
    RATE_LIMITS = {
        'messages_per_second': 25,     # Telegram limit: 30/sec
        'messages_per_minute': 1500,   # Safe margin
        'bulk_messages_per_second': 1, # For broadcast operations
    }
    
    # Async Settings
    ASYNCIO_CONFIG = {
        'max_workers': 10,             # Thread pool size
        'semaphore_limit': 50,         # Concurrent operations limit
    }
    
    @classmethod
    def get_optimized_bot_settings(cls) -> dict:
        """Get optimized settings for Bot creation"""
        return {
            'read_timeout': cls.TELEGRAM_TIMEOUTS['read_timeout'],
            'write_timeout': cls.TELEGRAM_TIMEOUTS['write_timeout'],
            'connect_timeout': cls.TELEGRAM_TIMEOUTS['connect_timeout'],
            'pool_timeout': cls.TELEGRAM_TIMEOUTS['pool_timeout'],
        }
    
    @classmethod
    def get_optimized_application_settings(cls) -> dict:
        """Get optimized settings for Application creation"""
        return {
            'read_timeout': cls.TELEGRAM_TIMEOUTS['read_timeout'],
            'write_timeout': cls.TELEGRAM_TIMEOUTS['write_timeout'],
            'connect_timeout': cls.TELEGRAM_TIMEOUTS['connect_timeout'],
            'pool_timeout': cls.TELEGRAM_TIMEOUTS['pool_timeout'],
            'concurrent_updates': True,      # CHANGED: Use True (default: 1 update per user at a time)
                                             # This prevents race conditions when user types fast!
                                             # Multiple users can still be handled concurrently
        }
    
    @classmethod
    def get_http_client_config(cls) -> dict:
        """Get HTTP client configuration"""
        return cls.HTTP_CLIENT_CONFIG
    
    @classmethod
    def get_mongodb_config(cls) -> dict:
        """Get MongoDB configuration"""
        return cls.MONGODB_CONFIG


# Performance monitoring helper
class PerformanceMonitor:
    """Monitor bot performance and detect slow operations"""
    
    def __init__(self):
        self.slow_operations = []
        self.operation_times = {}
    
    async def monitor_operation(self, operation_name: str, coro):
        """Monitor async operation performance"""
        import time
        start_time = time.time()
        
        try:
            result = await coro
            execution_time = time.time() - start_time
            
            # Log slow operations (>2 seconds)
            if execution_time > 2.0:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Slow operation: {operation_name} took {execution_time:.2f}s")
                self.slow_operations.append({
                    'operation': operation_name,
                    'time': execution_time,
                    'timestamp': time.time()
                })
            
            self.operation_times[operation_name] = execution_time
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Operation {operation_name} failed after {execution_time:.2f}s: {e}")
            raise


# Global performance monitor instance
performance_monitor = PerformanceMonitor()
