"""
Debug Router
Эндпоинты для отладки (только для development)
"""
from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/logs")
async def get_debug_logs(lines: int = 100):
    """Get recent log lines"""
    try:
        import subprocess
        result = subprocess.run(
            ['tail', '-n', str(lines), '/var/log/supervisor/backend.out.log'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return {"logs": result.stdout}
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clear-all-conversations")
async def clear_all_conversations():
    """Clear all active conversations (для тестирования)"""
    from server import application
    
    try:
        if hasattr(application, 'persistence') and application.persistence:
            await application.persistence.flush()
            return {"status": "success", "message": "All conversations cleared"}
        return {"status": "success", "message": "No persistence configured"}
    except Exception as e:
        logger.error(f"Error clearing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active-conversations")
async def get_active_conversations():
    """Get list of active conversations"""
    from server import application
    
    try:
        if hasattr(application, 'persistence') and application.persistence:
            # This is a simplified version - actual implementation may vary
            return {
                "status": "success",
                "message": "Active conversations endpoint",
                "count": 0
            }
        return {"status": "no persistence"}
    except Exception as e:
        logger.error(f"Error getting active conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/persistence")
async def check_persistence():
    """Check persistence status"""
    from server import application
    
    try:
        has_persistence = hasattr(application, 'persistence') and application.persistence is not None
        return {
            "enabled": has_persistence,
            "type": type(application.persistence).__name__ if has_persistence else None
        }
    except Exception as e:
        logger.error(f"Error checking persistence: {e}")
        raise HTTPException(status_code=500, detail=str(e))
