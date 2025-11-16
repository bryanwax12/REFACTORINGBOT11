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
    import logging
    logger = logging.getLogger(__name__)
    print("🔔🔔🔔 WEBHOOK ENDPOINT CALLED! 🔔🔔🔔")
    logger.info("🔔 Webhook endpoint called!")
    
    try:
        from handlers.webhook_handlers import handle_oxapay_webhook
        from repositories import get_user_repo
        # Import from server inside function to avoid circular import
        import server as srv
        
        print("✅ All imports successful")
        logger.info("✅ All imports successful")
        
        user_repo = get_user_repo()
        
        # Simple pending order lookup using db directly
        async def find_pending_order(order_id):
            return await srv.db.pending_orders.find_one({"order_id": order_id}, {"_id": 0})
        
        print("🚀 About to call handle_oxapay_webhook...")
        result = await handle_oxapay_webhook(
            request, 
            srv.db, 
            srv.bot_instance, 
            srv.safe_telegram_call, 
            user_repo.find_by_telegram_id,
            find_pending_order,
            srv.create_and_send_label
        )
        print(f"✅ Webhook processed: {result}")
        logger.info(f"✅ Webhook processed: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    from server import handle_telegram_webhook, application
    
    return await handle_telegram_webhook(request, application)
