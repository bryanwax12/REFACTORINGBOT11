"""
Settings Router
Эндпоинты для управления настройками
"""
from fastapi import APIRouter, HTTPException, Depends
from handlers.admin_handlers import verify_admin_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/api-mode")
async def get_api_mode():
    """Get current API mode (ShipStation provider)"""
    from server import api_config_manager
    
    try:
        current_mode = api_config_manager.get_current_mode()
        
        return {
            "current_mode": current_mode,
            "available_modes": ["production", "test"]
        }
    except Exception as e:
        logger.error(f"Error getting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api-mode")
async def set_api_mode(mode: str):
    """Set API mode (production/test)"""
    from server import api_config_manager
    
    try:
        if mode not in ["production", "test"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid mode. Use 'production' or 'test'"
            )
        
        success = api_config_manager.switch_mode(mode)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to switch API mode"
            )
        
        return {
            "status": "success",
            "new_mode": mode,
            "message": f"Switched to {mode} mode"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))
