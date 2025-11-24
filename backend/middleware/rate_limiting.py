"""
Rate Limiting Middleware
Middleware для ограничения частоты запросов
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
from collections import defaultdict
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для ограничения частоты запросов (rate limiting)
    Простая реализация с хранением в памяти
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000
    ):
        """
        Инициализация middleware
        
        Args:
            app: FastAPI application
            requests_per_minute: Лимит запросов в минуту
            requests_per_hour: Лимит запросов в час
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        
        # Хранилище: {ip: [(timestamp, count), ...]}
        self.request_history: Dict[str, list] = defaultdict(list)
        
        # Время последней очистки
        self.last_cleanup = time.time()
    
    def _cleanup_old_requests(self):
        """Очистка старых записей (каждые 10 минут)"""
        current_time = time.time()
        
        if current_time - self.last_cleanup > 600:  # 10 minutes
            hour_ago = current_time - 3600
            
            for ip in list(self.request_history.keys()):
                # Удаляем записи старше часа
                self.request_history[ip] = [
                    (ts, count) for ts, count in self.request_history[ip]
                    if ts > hour_ago
                ]
                
                # Удаляем IP без записей
                if not self.request_history[ip]:
                    del self.request_history[ip]
            
            self.last_cleanup = current_time
            logger.debug(f"Cleaned up rate limit history. Active IPs: {len(self.request_history)}")
    
    def _check_rate_limit(self, ip: str) -> Tuple[bool, str]:
        """
        Проверить лимиты для IP
        
        Args:
            ip: IP адрес клиента
            
        Returns:
            (allowed, error_message)
        """
        current_time = time.time()
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        # Получаем историю запросов
        history = self.request_history[ip]
        
        # Считаем запросы за минуту
        requests_last_minute = sum(
            count for ts, count in history
            if ts > minute_ago
        )
        
        # Считаем запросы за час
        requests_last_hour = sum(
            count for ts, count in history
            if ts > hour_ago
        )
        
        # Проверяем лимиты
        if requests_last_minute >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {requests_last_minute}/{self.requests_per_minute} requests per minute"
        
        if requests_last_hour >= self.requests_per_hour:
            return False, f"Rate limit exceeded: {requests_last_hour}/{self.requests_per_hour} requests per hour"
        
        return True, ""
    
    def _record_request(self, ip: str):
        """
        Записать запрос
        
        Args:
            ip: IP адрес клиента
        """
        current_time = time.time()
        self.request_history[ip].append((current_time, 1))
    
    async def dispatch(self, request: Request, call_next):
        """
        Обработка запроса
        
        Args:
            request: HTTP запрос
            call_next: Следующий handler
            
        Returns:
            Response
        """
        # Периодическая очистка
        self._cleanup_old_requests()
        
        # Получаем IP клиента
        client_host = request.client.host if request.client else "unknown"
        
        # Пропускаем локальные запросы
        if client_host in ["127.0.0.1", "localhost", "unknown"]:
            return await call_next(request)
        
        # Проверяем лимиты
        allowed, error_message = self._check_rate_limit(client_host)
        
        if not allowed:
            logger.warning(f"⚠️ Rate limit exceeded for {client_host}: {request.url.path}")
            raise HTTPException(
                status_code=429,
                detail=error_message,
                headers={"Retry-After": "60"}
            )
        
        # Записываем запрос
        self._record_request(client_host)
        
        # Обрабатываем запрос
        response = await call_next(request)
        
        return response
