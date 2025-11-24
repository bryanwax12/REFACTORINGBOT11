"""
Performance monitoring and profiling utilities
Логирование времени выполнения DB и API запросов
"""
import time
import logging
from functools import wraps
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Статистика производительности
PERFORMANCE_STATS = {
    'db_queries': [],
    'api_calls': [],
    'slow_queries': []
}

SLOW_QUERY_THRESHOLD_MS = 100  # Логировать запросы медленнее 100ms


def profile_db_query(operation_name: str, order_id: Optional[str] = None):
    """
    Декоратор для профилирования DB запросов
    
    Usage:
        @profile_db_query("find_user")
        async def get_user(user_id):
            return await db.users.find_one({"user_id": user_id})
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            
            # Try to extract order_id from kwargs if not provided
            extracted_order_id = order_id or kwargs.get('order_id')
            
            try:
                result = await func(*args, **kwargs)
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                # Логирование
                if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
                    order_info = f" [order: {extracted_order_id[:12]}]" if extracted_order_id else ""
                    logger.warning(f"🐌 SLOW DB QUERY: {operation_name}{order_info} took {elapsed_ms:.2f}ms")
                    PERFORMANCE_STATS['slow_queries'].append({
                        'operation': operation_name,
                        'order_id': extracted_order_id,
                        'duration_ms': elapsed_ms,
                        'timestamp': datetime.now().isoformat(),
                        'type': 'db'
                    })
                else:
                    logger.debug(f"⚡ DB: {operation_name} took {elapsed_ms:.2f}ms")
                
                # Статистика
                PERFORMANCE_STATS['db_queries'].append({
                    'operation': operation_name,
                    'duration_ms': elapsed_ms
                })
                
                # Ограничить размер статистики (последние 100)
                if len(PERFORMANCE_STATS['db_queries']) > 100:
                    PERFORMANCE_STATS['db_queries'].pop(0)
                
                return result
                
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"❌ DB ERROR in {operation_name} after {elapsed_ms:.2f}ms: {e}")
                raise
        
        return wrapper
    return decorator


def profile_api_call(service_name: str):
    """
    Декоратор для профилирования внешних API вызовов
    
    Usage:
        @profile_api_call("ShipStation")
        async def fetch_rates():
            return await make_api_call()
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            
            try:
                result = await func(*args, **kwargs)
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                # Логирование
                if elapsed_ms > 1000:  # >1 секунда
                    logger.warning(f"🐌 SLOW API: {service_name} took {elapsed_ms:.2f}ms")
                    PERFORMANCE_STATS['slow_queries'].append({
                        'operation': service_name,
                        'duration_ms': elapsed_ms,
                        'timestamp': datetime.now().isoformat(),
                        'type': 'api'
                    })
                else:
                    logger.info(f"⚡ API: {service_name} took {elapsed_ms:.2f}ms")
                
                # Статистика
                PERFORMANCE_STATS['api_calls'].append({
                    'service': service_name,
                    'duration_ms': elapsed_ms
                })
                
                # Ограничить размер
                if len(PERFORMANCE_STATS['api_calls']) > 100:
                    PERFORMANCE_STATS['api_calls'].pop(0)
                
                return result
                
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"❌ API ERROR in {service_name} after {elapsed_ms:.2f}ms: {e}")
                raise
        
        return wrapper
    return decorator


class QueryTimer:
    """
    Context manager для ручного профилирования
    
    Usage:
        async with QueryTimer("complex_operation") as timer:
            await do_something()
            timer.checkpoint("step1")
            await do_more()
            timer.checkpoint("step2")
    """
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.checkpoints = []
    
    async def __aenter__(self):
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        
        if exc_type:
            logger.error(f"❌ {self.operation_name} FAILED after {elapsed_ms:.2f}ms")
        elif elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
            logger.warning(f"🐌 {self.operation_name} took {elapsed_ms:.2f}ms")
            if self.checkpoints:
                logger.warning(f"   Checkpoints: {self.checkpoints}")
        else:
            logger.debug(f"⚡ {self.operation_name} took {elapsed_ms:.2f}ms")
    
    def checkpoint(self, name: str):
        """Добавить промежуточную точку измерения"""
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        self.checkpoints.append(f"{name}={elapsed_ms:.2f}ms")


def get_performance_stats() -> Dict[str, Any]:
    """
    Получить статистику производительности
    
    Returns:
        dict: Статистика с avg/min/max временем запросов
    """
    stats = {
        'db_queries': {
            'count': len(PERFORMANCE_STATS['db_queries']),
            'avg_ms': 0,
            'min_ms': 0,
            'max_ms': 0
        },
        'api_calls': {
            'count': len(PERFORMANCE_STATS['api_calls']),
            'avg_ms': 0,
            'min_ms': 0,
            'max_ms': 0
        },
        'slow_queries_count': len(PERFORMANCE_STATS['slow_queries']),
        'recent_slow_queries': PERFORMANCE_STATS['slow_queries'][-10:]  # Последние 10
    }
    
    # DB статистика
    if PERFORMANCE_STATS['db_queries']:
        durations = [q['duration_ms'] for q in PERFORMANCE_STATS['db_queries']]
        stats['db_queries']['avg_ms'] = sum(durations) / len(durations)
        stats['db_queries']['min_ms'] = min(durations)
        stats['db_queries']['max_ms'] = max(durations)
    
    # API статистика
    if PERFORMANCE_STATS['api_calls']:
        durations = [c['duration_ms'] for c in PERFORMANCE_STATS['api_calls']]
        stats['api_calls']['avg_ms'] = sum(durations) / len(durations)
        stats['api_calls']['min_ms'] = min(durations)
        stats['api_calls']['max_ms'] = max(durations)
    
    return stats


def clear_performance_stats():
    """Очистить статистику (для тестов)"""
    PERFORMANCE_STATS['db_queries'].clear()
    PERFORMANCE_STATS['api_calls'].clear()
    PERFORMANCE_STATS['slow_queries'].clear()
    logger.info("🧹 Performance stats cleared")
