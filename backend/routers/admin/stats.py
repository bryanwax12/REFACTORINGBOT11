"""
Admin Stats Router
Handles statistics and analytics endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from handlers.admin_handlers import verify_admin_key
import logging
import pymongo.errors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["admin-stats"])


@router.get("/dashboard")
async def get_dashboard_stats(
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get main dashboard statistics
    
    Returns comprehensive statistics for admin dashboard
    """
    from server import db
    from services.admin.stats_admin_service import stats_admin_service
    
    try:
        stats = await stats_admin_service.get_dashboard_stats(db)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return stats
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error getting dashboard stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Unexpected error getting dashboard stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses")
async def get_expense_stats(
    days: int = Query(30, ge=1, le=365),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get expense statistics for specified period
    
    Query Parameters:
    - days: Number of days to analyze (1-365)
    """
    from server import db
    from services.admin.stats_admin_service import stats_admin_service
    
    try:
        stats = await stats_admin_service.get_expense_stats(db, days=days)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return stats
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error getting expense stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Unexpected error getting expense stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topups")
async def get_topup_stats(
    limit: int = Query(50, ge=1, le=500),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get recent top-up statistics
    
    Query Parameters:
    - limit: Number of recent top-ups to return (1-500)
    """
    from server import db
    from services.admin.stats_admin_service import stats_admin_service
    
    try:
        stats = await stats_admin_service.get_topup_stats(db, limit=limit)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return stats
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error getting topup stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Unexpected error getting topup stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance_stats(
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get performance statistics
    
    Returns active sessions, pending orders, and payment success rate
    """
    from server import db
    from services.admin.stats_admin_service import stats_admin_service
    
    try:
        stats = await stats_admin_service.get_performance_stats(db)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return stats
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error getting performance stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Unexpected error getting performance stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
