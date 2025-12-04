"""
Admin handlers and API endpoints
Includes: authentication, notifications, stats, and admin utilities
"""
import logging
from typing import Optional
from fastapi import Header, HTTPException
from datetime import datetime, timezone, timedelta
import telegram.error
import pymongo.errors

# Logger
logger = logging.getLogger(__name__)


# ==================== AUTHENTICATION ====================

async def verify_admin_key(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    """
    Verify admin API key for protected endpoints
    SECURITY: Denies access if ADMIN_API_KEY not set
    Accepts both X-API-Key and Authorization headers for compatibility
    """
    from middleware.security import security_manager
    
    # Try X-API-Key first (custom header)
    api_key = x_api_key
    
    # If not found, try Authorization header (Bearer token)
    if not api_key and authorization:
        # Extract token from "Bearer <token>" format
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]  # Remove "Bearer " prefix
        else:
            api_key = authorization
    
    # Use centralized security manager (fixes critical vulnerability)
    return security_manager.verify_admin_api_key(api_key)


# ==================== ADMIN NOTIFICATIONS ====================

async def notify_admin_error(user_info: dict, error_type: str, error_details: str, order_id: str = None):
    """Send error notification to admin"""
    from server import ADMIN_TELEGRAM_ID, bot_instance
    from handlers.common_handlers import safe_telegram_call
    
    logger.info(f"🔔 notify_admin_error called: error_type={error_type}, order_id={order_id}")
    
    if not ADMIN_TELEGRAM_ID:
        logger.warning("⚠️ ADMIN_TELEGRAM_ID not set, skipping error notification")
        return
    
    if not bot_instance:
        logger.warning("⚠️ bot_instance not available, skipping error notification")
        return
    
    try:
        username = user_info.get('username', 'N/A')
        telegram_id = user_info.get('telegram_id', 'N/A')
        first_name = user_info.get('first_name', 'N/A')
        
        logger.info(f"📤 Sending error notification to admin {ADMIN_TELEGRAM_ID} for user {telegram_id}")
        
        message = f"""🚨 <b>ОШИБКА В БОТЕ</b> 🚨

👤 <b>Пользователь:</b>
   • ID: {telegram_id}
   • Имя: {first_name}
   • Username: @{username if username != 'N/A' else 'не указан'}

❌ <b>Тип ошибки:</b> {error_type}

📋 <b>Детали:</b>
{error_details}
"""
        
        if order_id:
            message += f"\n🔖 <b>Order ID:</b> {order_id}"
        
        await safe_telegram_call(bot_instance.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=message,
            parse_mode='HTML'
        ))
        logger.info(f"✅ Error notification sent to admin successfully")
    except telegram.error.BadRequest as e:
        logger.error(f"❌ Telegram bad request sending admin notification: {e}")
    except telegram.error.TelegramError as e:
        logger.error(f"❌ Telegram error sending admin notification: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ Unexpected error sending admin notification: {e}", exc_info=True)


# ==================== ADMIN STATISTICS ====================

async def get_stats_data(db):
    """Get statistics data for admin dashboard"""
    total_users = await db.users.count_documents({})
    total_orders = await db.orders.count_documents({})
    paid_orders = await db.orders.count_documents({"payment_status": "paid"})
    
    # Calculate total revenue
    total_revenue = await db.orders.aggregate([
        {"$match": {"payment_status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    
    revenue = total_revenue[0]['total'] if total_revenue else 0
    
    # Calculate profit: $10 per created label
    total_labels = await db.shipping_labels.count_documents({"status": "created"})
    total_profit = total_labels * 10.0
    
    # Calculate total user balance (sum of all user balances)
    total_user_balance = await db.users.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]).to_list(1)
    
    user_balance_sum = total_user_balance[0]['total'] if total_user_balance else 0
    
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "total_revenue": revenue,
        "total_profit": total_profit,
        "total_labels": total_labels,
        "total_user_balance": user_balance_sum
    }


async def get_expense_stats_data(db, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Get expenses statistics (money spent on ShipStation labels)"""
    try:
        # Build query for paid orders with labels
        query = {"payment_status": "paid"}
        
        # Add date filter if provided
        if date_from or date_to:
            date_query = {}
            if date_from:
                date_query["$gte"] = date_from
            if date_to:
                # Add one day to include the end date
                end_date = datetime.fromisoformat(date_to) + timedelta(days=1)
                date_query["$lt"] = end_date.isoformat()
            query["created_at"] = date_query
        
        # Get all paid orders with original_amount (real cost from ShipStation)
        total_spent = await db.orders.aggregate([
            {"$match": query},
            {"$match": {"original_amount": {"$exists": True}}},
            {"$group": {"_id": None, "total": {"$sum": "$original_amount"}}}
        ]).to_list(1)
        
        total_expense = total_spent[0]['total'] if total_spent else 0
        
        # Get count of labels created (without refunded)
        labels_query = {"status": "created"}
        if date_from or date_to:
            date_query = {}
            if date_from:
                date_query["$gte"] = date_from
            if date_to:
                end_date = datetime.fromisoformat(date_to) + timedelta(days=1)
                date_query["$lt"] = end_date.isoformat()
            labels_query["created_at"] = date_query
        
        labels_count = await db.shipping_labels.count_documents(labels_query)
        
        # Get today's expenses
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_query = {
            "payment_status": "paid",
            "original_amount": {"$exists": True},
            "created_at": {"$gte": today_start.isoformat()}
        }
        
        today_spent = await db.orders.aggregate([
            {"$match": today_query},
            {"$group": {"_id": None, "total": {"$sum": "$original_amount"}}}
        ]).to_list(1)
        
        today_expense = today_spent[0]['total'] if today_spent else 0
        
        # Get today's label count
        today_labels = await db.shipping_labels.count_documents({
            "status": "created",
            "created_at": {"$gte": today_start.isoformat()}
        })
        
        return {
            "total_expense": total_expense,
            "labels_count": labels_count,
            "today_expense": today_expense,
            "today_labels": today_labels,
            "date_from": date_from,
            "date_to": date_to
        }
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error getting expense stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Unexpected error getting expense stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
