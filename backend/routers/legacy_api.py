"""
Legacy API Router
Provides backward compatibility for old API endpoints used by frontend
"""
from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Optional

router = APIRouter(prefix="/api", tags=["legacy"])

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify admin API key"""
    import os
    admin_key = os.environ.get('ADMIN_API_KEY', 'sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024')
    if not x_api_key or x_api_key != admin_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


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
    """Legacy orders endpoint - returns array directly"""
    from server import db
    orders = await db.orders.find({}, {"_id": 0}).limit(100).to_list(100)
    return orders


@router.get("/users")
async def legacy_get_users(api_key: str = Depends(verify_api_key)):
    """Legacy users endpoint - returns array directly"""
    from server import db
    users = await db.users.find({}, {"_id": 0}).limit(100).to_list(100)
    return users


@router.get("/topups")
async def legacy_get_topups(api_key: str = Depends(verify_api_key)):
    """Legacy topups endpoint - returns array directly"""
    from server import db
    payments = await db.payments.find(
        {"type": "topup"},
        {"_id": 0}
    ).limit(100).to_list(100)
    return payments


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
async def legacy_set_api_mode(request: dict, api_key: str = Depends(verify_api_key)):
    """Legacy API mode endpoint - set mode"""
    from server import db, clear_settings_cache
    
    mode = request.get("mode", "production")
    if mode not in ["production", "test", "preview"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    await db.settings.update_one(
        {"key": "api_mode"},
        {"$set": {"value": mode}},
        upsert=True
    )
    clear_settings_cache()
    
    return {"success": True, "message": f"API mode set to {mode}"}


@router.get("/maintenance/status")
async def legacy_get_maintenance_status(api_key: str = Depends(verify_api_key)):
    """Legacy maintenance status endpoint"""
    from server import db
    setting = await db.settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
    is_enabled = setting.get("value", False) if setting else False
    return {
        "maintenance_mode": is_enabled,
        "message": "Maintenance mode is enabled" if is_enabled else ""
    }


@router.post("/maintenance/enable")
async def legacy_enable_maintenance(api_key: str = Depends(verify_api_key)):
    """Legacy maintenance enable endpoint"""
    from server import db, clear_settings_cache, bot_instance
    from handlers.common_handlers import safe_telegram_call
    
    await db.settings.update_one(
        {"key": "maintenance_mode"},
        {"$set": {"value": True}},
        upsert=True
    )
    clear_settings_cache()
    
    # Notify all users
    users_notified = 0
    if bot_instance:
        users = await db.users.find({"blocked": False, "bot_blocked_by_user": {"$ne": True}}, {"_id": 0}).to_list(1000)
        message = "⚠️ *Режим технического обслуживания*\n\nБот временно недоступен для технического обслуживания.\nМы скоро вернемся!"
        
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
            except:
                pass
    
    return {"success": True, "message": "Maintenance mode enabled", "users_notified": users_notified}


@router.post("/maintenance/disable")
async def legacy_disable_maintenance(api_key: str = Depends(verify_api_key)):
    """Legacy maintenance disable endpoint"""
    from server import db, clear_settings_cache, bot_instance
    from handlers.common_handlers import safe_telegram_call
    
    await db.settings.update_one(
        {"key": "maintenance_mode"},
        {"$set": {"value": False}},
        upsert=True
    )
    clear_settings_cache()
    
    # Notify all users
    users_notified = 0
    if bot_instance:
        users = await db.users.find({"blocked": False, "bot_blocked_by_user": {"$ne": True}}, {"_id": 0}).to_list(1000)
        message = "✅ *Технические работы завершены*\n\nБот снова работает! Спасибо за ожидание."
        
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
            except:
                pass
    
    return {"success": True, "message": "Maintenance mode disabled", "users_notified": users_notified}
