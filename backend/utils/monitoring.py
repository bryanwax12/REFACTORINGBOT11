"""
Модуль мониторинга
Интеграция с Sentry и кастомные метрики для отслеживания здоровья бота
"""
import os
import logging
import time
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================
# SENTRY INTEGRATION
# ============================================================

def init_sentry():
    """
    Инициализация Sentry для мониторинга ошибок
    
    Установите SENTRY_DSN в .env для активации
    Пример: SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
    """
    sentry_dsn = os.environ.get('SENTRY_DSN')
    
    if not sentry_dsn:
        logger.info("⚠️ Sentry не настроен (SENTRY_DSN отсутствует)")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastAPIIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        # Настройка Sentry
        sentry_sdk.init(
            dsn=sentry_dsn,
            
            # Интеграции
            integrations=[
                FastAPIIntegration(
                    transaction_style="endpoint",
                    failed_request_status_codes=[500, 501, 502, 503, 504, 505]
                ),
                LoggingIntegration(
                    level=logging.INFO,  # Capture info and above as breadcrumbs
                    event_level=logging.ERROR  # Send errors as events
                )
            ],
            
            # Производительность
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),  # 10% транзакций
            profiles_sample_rate=float(os.environ.get('SENTRY_PROFILES_SAMPLE_RATE', '0.1')),  # 10% профилей
            
            # Окружение
            environment=os.environ.get('ENVIRONMENT', 'production'),
            
            # Дополнительные опции
            send_default_pii=False,  # Не отправлять персональные данные
            attach_stacktrace=True,
            debug=False
        )
        
        logger.info("✅ Sentry инициализирован успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Sentry: {e}")
        return False


def capture_exception(error: Exception, context: Optional[Dict] = None):
    """
    Отправить исключение в Sentry с контекстом
    
    Args:
        error: Исключение для логирования
        context: Дополнительный контекст (user_id, order_id и т.д.)
    """
    try:
        import sentry_sdk
        
        # Добавить контекст если есть
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_tag(key, value)
                
                sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_exception(error)
            
    except Exception as e:
        logger.error(f"Ошибка отправки в Sentry: {e}")


def capture_message(message: str, level: str = "info", context: Optional[Dict] = None):
    """
    Отправить сообщение в Sentry
    
    Args:
        message: Сообщение
        level: Уровень (info, warning, error)
        context: Дополнительный контекст
    """
    try:
        import sentry_sdk
        
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_tag(key, value)
                
                sentry_sdk.capture_message(message, level=level)
        else:
            sentry_sdk.capture_message(message, level=level)
            
    except Exception:
        pass


# ============================================================
# СИСТЕМА МЕТРИК
# ============================================================

class MetricsCollector:
    """
    Сборщик метрик для мониторинга
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            'requests_total': 0,
            'requests_success': 0,
            'requests_failed': 0,
            'orders_created': 0,
            'labels_generated': 0,
            'payments_processed': 0,
            'errors_count': 0,
            'slow_operations': [],
            'circuit_breaker_opens': 0
        }
    
    def increment(self, metric: str, value: int = 1):
        """Увеличить счётчик метрики"""
        if metric in self.metrics:
            self.metrics[metric] += value
    
    def record_slow_operation(self, operation: str, duration: float):
        """Записать медленную операцию"""
        self.metrics['slow_operations'].append({
            'operation': operation,
            'duration': duration,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Оставляем только последние 100
        if len(self.metrics['slow_operations']) > 100:
            self.metrics['slow_operations'] = self.metrics['slow_operations'][-100:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить все метрики"""
        uptime = time.time() - self.start_time
        
        return {
            **self.metrics,
            'uptime_seconds': uptime,
            'uptime_human': self._format_uptime(uptime),
            'success_rate': self._calculate_success_rate(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def _format_uptime(self, seconds: float) -> str:
        """Форматировать время работы"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}ч {minutes}м {secs}с"
    
    def _calculate_success_rate(self) -> float:
        """Рассчитать процент успешных запросов"""
        total = self.metrics['requests_total']
        if total == 0:
            return 100.0
        
        success = self.metrics['requests_success']
        return round((success / total) * 100, 2)


# Глобальный экземпляр сборщика метрик
metrics_collector = MetricsCollector()


# ============================================================
# СИСТЕМНЫЕ МЕТРИКИ
# ============================================================

def get_system_metrics() -> Dict[str, Any]:
    """
    Получить метрики системы (CPU, память, диск)
    """
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Память
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        
        # Диск
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        
        return {
            'cpu': {
                'percent': cpu_percent,
                'count': cpu_count
            },
            'memory': {
                'used_mb': round(memory_used_mb, 2),
                'total_mb': round(memory_total_mb, 2),
                'percent': memory.percent
            },
            'disk': {
                'used_gb': round(disk_used_gb, 2),
                'total_gb': round(disk_total_gb, 2),
                'percent': disk.percent
            }
        }
    except Exception as e:
        logger.error(f"Ошибка сбора системных метрик: {e}")
        return {}


# ============================================================
# HEALTH CHECK
# ============================================================

async def check_health(db) -> Dict[str, Any]:
    """
    Проверка здоровья системы
    
    Args:
        db: MongoDB клиент
    
    Returns:
        Статус всех компонентов
    """
    health = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'components': {}
    }
    
    # Проверка MongoDB
    try:
        await db.command('ping')
        health['components']['mongodb'] = {
            'status': 'healthy',
            'latency_ms': 0  # TODO: измерить реальную задержку
        }
    except Exception as e:
        health['components']['mongodb'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health['status'] = 'degraded'
    
    # Проверка API ключей
    from services.api_services import SHIPSTATION_API_KEY, OXAPAY_API_KEY
    
    health['components']['shipstation_api'] = {
        'status': 'configured' if SHIPSTATION_API_KEY else 'missing'
    }
    
    health['components']['oxapay_api'] = {
        'status': 'configured' if OXAPAY_API_KEY else 'missing'
    }
    
    # Проверка Circuit Breakers
    from utils.retry_utils import SHIPSTATION_CIRCUIT, OXAPAY_CIRCUIT
    
    health['components']['circuit_breakers'] = {
        'shipstation': SHIPSTATION_CIRCUIT.state,
        'oxapay': OXAPAY_CIRCUIT.state
    }
    
    return health


# ============================================================
# АЛЕРТЫ
# ============================================================

class AlertManager:
    """
    Менеджер алертов для критических событий
    """
    
    def __init__(self):
        self.telegram_alerts_enabled = os.environ.get('TELEGRAM_ALERTS_ENABLED', 'false').lower() == 'true'
        self.alert_chat_id = os.environ.get('ALERT_CHAT_ID')
        self.alert_threshold = {
            'error_rate': float(os.environ.get('ALERT_ERROR_RATE', '10.0')),  # %
            'response_time': float(os.environ.get('ALERT_RESPONSE_TIME', '5.0')),  # секунды
            'memory_percent': float(os.environ.get('ALERT_MEMORY_PERCENT', '85.0'))  # %
        }
    
    async def check_and_alert(self, bot=None):
        """
        Проверить метрики и отправить алерты если нужно
        """
        alerts = []
        
        # Проверка процента ошибок
        metrics = metrics_collector.get_metrics()
        if metrics['requests_total'] > 10:  # Минимум 10 запросов
            success_rate = metrics['success_rate']
            error_rate = 100 - success_rate
            
            if error_rate > self.alert_threshold['error_rate']:
                alerts.append(
                    f"🔴 ВЫСОКИЙ ПРОЦЕНТ ОШИБОК: {error_rate:.1f}% "
                    f"(порог: {self.alert_threshold['error_rate']}%)"
                )
        
        # Проверка памяти
        system_metrics = get_system_metrics()
        if system_metrics:
            memory_percent = system_metrics['memory']['percent']
            if memory_percent > self.alert_threshold['memory_percent']:
                alerts.append(
                    f"🟡 ВЫСОКОЕ ИСПОЛЬЗОВАНИЕ ПАМЯТИ: {memory_percent:.1f}% "
                    f"(порог: {self.alert_threshold['memory_percent']}%)"
                )
        
        # Проверка Circuit Breakers
        from utils.retry_utils import SHIPSTATION_CIRCUIT, OXAPAY_CIRCUIT
        
        if SHIPSTATION_CIRCUIT.state == "OPEN":
            alerts.append("🔴 CIRCUIT BREAKER ОТКРЫТ: ShipStation API недоступен")
        
        if OXAPAY_CIRCUIT.state == "OPEN":
            alerts.append("🔴 CIRCUIT BREAKER ОТКРЫТ: Oxapay API недоступен")
        
        # Отправка алертов
        if alerts and self.telegram_alerts_enabled and self.alert_chat_id and bot:
            alert_message = "⚠️ АЛЕРТЫ СИСТЕМЫ:\n\n" + "\n".join(alerts)
            try:
                await bot.send_message(chat_id=self.alert_chat_id, text=alert_message)
                logger.warning(f"Отправлен алерт: {alert_message}")
            except Exception as e:
                logger.error(f"Не удалось отправить алерт: {e}")
        
        return alerts


# Глобальный экземпляр менеджера алертов
alert_manager = AlertManager()


# ============================================================
# ДЕКОРАТОР ДЛЯ ТРЕКИНГА МЕТРИК
# ============================================================

def track_metrics(metric_name: str):
    """
    Декоратор для автоматического трекинга метрик
    
    Usage:
        @track_metrics('orders_created')
        async def create_order():
            ...
    """
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics_collector.increment('requests_total')
            
            try:
                result = await func(*args, **kwargs)
                metrics_collector.increment('requests_success')
                metrics_collector.increment(metric_name)
                return result
            except Exception as e:
                metrics_collector.increment('requests_failed')
                metrics_collector.increment('errors_count')
                raise
        
        return wrapper
    return decorator


# ============================================================
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
# ============================================================

"""
Пример 1: Инициализация при старте
------------------------------------
from utils.monitoring import init_sentry, metrics_collector

# В startup event
init_sentry()

# Доступ к метрикам
metrics = metrics_collector.get_metrics()


Пример 2: Логирование ошибки в Sentry
--------------------------------------
from utils.monitoring import capture_exception

try:
    result = await risky_operation()
except Exception as e:
    capture_exception(e, context={
        'user_id': user_id,
        'order_id': order_id,
        'operation': 'create_label'
    })
    raise


Пример 3: Трекинг метрик
-------------------------
from utils.monitoring import track_metrics

@track_metrics('orders_created')
async def create_order(data):
    order = await db.orders.insert_one(data)
    return order


Пример 4: Health Check
-----------------------
from utils.monitoring import check_health

@app.get("/health")
async def health_check():
    health = await check_health(db)
    return health


Пример 5: Алерты
-----------------
from utils.monitoring import alert_manager

# Периодически проверять
alerts = await alert_manager.check_and_alert(bot)
if alerts:
    logger.warning(f"Найдены алерты: {alerts}")
"""
