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
    print("🔔 [OXAPAY_WEBHOOK] Webhook endpoint called!")
    
    try:
        from handlers.webhook_handlers import handle_oxapay_webhook
        from repositories import get_user_repo
        # Import from server inside function to avoid circular import
        import server as srv
        
        # Get bot_instance from app.state instead of server module
        bot_instance = getattr(request.app.state, 'bot_instance', None)
        print(f"🔔 [OXAPAY_WEBHOOK] bot_instance from app.state: {'AVAILABLE' if bot_instance else 'NONE'}")
        
        user_repo = get_user_repo()
        
        # Simple pending order lookup by telegram_id (for topup flow) or order_id (for order flow)
        async def find_pending_order(identifier):
            # Try telegram_id first (for topup), then order_id (for order payment)
            result = await srv.db.pending_orders.find_one({"telegram_id": identifier}, {"_id": 0})
            if not result:
                result = await srv.db.pending_orders.find_one({"order_id": identifier}, {"_id": 0})
            return result
        
        print("🔔 [OXAPAY_WEBHOOK] About to call handle_oxapay_webhook")
        result = await handle_oxapay_webhook(
            request, 
            srv.db, 
            bot_instance,  # Use bot_instance from app.state
            srv.safe_telegram_call, 
            user_repo.find_by_telegram_id,
            find_pending_order,
            srv.create_and_send_label
        )
        print(f"✅ [OXAPAY_WEBHOOK] Webhook processed: {result}")
        return result
    except Exception as e:
        print(f"❌ [OXAPAY_WEBHOOK] Webhook error: {e}")
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    try:
        import server as srv
        from telegram import Update
        
        # Get the update data from the request
        update_data = await request.json()
        
        # Check if application is initialized
        if not srv.application:
            logger.error("Application not initialized")
            return {"ok": False, "error": "Application not ready"}
        
        # Create a Telegram Update object using application's bot
        update = Update.de_json(update_data, srv.application.bot)
        
        if update:
            # Process the update through the application
            await srv.application.process_update(update)
            return {"ok": True}
        else:
            logger.warning("Update is None")
            return {"ok": False, "error": "Invalid update"}
            
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}
