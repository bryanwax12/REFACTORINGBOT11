"""
Authentication Middleware
Middleware для проверки авторизации
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import os

logger = logging.getLogger(__name__)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки админского доступа
    """
    
    def __init__(self, app, admin_paths: list = None):
        """
        Инициализация middleware
        
        Args:
            app: FastAPI application
            admin_paths: Список путей, требующих админского доступа
        """
        super().__init__(app)
        self.admin_paths = admin_paths or [
            "/api/admin",
            "/api/broadcast",
            "/api/users/",
            "/api/maintenance"
        ]
        self.admin_key = os.environ.get("ADMIN_KEY", "")
    
    async def dispatch(self, request: Request, call_next):
        """
        Обработка запроса
        
        Args:
            request: HTTP запрос
            call_next: Следующий handler
            
        Returns:
            Response
        """
        path = request.url.path
        
        # Проверяем нужна ли авторизация
        requires_auth = any(path.startswith(admin_path) for admin_path in self.admin_paths)
        
        if requires_auth:
            # Проверяем admin key
            auth_header = request.headers.get("X-Admin-Key") or request.headers.get("Authorization")
            
            if not auth_header:
                logger.warning(f"🚫 Unauthorized access attempt to {path}")
                raise HTTPException(
                    status_code=401,
                    detail="Admin authorization required"
                )
            
            # Проверяем ключ
            provided_key = auth_header.replace("Bearer ", "").strip()
            
            if not self.admin_key or provided_key != self.admin_key:
                logger.warning(f"🚫 Invalid admin key for {path}")
                raise HTTPException(
                    status_code=403,
                    detail="Invalid admin credentials"
                )
            
            logger.info(f"✅ Admin access granted to {path}")
        
        response = await call_next(request)
        return response


async def verify_admin_key(request: Request):
    """
    Dependency для проверки админского ключа
    Использовать в эндпоинтах: dependencies=[Depends(verify_admin_key)]
    
    Args:
        request: HTTP запрос
        
    Raises:
        HTTPException: Если ключ неверный
    """
    admin_key = os.environ.get("ADMIN_KEY", "")
    
    auth_header = request.headers.get("X-Admin-Key") or request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Admin authorization required. Provide X-Admin-Key header"
        )
    
    provided_key = auth_header.replace("Bearer ", "").strip()
    
    if not admin_key or provided_key != admin_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin credentials"
        )
    
    return True
