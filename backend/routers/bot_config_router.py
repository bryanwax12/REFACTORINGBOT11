"""
Bot Configuration Management API
API endpoints для управления конфигурацией бота
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
import logging
from handlers.admin_handlers import verify_admin_key
from utils.bot_config import get_bot_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot-config", tags=["bot-configuration"])


@router.get("/status")
async def get_bot_config_status():
    """
    Получить текущую конфигурацию бота (публичный endpoint для мониторинга)
    
    Returns:
        Текущие настройки бота (без чувствительной информации)
    """
    config = get_bot_config()
    summary = config.get_config_summary()
    
    return {
        "success": True,
        "config": {
            "environment": summary['environment'],
            "mode": summary['mode'],
            "bot_username": summary['bot_username'],
            "webhook_enabled": summary['webhook_enabled'],
            "is_production": summary['is_production']
        }
    }


@router.get("/full")
async def get_bot_config_full(authenticated: bool = Depends(verify_admin_key)):
    """
    Получить полную конфигурацию бота (требует аутентификацию)
    
    Включает:
    - Все настройки окружения
    - Webhook URL (если используется)
    - Информация о ботах
    
    Returns:
        Полная конфигурация бота
    """
    config = get_bot_config()
    config.get_config_summary()
    
    return {
        "success": True,
        "config": {
            "environment": config.environment,
            "mode": config.mode,
            "bot_username": config.get_active_bot_username(),
            "test_bot": {
                "username": config.test_bot_username,
                "configured": bool(config.test_bot_token)
            },
            "prod_bot": {
                "username": config.prod_bot_username,
                "configured": bool(config.prod_bot_token)
            },
            "webhook": {
                "enabled": config.should_use_webhook(),
                "url": config.get_webhook_url() if config.should_use_webhook() else None,
                "base_url": config.webhook_base_url,
                "path": config.webhook_path
            },
            "is_production": config.is_production()
        },
        "message": "Full bot configuration retrieved"
    }


@router.post("/switch-environment")
async def switch_environment(
    data: Dict,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Переключить окружение бота (требует аутентификацию и перезапуск)
    
    Body:
        {
            "environment": "test" или "production"
        }
    
    Note:
        Требует перезапуск сервера для применения изменений!
    """
    new_env = data.get('environment', '').lower()
    
    if new_env not in ['test', 'production']:
        raise HTTPException(
            status_code=400,
            detail="Invalid environment. Must be 'test' or 'production'"
        )
    
    config = get_bot_config()
    old_env = config.environment
    
    if old_env == new_env:
        return {
            "success": True,
            "message": f"Already using {new_env} environment",
            "config": config.get_config_summary()
        }
    
    try:
        config.switch_environment(new_env)
        
        logger.warning(f"⚠️ Bot environment switched: {old_env} -> {new_env}")
        
        return {
            "success": True,
            "message": f"Environment switched from {old_env} to {new_env}",
            "warning": "⚠️ SERVER RESTART REQUIRED for changes to take effect!",
            "old_environment": old_env,
            "new_environment": new_env,
            "config": config.get_config_summary()
        }
    except Exception as e:
        logger.error(f"Failed to switch environment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch-mode")
async def switch_mode(
    data: Dict,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Переключить режим работы бота (требует аутентификацию и перезапуск)
    
    Body:
        {
            "mode": "polling" или "webhook"
        }
    
    Note:
        Требует перезапуск сервера для применения изменений!
    """
    new_mode = data.get('mode', '').lower()
    
    if new_mode not in ['polling', 'webhook']:
        raise HTTPException(
            status_code=400,
            detail="Invalid mode. Must be 'polling' or 'webhook'"
        )
    
    config = get_bot_config()
    old_mode = config.mode
    
    if old_mode == new_mode:
        return {
            "success": True,
            "message": f"Already using {new_mode} mode",
            "config": config.get_config_summary()
        }
    
    try:
        config.switch_mode(new_mode)
        
        logger.warning(f"⚠️ Bot mode switched: {old_mode} -> {new_mode}")
        
        return {
            "success": True,
            "message": f"Mode switched from {old_mode} to {new_mode}",
            "warning": "⚠️ SERVER RESTART REQUIRED for changes to take effect!",
            "old_mode": old_mode,
            "new_mode": new_mode,
            "config": config.get_config_summary()
        }
    except Exception as e:
        logger.error(f"Failed to switch mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhook-info")
async def get_webhook_info(authenticated: bool = Depends(verify_admin_key)):
    """
    Получить информацию о webhook из Telegram API
    
    Полезно для диагностики проблем с webhook
    
    Returns:
        Информация о текущем webhook
    """
    from server import bot_instance
    
    if not bot_instance:
        raise HTTPException(
            status_code=503,
            detail="Bot instance not initialized"
        )
    
    try:
        webhook_info = await bot_instance.get_webhook_info()
        
        return {
            "success": True,
            "webhook_info": {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": webhook_info.last_error_date.isoformat() if webhook_info.last_error_date else None,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": webhook_info.allowed_updates
            }
        }
    except Exception as e:
        logger.error(f"Failed to get webhook info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set-webhook")
async def set_webhook_manually(
    data: Dict,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Вручную установить webhook (для отладки)
    
    Body:
        {
            "url": "https://example.com/api/telegram/webhook"
        }
    
    Note:
        Обычно webhook устанавливается автоматически при запуске
    """
    from server import bot_instance
    
    if not bot_instance:
        raise HTTPException(
            status_code=503,
            detail="Bot instance not initialized"
        )
    
    webhook_url = data.get('url', '').strip()
    
    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Webhook URL required"
        )
    
    if not webhook_url.startswith('https://'):
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must use HTTPS"
        )
    
    try:
        # Удалить старый webhook
        await bot_instance.delete_webhook(drop_pending_updates=True)
        
        # Установить новый
        await bot_instance.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"]
        )
        
        logger.info(f"✅ Webhook set manually: {webhook_url}")
        
        return {
            "success": True,
            "message": "Webhook set successfully",
            "webhook_url": webhook_url
        }
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-webhook")
async def delete_webhook(authenticated: bool = Depends(verify_admin_key)):
    """
    Удалить webhook (переключиться на polling вручную)
    
    Note:
        После удаления webhook нужно запустить polling
    """
    from server import bot_instance
    
    if not bot_instance:
        raise HTTPException(
            status_code=503,
            detail="Bot instance not initialized"
        )
    
    try:
        await bot_instance.delete_webhook(drop_pending_updates=True)
        
        logger.info("✅ Webhook deleted")
        
        return {
            "success": True,
            "message": "Webhook deleted successfully",
            "note": "You may need to start polling manually"
        }
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_config_recommendations():
    """
    Получить рекомендации по конфигурации для текущего окружения
    
    Returns:
        Рекомендуемые настройки
    """
    config = get_bot_config()
    
    recommendations = {
        "current": config.get_config_summary(),
        "recommendations": []
    }
    
    # Проверка на production без webhook
    if config.is_production() and not config.should_use_webhook():
        recommendations["recommendations"].append({
            "type": "warning",
            "message": "Production environment should use webhook mode",
            "suggestion": "Set BOT_MODE=webhook in .env"
        })
    
    # Проверка на test с webhook
    if config.is_test() and config.should_use_webhook():
        recommendations["recommendations"].append({
            "type": "info",
            "message": "Test environment usually uses polling mode",
            "suggestion": "Consider using BOT_MODE=polling for easier development"
        })
    
    # Проверка на webhook без URL
    if config.should_use_webhook() and not config.webhook_base_url:
        recommendations["recommendations"].append({
            "type": "error",
            "message": "Webhook mode enabled but WEBHOOK_BASE_URL not set",
            "suggestion": "Set WEBHOOK_BASE_URL in .env"
        })
    
    # Проверка на отсутствие токенов
    if not config.test_bot_token:
        recommendations["recommendations"].append({
            "type": "warning",
            "message": "TEST_BOT_TOKEN not configured",
            "suggestion": "Set TEST_BOT_TOKEN in .env for test environment"
        })
    
    if not config.prod_bot_token:
        recommendations["recommendations"].append({
            "type": "warning",
            "message": "PROD_BOT_TOKEN not configured",
            "suggestion": "Set PROD_BOT_TOKEN in .env for production environment"
        })
    
    return {
        "success": True,
        **recommendations
    }
