"""
Maintenance Router
Эндпоинты для управления режимом обслуживания
"""
from fastapi import APIRouter, HTTPException, Depends
from handlers.admin_handlers import verify_admin_key
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("/status")
async def get_maintenance_status():
    """Get current maintenance mode status"""
    from server import db
    
    try:
        settings = await db.bot_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
        
        if not settings:
            return {
                "enabled": False,
                "message": None
            }
        
        return {
            "enabled": settings.get("enabled", False),
            "message": settings.get("message")
        }
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable", dependencies=[Depends(verify_admin_key)])
async def enable_maintenance(message: Optional[str] = None):
    """Enable maintenance mode - ADMIN ONLY"""
    from server import db
    
    try:
        maintenance_message = message or "Бот временно на техническом обслуживании. Попробуйте позже."
        
        await db.bot_settings.update_one(
            {"key": "maintenance_mode"},
            {
                "$set": {
                    "enabled": True,
                    "message": maintenance_message
                }
            },
            upsert=True
        )
        
        logger.info("🔧 Maintenance mode ENABLED")
        
        return {
            "status": "enabled",
            "message": maintenance_message
        }
    except Exception as e:
        logger.error(f"Error enabling maintenance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_maintenance():
    """Disable maintenance mode"""
    from server import db
    
    try:
        await db.bot_settings.update_one(
            {"key": "maintenance_mode"},
            {
                "$set": {
                    "enabled": False,
                    "message": None
                }
            },
            upsert=True
        )
        
        logger.info("✅ Maintenance mode DISABLED")
        
        return {
            "status": "disabled",
            "message": "Maintenance mode disabled"
        }
    except Exception as e:
        logger.error(f"Error disabling maintenance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
