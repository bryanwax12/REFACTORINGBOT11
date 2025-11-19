"""
Bot Management Router
Эндпоинты для управления ботом
"""
from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot", tags=["bot"])


@router.get("/health")
async def bot_health():
    """Check bot health status"""
    from server import bot_instance, application
    
    try:
        if not bot_instance:
            return {"status": "error", "message": "Bot not initialized"}
        
        bot_info = await bot_instance.get_me()
        
        return {
            "status": "healthy",
            "bot_username": bot_info.username,
            "bot_id": bot_info.id,
            "bot_name": bot_info.first_name,
            "application_running": application is not None
        }
    except Exception as e:
        logger.error(f"Error checking bot health: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/status")
async def telegram_status():
    """Get detailed Telegram bot status"""
    from server import bot_instance, application, BOT_MODE
    
    try:
        if not bot_instance:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        
        bot_info = await bot_instance.get_me()
        
        webhook_info = None
        if BOT_MODE == "webhook":
            webhook_info = await bot_instance.get_webhook_info()
        
        return {
            "bot_id": bot_info.id,
            "username": bot_info.username,
            "first_name": bot_info.first_name,
            "mode": BOT_MODE,
            "webhook_info": {
                "url": webhook_info.url if webhook_info else None,
                "has_custom_certificate": webhook_info.has_custom_certificate if webhook_info else False,
                "pending_update_count": webhook_info.pending_update_count if webhook_info else 0
            } if BOT_MODE == "webhook" else None,
            "application_initialized": application is not None
        }
    except Exception as e:
        logger.error(f"Error getting telegram status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart")
async def restart_bot():
    """Restart bot (supervisor restart)"""
    import subprocess
    
    try:
        # Restart backend service via supervisor
        result = subprocess.run(
            ['sudo', 'supervisorctl', 'restart', 'backend'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return {
            "status": "restarting",
            "message": "Bot restart initiated",
            "output": result.stdout
        }
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_bot_logs(lines: int = 100):
    """Get recent bot logs"""
    import subprocess
    
    try:
        result = subprocess.run(
            ['tail', '-n', str(lines), '/var/log/supervisor/backend.out.log'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        return {
            "logs": result.stdout,
            "lines": lines
        }
    except Exception as e:
        logger.error(f"Error getting bot logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_bot_metrics():
    """Get bot metrics and statistics"""
    from server import db
    from repositories import get_user_repo, get_order_repo
    
    try:
        user_repo = get_user_repo()
        order_repo = get_order_repo()
        
        # Get basic metrics
        total_users = await user_repo.count()
        total_orders = await order_repo.count()
        
        # Get recent activity
        active_sessions = await db.user_sessions.count_documents({})
        pending_orders = await db.pending_orders.count_documents({})
        
        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "active_sessions": active_sessions,
            "pending_orders": pending_orders
        }
    except Exception as e:
        logger.error(f"Error getting bot metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
