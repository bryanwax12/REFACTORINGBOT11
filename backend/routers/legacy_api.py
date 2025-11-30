"""
Legacy API Router
Provides backward compatibility for old API endpoints used by frontend
"""
from fastapi import APIRouter, Header, HTTPException, Depends, Request
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["legacy"])

async def verify_api_key(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    """Verify admin API key - accepts both X-API-Key and Authorization headers"""
    import os
    admin_key = os.environ.get('ADMIN_API_KEY', 'sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024')
    
    # Try X-API-Key first
    api_key = x_api_key
    
    # If not found, try Authorization header (Bearer token)
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]  # Remove "Bearer " prefix
        else:
            api_key = authorization
    
    if not api_key or api_key != admin_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


@router.get("/stats")
async def legacy_get_stats(api_key: str = Depends(verify_api_key)):
    """Legacy stats endpoint - returns dashboard statistics"""
    from server import db
    from handlers.admin_handlers import get_stats_data
    
    stats = await get_stats_data(db)
    return stats


@router.get("/stats/expenses")
async def legacy_get_expense_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Legacy expense stats endpoint - returns real expense data"""
    from server import db
    from handlers.admin_handlers import get_expense_stats_data
    
    stats = await get_expense_stats_data(db, date_from, date_to)
    return stats


@router.get("/orders")
async def legacy_get_orders(api_key: str = Depends(verify_api_key)):
    """Legacy orders endpoint - returns array directly with user enrichment"""
    from server import db
    from repositories import get_user_repo
    import logging
    
    logging.getLogger(__name__)
    
    # Get orders
    orders = await db.orders.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    
    # Enrich with user data
    user_repo = get_user_repo()
    enriched_orders = []
    
    for order in orders:
        telegram_id = order.get('telegram_id')
        if telegram_id:
            user = await user_repo.find_by_telegram_id(telegram_id)
            
            enriched_order = order.copy()
            if user:
                # Add user fields for frontend compatibility
                enriched_order['user_name'] = user.get('first_name', 'Unknown')
                enriched_order['user_username'] = user.get('username', 'no_username')
                enriched_order['first_name'] = user.get('first_name', 'Unknown')  # Legacy field
                enriched_order['username'] = user.get('username', 'no_username')  # Legacy field
            else:
                enriched_order['user_name'] = 'Unknown'
                enriched_order['user_username'] = 'no_username'
                enriched_order['first_name'] = 'Unknown'
                enriched_order['username'] = 'no_username'
            
            enriched_orders.append(enriched_order)
        else:
            # No telegram_id - add defaults
            enriched_order = order.copy()
            enriched_order['user_name'] = 'Unknown'
            enriched_order['user_username'] = 'no_username'
            enriched_order['first_name'] = 'Unknown'
            enriched_order['username'] = 'no_username'
            enriched_orders.append(enriched_order)
    
    return enriched_orders


@router.get("/users")
async def legacy_get_users(api_key: str = Depends(verify_api_key)):
    """Legacy users endpoint - returns array directly"""
    from server import db
    users = await db.users.find({}, {"_id": 0}).limit(100).to_list(100)
    return users


@router.get("/topups")
async def legacy_get_topups(api_key: str = Depends(verify_api_key)):
    """Legacy topups endpoint - returns array directly with user enrichment"""
    from server import db
    from repositories import get_user_repo
    import logging
    
    logging.getLogger(__name__)
    
    # Get topups
    topups = await db.payments.find(
        {"type": "topup"},
        {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    
    # Enrich with user data
    user_repo = get_user_repo()
    enriched_topups = []
    
    for topup in topups:
        telegram_id = topup.get('telegram_id')
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        enriched_topup = topup.copy()
        if user:
            # Add user fields for frontend compatibility
            enriched_topup['user_name'] = user.get('first_name', 'Unknown')
            enriched_topup['user_username'] = user.get('username', '')
            enriched_topup['first_name'] = user.get('first_name', 'Unknown')  # Legacy field
            enriched_topup['username'] = user.get('username', '')  # Legacy field
        else:
            enriched_topup['user_name'] = 'Unknown'
            enriched_topup['user_username'] = ''
            enriched_topup['first_name'] = 'Unknown'
            enriched_topup['username'] = ''
        
        enriched_topups.append(enriched_topup)
    
    return enriched_topups


@router.get("/users/leaderboard")
async def legacy_get_leaderboard(api_key: str = Depends(verify_api_key)):
    """Legacy leaderboard endpoint - returns array with rating metrics"""
    from server import db
    
    # Get top users by balance
    users = await db.users.find(
        {},
        {"_id": 0}
    ).limit(100).to_list(100)
    
    # Calculate rating for each user
    leaderboard = []
    for user in users:
        telegram_id = user.get("telegram_id")
        
        # Get user's orders
        total_orders = await db.orders.count_documents({"telegram_id": telegram_id})
        paid_orders = await db.orders.count_documents({
            "telegram_id": telegram_id,
            "payment_status": "paid"
        })
        
        # Calculate total spent
        spent_result = await db.orders.aggregate([
            {"$match": {"telegram_id": telegram_id, "payment_status": "paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1)
        
        total_spent = spent_result[0]["total"] if spent_result else 0
        
        # Calculate rating score
        rating_score = 0
        rating_score += paid_orders * 10  # 10 points per paid order
        rating_score += total_spent * 0.5  # 0.5 points per dollar spent
        
        # Determine rating level
        if rating_score >= 100:
            rating_level = "🏆 VIP"
        elif rating_score >= 50:
            rating_level = "⭐ Gold"
        elif rating_score >= 20:
            rating_level = "🥈 Silver"
        elif rating_score >= 5:
            rating_level = "🥉 Bronze"
        else:
            rating_level = "🆕 New"
        
        leaderboard.append({
            **user,
            "total_orders": total_orders,
            "paid_orders": paid_orders,
            "total_spent": total_spent,
            "rating_score": rating_score,
            "rating_level": rating_level
        })
    
    # Sort by rating score and return top 10
    leaderboard.sort(key=lambda x: x["rating_score"], reverse=True)
    return leaderboard[:10]


@router.get("/settings/api-mode")
async def legacy_get_api_mode(api_key: str = Depends(verify_api_key)):
    """Legacy API mode endpoint - get current mode"""
    from server import db
    setting = await db.settings.find_one({"key": "api_mode"}, {"_id": 0})
    api_mode = setting.get("value", "production") if setting else "production"
    return {"mode": api_mode}


@router.post("/settings/api-mode")
async def legacy_set_api_mode(req: Request, request: dict, api_key: str = Depends(verify_api_key)):
    """Legacy API mode endpoint - set mode"""
    from server import db, clear_settings_cache, ADMIN_TELEGRAM_ID, api_config_manager
    from handlers.common_handlers import safe_telegram_call
    import server
    import os
    
    # Get bot_instance from app.state
    bot_instance = getattr(req.app.state, 'bot_instance', None)
    
    mode = request.get("mode", "production")
    if mode not in ["production", "test", "preview"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    
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
    
    # Notify admin about API mode change
    if bot_instance and ADMIN_TELEGRAM_ID:
        mode_emoji = "🚀" if mode == "production" else "🧪"
        mode_text = {
            "production": "Продакшн (Production)",
            "test": "Тестовый (Test)",
            "preview": "Превью (Preview)"
        }.get(mode, mode)
        
        admin_message = (
            f"{mode_emoji} *API режим изменен*\n\n"
            f"Новый режим: *{mode_text}*\n"
            f"API ключ: `{masked_key}`\n"
            f"✅ Все пользователи будут использовать новый API ключ"
        )
        
        try:
            await safe_telegram_call(
                bot_instance.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                )
            )
        except Exception as e:
            # Don't fail the request if admin notification fails
            logger.error(f"Failed to notify admin about API mode change: {e}")
    
    return {"success": True, "message": f"API mode set to {mode}"}


@router.get("/maintenance/status")
async def legacy_get_maintenance_status(api_key: str = Depends(verify_api_key)):
    """Legacy maintenance status endpoint"""
    from server import db
    # CRITICAL: Use bot_settings collection (same as maintenance check)
    setting = await db.bot_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
    is_enabled = setting.get("enabled", False) if setting else False
    return {
        "maintenance_mode": is_enabled,
        "message": "Maintenance mode is enabled" if is_enabled else ""
    }


@router.post("/maintenance/enable")
async def legacy_enable_maintenance(request: Request, api_key: str = Depends(verify_api_key)):
    """Legacy maintenance enable endpoint"""
    from server import db, clear_settings_cache
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    await db.settings.update_one(
        {"key": "maintenance_mode"},
        {"$set": {"value": True}},
        upsert=True
    )
    clear_settings_cache()
    
    # Notify all users
    users_notified = 0
    if bot_instance:
        users = await db.users.find({"bot_blocked_by_user": {"$ne": True}}, {"_id": 0}).to_list(1000)
        message = (
            "🔧 *Технические работы*\n\n"
            "Уважаемый пользователь!\n\n"
            "В данный момент проводятся плановые технические работы для улучшения качества сервиса.\n\n"
            "⏰ Примерное время: 10-15 минут\n"
            "✅ Все ваши данные и заказы сохранены\n"
            "📱 Бот вернется к работе в ближайшее время\n\n"
            "Приносим извинения за временные неудобства!\n"
            "Спасибо за понимание 🙏"
        )
        
        for user in users:
            try:
                await safe_telegram_call(
                    bot_instance.send_message(
                        chat_id=user["telegram_id"],
                        text=message,
                        parse_mode='Markdown'
                    )
                )
                users_notified += 1
            except Exception:
                pass
    
    return {"success": True, "message": "Maintenance mode enabled", "users_notified": users_notified}


@router.post("/maintenance/disable")
async def legacy_disable_maintenance(request: Request, api_key: str = Depends(verify_api_key)):
    """Legacy maintenance disable endpoint"""
    from server import db, clear_settings_cache
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    await db.settings.update_one(
        {"key": "maintenance_mode"},
        {"$set": {"value": False}},
        upsert=True
    )
    clear_settings_cache()
    
    # Notify all users
    users_notified = 0
    if bot_instance:
        users = await db.users.find({"bot_blocked_by_user": {"$ne": True}}, {"_id": 0}).to_list(1000)
        message = (
            "✅ *Технические работы завершены!*\n\n"
            "Добрый день!\n\n"
            "Рады сообщить, что все технические работы успешно завершены. "
            "Бот снова полностью работает и готов к приему заказов! 🚀\n\n"
            "Спасибо за терпение и понимание!\n"
            "Приятного использования 😊"
        )
        
        for user in users:
            try:
                await safe_telegram_call(
                    bot_instance.send_message(
                        chat_id=user["telegram_id"],
                        text=message,
                        parse_mode='Markdown'
                    )
                )
                users_notified += 1
            except Exception:
                pass
    
    return {"success": True, "message": "Maintenance mode disabled", "users_notified": users_notified}
