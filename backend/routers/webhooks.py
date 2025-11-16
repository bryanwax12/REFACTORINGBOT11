"""
Webhooks Router
Эндпоинты для обработки вебхуков
"""
from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


@router.post("/oxapay/webhook")
async def oxapay_webhook(request: Request):
    """Handle Oxapay payment webhooks"""
    from handlers.webhook_handlers import handle_oxapay_webhook
    from server import db, bot_instance, safe_telegram_call, create_and_send_label
    from repositories import get_user_repo, get_order_repo
    
    user_repo = get_user_repo()
    order_repo = get_order_repo()
    
    return await handle_oxapay_webhook(
        request, 
        db, 
        bot_instance, 
        safe_telegram_call, 
        user_repo.find_by_telegram_id,  # Use repository method
        order_repo.find_pending_by_order_id,  # Use repository method
        create_and_send_label
    )


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    from server import handle_telegram_webhook, application
    
    return await handle_telegram_webhook(request, application)
