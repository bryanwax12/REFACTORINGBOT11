"""
Webhooks Router
Эндпоинты для обработки вебхуков
"""
from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["webhooks"])


@router.post("/oxapay/webhook")
async def oxapay_webhook(request: Request):
    """Handle Oxapay payment webhooks"""
    from handlers.webhook_handlers import handle_oxapay_webhook
    from server import db, bot_instance, safe_telegram_call, create_and_send_label
    from repositories import get_user_repo
    
    user_repo = get_user_repo()
    
    # Simple pending order lookup using db directly
    async def find_pending_order(order_id):
        return await db.pending_orders.find_one({"order_id": order_id}, {"_id": 0})
    
    return await handle_oxapay_webhook(
        request, 
        db, 
        bot_instance, 
        safe_telegram_call, 
        user_repo.find_by_telegram_id,
        find_pending_order,
        create_and_send_label
    )


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    from server import handle_telegram_webhook, application
    
    return await handle_telegram_webhook(request, application)
