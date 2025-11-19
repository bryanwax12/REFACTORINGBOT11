"""
Monitoring Router
API endpoints для мониторинга и health checks
"""
from fastapi import APIRouter, Depends, HTTPException
import logging
from handlers.admin_handlers import verify_admin_key
from utils.monitoring import (
    metrics_collector,
    get_system_metrics,
    check_health,
    alert_manager
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/health")
async def health_check():
    """
    Проверка здоровья системы (публичный endpoint)
    
    Проверяет:
    - MongoDB подключение
    - Наличие API ключей
    - Статус circuit breakers
    
    Returns:
        Статус компонентов системы
    """
    from server import db
    
    health = await check_health(db)
    
    # Вернуть 503 если система нездорова
    if health['status'] != 'healthy':
        raise HTTPException(
            status_code=503,
            detail=f"Service degraded: {health}"
        )
    
    return health


@router.get("/metrics")
async def get_metrics(authenticated: bool = Depends(verify_admin_key)):
    """
    Получить метрики приложения (требует авторизацию)
    
    Метрики включают:
    - Счётчики запросов (total, success, failed)
    - Счётчики бизнес-операций (orders, labels, payments)
    - Медленные операции
    - Процент успешных запросов
    - Время работы (uptime)
    
    Returns:
        Словарь с метриками
    """
    metrics = metrics_collector.get_metrics()
    return {
        "success": True,
        "metrics": metrics,
        "message": "Метрики успешно получены"
    }


@router.get("/system")
async def get_system_info(authenticated: bool = Depends(verify_admin_key)):
    """
    Получить системные метрики (требует авторизацию)
    
    Метрики включают:
    - CPU использование
    - Память (RAM)
    - Диск
    
    Returns:
        Системные метрики
    """
    system_metrics = get_system_metrics()
    
    return {
        "success": True,
        "system": system_metrics,
        "message": "Системные метрики успешно получены"
    }


@router.get("/combined")
async def get_combined_metrics(authenticated: bool = Depends(verify_admin_key)):
    """
    Получить все метрики (приложение + система)
    
    Полный дашборд для мониторинга
    """
    from server import db
    
    # Собрать все метрики
    app_metrics = metrics_collector.get_metrics()
    system_metrics = get_system_metrics()
    health = await check_health(db)
    
    return {
        "success": True,
        "timestamp": app_metrics['timestamp'],
        "health": health,
        "application": app_metrics,
        "system": system_metrics,
        "message": "Все метрики успешно получены"
    }


@router.post("/alert/test")
async def test_alert(authenticated: bool = Depends(verify_admin_key)):
    """
    Тестовый алерт для проверки настроек
    
    Отправит тестовое уведомление если алерты настроены
    """
    from utils.monitoring import capture_message
    
    try:
        # Отправить тестовое сообщение в Sentry
        capture_message(
            "🧪 Тестовый алерт мониторинга",
            level="info",
            context={"test": True}
        )
        
        return {
            "success": True,
            "message": "Тестовый алерт отправлен (проверьте Sentry)"
        }
    except Exception as e:
        logger.error(f"Ошибка отправки тестового алерта: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Не удалось отправить алерт"
        }


@router.get("/alerts/check")
async def check_alerts(authenticated: bool = Depends(verify_admin_key)):
    """
    Проверить текущие алерты
    
    Проверяет:
    - Процент ошибок
    - Использование памяти
    - Статус circuit breakers
    
    Returns:
        Список активных алертов
    """
    alerts = await alert_manager.check_and_alert(bot=None)  # bot=None, не отправляем
    
    return {
        "success": True,
        "alerts_count": len(alerts),
        "alerts": alerts,
        "message": f"Найдено алертов: {len(alerts)}"
    }


@router.get("/slow-operations")
async def get_slow_operations(
    limit: int = 20,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Получить список медленных операций
    
    Args:
        limit: Количество записей (по умолчанию 20)
    
    Returns:
        Список медленных операций с длительностью
    """
    metrics = metrics_collector.get_metrics()
    slow_ops = metrics.get('slow_operations', [])
    
    # Отсортировать по длительности (самые медленные сверху)
    slow_ops_sorted = sorted(
        slow_ops,
        key=lambda x: x['duration'],
        reverse=True
    )[:limit]
    
    return {
        "success": True,
        "count": len(slow_ops_sorted),
        "operations": slow_ops_sorted,
        "message": f"Найдено медленных операций: {len(slow_ops_sorted)}"
    }


@router.post("/metrics/reset")
async def reset_metrics(authenticated: bool = Depends(verify_admin_key)):
    """
    Сбросить метрики (для тестирования)
    
    ⚠️ ВНИМАНИЕ: Сбрасывает все счётчики!
    """
    global metrics_collector
    
    from utils.monitoring import MetricsCollector
    metrics_collector = MetricsCollector()
    
    logger.warning("⚠️ Метрики сброшены вручную")
    
    return {
        "success": True,
        "message": "Метрики успешно сброшены"
    }


# ============================================================
# ДОПОЛНИТЕЛЬНЫЕ ЭНДПОИНТЫ
# ============================================================

@router.get("/uptime")
async def get_uptime():
    """
    Получить время работы сервиса (публичный endpoint)
    """
    metrics = metrics_collector.get_metrics()
    
    return {
        "success": True,
        "uptime_seconds": metrics['uptime_seconds'],
        "uptime_human": metrics['uptime_human'],
        "started_at": metrics['timestamp']
    }


@router.get("/version")
async def get_version():
    """
    Получить версию API (публичный endpoint)
    """
    return {
        "success": True,
        "version": "1.0.0",
        "api": "Telegram Shipping Bot",
        "features": [
            "async_http",
            "retry_logic",
            "circuit_breakers",
            "monitoring"
        ]
    }
