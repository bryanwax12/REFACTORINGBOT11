"""
Admin API Router - Complete Implementation
All admin endpoints migrated from server.py
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
async def block_user(request: Request, telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Block a user from using the bot"""
    from server import db
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        # Check if user exists
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": True}}
        )
        
        if result.modified_count > 0:
            if bot_instance:
                try:
                    message = (
                        "⛔️ *АККАУНТ ЗАБЛОКИРОВАН*\n\n"
                        "🚫 Ваш доступ к боту ограничен администратором.\n\n"
                        "📞 Для разблокировки обратитесь в поддержку."
                    )
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message,
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
async def unblock_user(request: Request, telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Unblock a user to allow bot usage"""
    from server import db
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        # Check if user exists
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": False}}
        )
        
        if result.modified_count > 0:
            if bot_instance:
                try:
                    message = (
                        "✅ *АККАУНТ РАЗБЛОКИРОВАН*\n\n"
                        "🎉 Ваш доступ к боту восстановлен!\n\n"
                        "✨ Теперь вы можете пользоваться всеми функциями.\n\n"
                        "💫 Добро пожаловать обратно!"
                    )
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message,
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
    from server import db, clear_settings_cache, bot_instance
    from handlers.common_handlers import safe_telegram_call
    
    logger.info("🔧 enable_maintenance_mode endpoint called (admin_router)")
    
    try:
        # Save to bot_settings (used by middleware check)
        result = await db.bot_settings.update_one(
            {"key": "maintenance_mode"},
            {"$set": {"enabled": True, "message": "Бот временно на техническом обслуживании. Попробуйте позже."}},
            upsert=True
        )
        
        logger.info(f"✅ Maintenance saved to DB (matched: {result.matched_count}, modified: {result.modified_count}, upserted: {result.upserted_id})")
        
        # Verify it was saved
        verify = await db.bot_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
        logger.info(f"✅ Verified settings: {verify}")
        
        clear_settings_cache()
        
        # Broadcast notification to all users
        if bot_instance:
            try:
                logger.info("📢 Broadcasting maintenance ENABLED notification to all users...")
                users = await db.users.find(
                    {"bot_blocked_by_user": {"$ne": True}},
                    {"_id": 0, "telegram_id": 1}
                ).to_list(10000)
                
                notification_text = "🔧 *Режим обслуживания*\n\nБот временно на техническом обслуживании. Попробуйте позже."
                
                success_count = 0
                failed_count = 0
                
                for user in users:
                    try:
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=user['telegram_id'],
                            text=notification_text,
                            parse_mode='Markdown'
                        ))
                        success_count += 1
                    except Exception as send_error:
                        failed_count += 1
                        if "bot was blocked" in str(send_error).lower():
                            await db.users.update_one(
                                {"telegram_id": user['telegram_id']},
                                {"$set": {"bot_blocked_by_user": True}}
                            )
                
                logger.info(f"✅ Maintenance ENABLED notification sent: {success_count} success, {failed_count} failed")
            except Exception as broadcast_error:
                logger.error(f"Error broadcasting maintenance notification: {broadcast_error}")
        
        return {"success": True, "message": "Maintenance mode enabled"}
    except Exception as e:
        logger.error(f"Error enabling maintenance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/maintenance/disable")
async def disable_maintenance_mode(authenticated: bool = Depends(verify_admin_key)):
    """Disable maintenance mode"""
    from server import db, clear_settings_cache, bot_instance
    from utils.telegram_utils import safe_telegram_call
    
    logger.info("✅ disable_maintenance_mode endpoint called (admin_router)")
    
    try:
        # Update bot_settings (used by middleware check)
        result = await db.bot_settings.update_one(
            {"key": "maintenance_mode"},
            {"$set": {"enabled": False}},
            upsert=True
        )
        
        logger.info(f"✅ Maintenance disabled in DB (matched: {result.matched_count}, modified: {result.modified_count})")
        
        # Verify
        verify = await db.bot_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
        logger.info(f"✅ Verified settings: {verify}")
        
        clear_settings_cache()
        
        # Broadcast notification to all users
        if bot_instance:
            try:
                logger.info("📢 Broadcasting maintenance DISABLED notification to all users...")
                users = await db.users.find(
                    {"bot_blocked_by_user": {"$ne": True}},
                    {"_id": 0, "telegram_id": 1}
                ).to_list(10000)
                
                notification_text = "✅ *Бот снова работает!*\n\nТехническое обслуживание завершено. Вы можете продолжить пользоваться ботом."
                
                success_count = 0
                failed_count = 0
                
                for user in users:
                    try:
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=user['telegram_id'],
                            text=notification_text,
                            parse_mode='Markdown'
                        ))
                        success_count += 1
                    except Exception as send_error:
                        failed_count += 1
                        if "bot was blocked" in str(send_error).lower():
                            await db.users.update_one(
                                {"telegram_id": user['telegram_id']},
                                {"$set": {"bot_blocked_by_user": True}}
                            )
                
                logger.info(f"✅ Maintenance DISABLED notification sent: {success_count} success, {failed_count} failed")
            except Exception as broadcast_error:
                logger.error(f"Error broadcasting maintenance disabled notification: {broadcast_error}")
        
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
        topups = await db.payments.find(
            {"type": "topup"},
            {"_id": 0}  # Exclude ObjectId to avoid serialization issues
        ).sort("created_at", -1).to_list(1000)
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



# Legacy compatibility endpoints for frontend
@admin_router.get("/settings/api-mode")
async def get_api_mode_legacy(authenticated: bool = Depends(verify_admin_key)):
    """Get current API mode (legacy endpoint for frontend compatibility)"""
    from server import db
    
    try:
        setting = await db.settings.find_one({"key": "api_mode"})
        api_mode = setting.get("value", "production") if setting else "production"
        
        return {
            "mode": api_mode,  # Frontend expects 'mode' key
            "message": f"API mode is set to {api_mode}"
        }
    except Exception as e:
        logger.error(f"Error getting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/settings/api-mode")
async def set_api_mode_legacy(request: dict, authenticated: bool = Depends(verify_admin_key)):
    """Set API mode (legacy endpoint for frontend compatibility)"""
    from server import db, clear_settings_cache, api_config_manager
    import server
    
    try:
        mode = request.get("mode", "production")
        if mode not in ["production", "test", "preview"]:
            raise HTTPException(status_code=400, detail="Invalid mode. Use 'production', 'test' or 'preview'")
        
        # Update database
        await db.settings.update_one(
            {"key": "api_mode"},
            {"$set": {"value": mode}},
            upsert=True
        )
        clear_settings_cache()
        
        # ⚠️ CRITICAL: Update api_config_manager environment
        api_config_manager.set_environment(mode)
        
        # ⚠️ CRITICAL: Update global SHIPSTATION_API_KEY variable
        server.SHIPSTATION_API_KEY = api_config_manager.get_shipstation_key()
        
        # Log the change with masked key
        masked_key = api_config_manager._mask_key(server.SHIPSTATION_API_KEY)
        logger.info(f"✅ API mode changed to: {mode.upper()}")
        logger.info(f"   ShipStation key updated: {masked_key}")
        
        return {
            "success": True,
            "mode": mode,
            "message": f"API mode set to {mode}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# DEBUGGING & LOGGING
# ============================================================

@admin_router.get("/logs")
async def get_debug_logs(
    lines: int = Query(200),
    filter: str = Query(""),
    authenticated: bool = Depends(verify_admin_key)
):
    """Get recent backend logs for debugging"""
    import subprocess
    import os
    from datetime import datetime, timezone
    
    try:
        log_files = [
            "/var/log/supervisor/backend.err.log",
            "/var/log/supervisor/backend.out.log",
            "/var/log/backend.log",
            "/app/backend.log",
            "backend.log"
        ]
        
        all_logs = []
        found_files = []
        
        for log_file in log_files:
            if os.path.exists(log_file):
                found_files.append(log_file)
                try:
                    cmd = f"tail -n {lines} {log_file}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                    if result.stdout:
                        all_logs.extend([f"[{log_file}] {line}" for line in result.stdout.split('\n') if line])
                except Exception as e:
                    logger.warning(f"Error reading log file {log_file}: {e}")
        
        # Filter if requested
        if filter:
            all_logs = [line for line in all_logs if filter.upper() in line.upper()]
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_lines": len(all_logs),
            "filter": filter or "none",
            "log_files_found": found_files,
            "logs": all_logs[-100:]  # Max 100 lines
        }
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/health")
async def get_bot_health(request: Request, authenticated: bool = Depends(verify_admin_key)):
    """Get bot health status"""
    from server import db, application
    from datetime import datetime, timezone
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bot_instance": bot_instance is not None,
            "application": application is not None,
            "database": False
        }
        
        # Test database connection
        try:
            await db.command('ping')
            health_status["database"] = True
        except Exception as e:
            health_status["database_error"] = str(e)
        
        # Get bot info if available
        if bot_instance:
            try:
                me = await bot_instance.get_me()
                health_status["bot_username"] = me.username
                health_status["bot_id"] = me.id
            except Exception as e:
                health_status["bot_error"] = str(e)
        
        return health_status
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/metrics")
async def get_bot_metrics(authenticated: bool = Depends(verify_admin_key)):
    """Get bot metrics and statistics"""
    from server import db
    from datetime import datetime, timezone, timedelta
    
    try:
        # Get counts
        total_users = await db.users.count_documents({})
        total_orders = await db.orders.count_documents({})
        paid_orders = await db.orders.count_documents({"payment_status": "paid"})
        
        # Get recent activity (last 24 hours)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        yesterday_str = yesterday.isoformat()
        
        recent_users = await db.users.count_documents({"created_at": {"$gte": yesterday_str}})
        recent_orders = await db.orders.count_documents({"created_at": {"$gte": yesterday_str}})
        
        # Get active sessions
        active_sessions = await db.user_sessions.count_documents({})
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "users": {
                "total": total_users,
                "recent_24h": recent_users
            },
            "orders": {
                "total": total_orders,
                "paid": paid_orders,
                "recent_24h": recent_orders
            },
            "sessions": {
                "active": active_sessions
            }
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# SHIPSTATION INTEGRATION
# ============================================================

@admin_router.post("/shipstation/check-balance")
async def check_shipstation_balance_endpoint(authenticated: bool = Depends(verify_admin_key)):
    """Check ShipStation carrier balances"""
    from services.api_services import check_shipstation_balance
    
    try:
        low_balance_carriers = await check_shipstation_balance()
        
        if low_balance_carriers is None:
            return {
                "success": False,
                "message": "Failed to check ShipStation balance"
            }
        
        if len(low_balance_carriers) == 0:
            return {
                "success": True,
                "message": "All carriers have sufficient balance",
                "carriers": []
            }
        
        return {
            "success": True,
            "message": f"Found {len(low_balance_carriers)} carriers with low balance",
            "carriers": low_balance_carriers
        }
    except Exception as e:
        logger.error(f"Error checking ShipStation balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Note: Additional endpoints can be added here following the same pattern
# - invite_user_to_channel
# - invite_all_users_to_channel  
# - broadcast
# - check_bot_access
# - check_user_channel_status



# ============================================================
# LEGACY COMPATIBILITY ENDPOINTS (for frontend)
# ============================================================

@admin_router.get("/users/{telegram_id}/details")
async def get_user_details_legacy(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """
    Legacy endpoint for user details
    Used by frontend - provides detailed user statistics
    """
    from server import db
    from services.admin.user_admin_service import user_admin_service
    
    try:
        stats = await user_admin_service.get_user_stats(db, telegram_id)
        
        if "error" in stats:
            raise HTTPException(status_code=404, detail=stats["error"])
        
        return stats
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/users/{telegram_id}/balance/add")
async def add_user_balance_legacy(
    request: Request,
    telegram_id: int,
    amount: float = Query(..., gt=0),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Legacy endpoint to add balance to user
    Used by frontend - adds specified amount to user balance
    """
    from server import db
    from services.admin.user_admin_service import user_admin_service
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        success, new_balance, error = await user_admin_service.update_user_balance(
            db,
            telegram_id,
            amount,
            operation="add"
        )
        
        if success:
            # Send beautiful notification to user
            if bot_instance:
                try:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    
                    message = (
                        "💰 *БАЛАНС ПОПОЛНЕН*\n\n"
                        f"✨ Администратор добавил:\n"
                        f"💵 *+${amount:.2f}*\n\n"
                        f"💳 Текущий баланс: *${new_balance:.2f}*\n\n"
                        f"🎉 Спасибо!"
                    )
                    
                    # Add "Continue Order" button
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📦 Продолжить заказ", callback_data="continue_order")]
                    ])
                    
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    ))
                    logger.info(f"Balance notification sent to user {telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send balance notification: {e}")
            
            return {
                "success": True,
                "new_balance": new_balance,
                "message": f"Added ${amount} to balance"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/users/{telegram_id}/balance/deduct")
async def deduct_user_balance_legacy(
    request: Request,
    telegram_id: int,
    amount: float = Query(..., gt=0),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Legacy endpoint to deduct balance from user
    Used by frontend - subtracts specified amount from user balance
    """
    from server import db
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        # Get current balance first
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0, "balance": 1})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_balance = user.get("balance", 0)
        new_balance = max(0, current_balance - amount)
        
        # Update balance
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"balance": new_balance}}
        )
        
        # Send beautiful notification to user
        if bot_instance:
            try:
                message = (
                    "⚠️ *БАЛАНС ИЗМЕНЕН*\n\n"
                    f"📉 Администратор снял:\n"
                    f"💸 *-${amount:.2f}*\n\n"
                    f"💳 Текущий баланс: *${new_balance:.2f}*\n\n"
                    f"❓ Вопросы? Свяжитесь с поддержкой."
                )
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode='Markdown'
                ))
                logger.info(f"Balance deduction notification sent to user {telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send balance deduction notification: {e}")
        
        logger.info(f"Admin deducted ${amount} from user {telegram_id}. New balance: ${new_balance}")
        
        return {
            "success": True,
            "new_balance": new_balance,
            "message": f"Deducted ${amount} from balance"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deducting balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# DEBUG / MAINTENANCE ENDPOINTS
# ============================================================

@admin_router.post("/users/{telegram_id}/clear-session-data")
async def clear_user_session_data(
    telegram_id: int,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Clear all session and conversation data for a specific user
    
    This is useful when a user has stuck/corrupted data that causes issues
    like the 5-second delay problem from old debounce data
    """
    from server import db
    
    try:
        # Check if user exists
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Clear user session data
        session_result = await db.user_sessions.delete_many({"user_id": telegram_id})
        
        logger.info(f"✅ Admin cleared session data for user {telegram_id}")
        logger.info(f"   Sessions deleted: {session_result.deleted_count}")
        
        return {
            "success": True,
            "telegram_id": telegram_id,
            "sessions_deleted": session_result.deleted_count,
            "message": "User session data cleared. User needs to send /start to create new session."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing session data for user {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/clear-all-sessions")
async def clear_all_sessions(authenticated: bool = Depends(verify_admin_key)):
    """
    Clear ALL user sessions (DANGER: This resets all active conversations)
    
    Use this to clean up after major bot changes that affect session structure
    """
    from server import db
    
    try:
        # Delete all sessions
        result = await db.user_sessions.delete_many({})
        
        logger.warning(f"⚠️ Admin cleared ALL sessions! Count: {result.deleted_count}")
        
        return {
            "success": True,
            "sessions_deleted": result.deleted_count,
            "message": "All sessions cleared. All users need to send /start."
        }
    
    except Exception as e:
        logger.error(f"Error clearing all sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

