"""
Request Logging Middleware
Middleware для логирования запросов
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования всех HTTP запросов
    """
    
    def __init__(self, app, log_body: bool = False):
        """
        Инициализация middleware
        
        Args:
            app: FastAPI application
            log_body: Логировать ли тело запроса
        """
        super().__init__(app)
        self.log_body = log_body
    
    async def dispatch(self, request: Request, call_next):
        """
        Обработка запроса
        
        Args:
            request: HTTP запрос
            call_next: Следующий handler
            
        Returns:
            Response
        """
        # Начало обработки
        start_time = time.time()
        
        # Получаем информацию о запросе
        method = request.method
        url = str(request.url)
        client_host = request.client.host if request.client else "unknown"
        
        # Логируем запрос
        logger.info(f"→ {method} {url} from {client_host}")
        
        # Логируем тело если нужно
        if self.log_body and method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    logger.debug(f"Request body: {body.decode()[:500]}")  # First 500 chars
            except Exception as e:
                logger.error(f"Error reading request body: {e}")
        
        # Обрабатываем запрос
        try:
            response = await call_next(request)
            
            # Вычисляем время обработки
            process_time = time.time() - start_time
            
            # Логируем ответ
            status_code = response.status_code
            
            if status_code < 400:
                logger.info(f"← {method} {url} → {status_code} ({process_time:.3f}s)")
            elif status_code < 500:
                logger.warning(f"← {method} {url} → {status_code} ({process_time:.3f}s)")
            else:
                logger.error(f"← {method} {url} → {status_code} ({process_time:.3f}s)")
            
            # Добавляем время обработки в заголовки
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"✗ {method} {url} failed after {process_time:.3f}s: {str(e)}")
            raise
