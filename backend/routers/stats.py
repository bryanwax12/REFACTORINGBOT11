"""
Stats Router
Эндпоинты для статистики и аналитики
"""
from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_stats():
    """Get general statistics"""
    from server import get_stats_data
    
    try:
        stats = await get_stats_data()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses")
async def get_expense_stats():
    """Get expense statistics"""
    from server import get_expense_stats_data
    
    try:
        stats = await get_expense_stats_data()
        return stats
    except Exception as e:
        logger.error(f"Error getting expense stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topups")
async def get_topups():
    """Get topup history with user details"""
    from server import db
    from repositories import get_user_repo
    
    try:
        # Get all topups
        topups = await db.payments.find(
            {"type": "topup"},
            {"_id": 0}
        ).sort("created_at", -1).limit(100).to_list(100)
        
        # Enrich with user data
        user_repo = get_user_repo()
        enriched_topups = []
        
        for topup in topups:
            user = await user_repo.find_by_telegram_id(topup['telegram_id'])
            
            enriched_topup = topup.copy()
            if user:
                enriched_topup['user_name'] = user.get('first_name', 'Unknown')
                enriched_topup['user_username'] = user.get('username', '')
            else:
                enriched_topup['user_name'] = 'Unknown'
                enriched_topup['user_username'] = ''
            
            enriched_topups.append(enriched_topup)
        
        return enriched_topups
    except Exception as e:
        logger.error(f"Error getting topups: {e}")
        raise HTTPException(status_code=500, detail=str(e))
