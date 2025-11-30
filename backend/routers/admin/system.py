"""
Admin System Router
Handles system management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from handlers.admin_handlers import verify_admin_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["admin-system"])


# Request models
class MaintenanceMessage(BaseModel):
    message: str = "Бот находится на обслуживании."


class ApiModeUpdate(BaseModel):
    enabled: bool


@router.get("/maintenance")
async def get_maintenance_status(
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get maintenance mode status
    """
    from server import db
    from services.admin.system_admin_service import system_admin_service
    
    try:
        status = await system_admin_service.get_maintenance_status(db)
        
        if "error" in status:
            raise HTTPException(status_code=500, detail=status["error"])
        
        return status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# REMOVED: Duplicate enable/disable maintenance endpoints
# All maintenance operations should use:
# - /api/maintenance/enable (legacy_api.py) - used by frontend
# - /api/admin/maintenance/enable (admin_router.py) - new standard API


@router.post("/sessions/clear")
async def clear_all_sessions(
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Clear all user sessions
    """
    from server import db, session_manager
    from services.admin.system_admin_service import system_admin_service
    
    try:
        success, count, message = await system_admin_service.clear_all_sessions(
            db,
            session_manager
        )
        
        if success:
            return {
                "success": True,
                "sessions_cleared": count,
                "message": message
            }
        else:
            raise HTTPException(status_code=500, detail=message)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api-mode")
async def get_api_mode(
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get API-only mode status
    """
    from server import db
    from services.admin.system_admin_service import system_admin_service
    
    try:
        status = await system_admin_service.get_api_mode(db)
        
        if "error" in status:
            raise HTTPException(status_code=500, detail=status["error"])
        
        return status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api-mode")
async def set_api_mode(
    payload: ApiModeUpdate,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Set API-only mode
    
    Request Body:
    - enabled: Whether to enable API-only mode
    """
    from server import db
    from services.admin.system_admin_service import system_admin_service
    
    try:
        success, message = await system_admin_service.set_api_mode(
            db,
            payload.enabled
        )
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=500, detail=message)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_system_logs(
    level: str = Query("ERROR", regex="^(ALL|DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    limit: int = Query(100, ge=1, le=1000),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get system logs
    
    Query Parameters:
    - level: Log level filter (ALL, DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - limit: Number of log lines to return (1-1000)
    """
    from server import db
    from services.admin.system_admin_service import system_admin_service
    
    try:
        logs = await system_admin_service.get_system_logs(db, level=level, limit=limit)
        
        if "error" in logs:
            raise HTTPException(status_code=500, detail=logs["error"])
        
        return logs
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shipstation/check-balance")
async def check_shipstation_balance(
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Check ShipStation account balance
    """
    from services.admin.system_admin_service import system_admin_service
    
    try:
        result = await system_admin_service.check_shipstation_balance()
        
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking ShipStation balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
