"""
Maintenance Router
Эндпоинты для управления режимом обслуживания
"""
from fastapi import APIRouter, HTTPException, Depends, Body, Request
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


# REMOVED: Duplicate enable/disable endpoints
# All maintenance operations should use:
# - /api/maintenance/enable (legacy_api.py) - used by frontend
# - /api/admin/maintenance/enable (admin_router.py) - new standard API
