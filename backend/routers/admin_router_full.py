"""
Admin API Router - Complete Implementation
All admin endpoints migrated from server.py
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from handlers.admin_handlers import verify_admin_key, get_stats_data, get_expense_stats_data
import logging

logger = logging.getLogger(__name__)

# Create admin router
admin_router = APIRouter(
    prefix="/api/admin",
    tags=["admin"]
)

# Import dependencies that will be needed
# Note: These imports happen at function level to avoid circular imports


# ============================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================

@admin_router.get("/users")
async def get_users(authenticated: bool = Depends(verify_admin_key)):
    """Get all users"""
    from server import db
    users = await db.users.find({}, {"_id": 0}).to_list(100)
    return users


@admin_router.post("/users/{telegram_id}/block")
async def block_user(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Block a user from using the bot"""
    from server import db, bot_instance, find_user_by_telegram_id
    from handlers.common_handlers import safe_telegram_call
    
    try:
        user = await find_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": True}}
        )
        
        if result.modified_count > 0:
            if bot_instance:
                try:
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text="⛔️ *Вы были заблокированы администратором.*\n\nДоступ к боту ограничен.",
                        parse_mode='Markdown'
                    ))
                except Exception as e:
                    logger.error(f"Failed to send block notification: {e}")
            
            return {"success": True, "message": "User blocked successfully"}
        else:
            return {"success": False, "message": "User already blocked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/users/{telegram_id}/unblock")
async def unblock_user(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Unblock a user to allow bot usage"""
    from server import db, bot_instance, find_user_by_telegram_id
    from handlers.common_handlers import safe_telegram_call
    
    try:
        user = await find_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": False}}
        )
        
        if result.modified_count > 0:
            if bot_instance:
                try:
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text="✅ *Вы были разблокированы!*\n\nТеперь вы можете снова использовать бот.",
                        parse_mode='Markdown'
                    ))
                except Exception as e:
                    logger.error(f"Failed to send unblock notification: {e}")
            
            return {"success": True, "message": "User unblocked successfully"}
        else:
            return {"success": False, "message": "User already unblocked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# MAINTENANCE MODE ENDPOINTS
# ============================================================

@admin_router.get("/maintenance/status")
async def get_maintenance_status(authenticated: bool = Depends(verify_admin_key)):
    """Get current maintenance mode status"""
    from server import db
    
    try:
        setting = await db.settings.find_one({"key": "maintenance_mode"})
        is_enabled = setting.get("value", False) if setting else False
        
        return {
            "maintenance_mode": is_enabled,
            "message": "Maintenance mode is enabled" if is_enabled else "Maintenance mode is disabled"
        }
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/maintenance/enable")
async def enable_maintenance_mode(authenticated: bool = Depends(verify_admin_key)):
    """Enable maintenance mode"""
    from server import db, clear_settings_cache
    
    try:
        await db.settings.update_one(
            {"key": "maintenance_mode"},
            {"$set": {"value": True}},
            upsert=True
        )
        clear_settings_cache()
        return {"success": True, "message": "Maintenance mode enabled"}
    except Exception as e:
        logger.error(f"Error enabling maintenance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/maintenance/disable")
async def disable_maintenance_mode(authenticated: bool = Depends(verify_admin_key)):
    """Disable maintenance mode"""
    from server import db, clear_settings_cache
    
    try:
        await db.settings.update_one(
            {"key": "maintenance_mode"},
            {"$set": {"value": False}},
            upsert=True
        )
        clear_settings_cache()
        return {"success": True, "message": "Maintenance mode disabled"}
    except Exception as e:
        logger.error(f"Error disabling maintenance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# STATISTICS ENDPOINTS
# ============================================================

@admin_router.get("/stats")
async def get_stats(authenticated: bool = Depends(verify_admin_key)):
    """Get bot statistics"""
    from server import db
    
    try:
        stats = await get_stats_data(db)
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/stats/expenses")
async def get_expense_stats(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    authenticated: bool = Depends(verify_admin_key)
):
    """Get expense statistics"""
    from server import db
    
    try:
        stats = await get_expense_stats_data(db, date_from, date_to)
        return stats
    except Exception as e:
        logger.error(f"Error getting expense stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/topups")
async def get_topups(authenticated: bool = Depends(verify_admin_key)):
    """Get all top-up payments"""
    from server import db
    
    try:
        topups = await db.payments.find({"type": "topup"}).sort("created_at", -1).to_list(1000)
        return topups
    except Exception as e:
        logger.error(f"Error getting topups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PERFORMANCE & MONITORING
# ============================================================

@admin_router.get("/performance/stats")
async def get_performance_stats(authenticated: bool = Depends(verify_admin_key)):
    """Get performance monitoring statistics"""
    from utils.performance import get_performance_stats as get_stats
    
    try:
        stats = get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting performance stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# SESSION MANAGEMENT
# ============================================================

@admin_router.post("/sessions/clear")
async def clear_all_conversations(authenticated: bool = Depends(verify_admin_key)):
    """Clear all user sessions (for debugging stuck conversations)"""
    from server import db, session_manager
    
    try:
        # Clear TTL-based sessions from MongoDB
        result = await db.user_sessions.delete_many({})
        sessions_cleared = result.deleted_count
        
        # Also clear SessionManager's in-memory cache if exists
        if hasattr(session_manager, 'clear_all'):
            await session_manager.clear_all()
        
        logger.info(f"Admin cleared {sessions_cleared} sessions")
        
        return {
            "success": True,
            "sessions_cleared": sessions_cleared,
            "message": f"Cleared {sessions_cleared} active sessions"
        }
    except Exception as e:
        logger.error(f"Error clearing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API MODE MANAGEMENT
# ============================================================

@admin_router.get("/api-mode")
async def get_api_mode(authenticated: bool = Depends(verify_admin_key)):
    """Get current API mode (production/preview)"""
    from server import db
    
    try:
        setting = await db.settings.find_one({"key": "api_mode"})
        api_mode = setting.get("value", "production") if setting else "production"
        
        return {
            "api_mode": api_mode,
            "message": f"API mode is set to {api_mode}"
        }
    except Exception as e:
        logger.error(f"Error getting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/api-mode")
async def set_api_mode(request: dict, authenticated: bool = Depends(verify_admin_key)):
    """Set API mode (production/preview)"""
    from server import db, clear_settings_cache
    
    try:
        mode = request.get("mode", "production")
        if mode not in ["production", "preview"]:
            raise HTTPException(status_code=400, detail="Invalid mode. Use 'production' or 'preview'")
        
        await db.settings.update_one(
            {"key": "api_mode"},
            {"$set": {"value": mode}},
            upsert=True
        )
        clear_settings_cache()
        
        return {"success": True, "message": f"API mode set to {mode}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Note: Additional endpoints (health, logs, metrics, bot access checks, etc.)
# can be added here following the same pattern
