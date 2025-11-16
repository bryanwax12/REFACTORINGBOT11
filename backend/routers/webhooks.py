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
        
        # Simple pending order lookup by telegram_id (for topup flow) or order_id (for order flow)
        async def find_pending_order(identifier):
            # Try telegram_id first (for topup), then order_id (for order payment)
            result = await srv.db.pending_orders.find_one({"telegram_id": identifier}, {"_id": 0})
            if not result:
                result = await srv.db.pending_orders.find_one({"order_id": identifier}, {"_id": 0})
            return result
        
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
    try:
        import server as srv
        from telegram import Update
        
        # Get the update data from the request
        update_data = await request.json()
        
        # Create a Telegram Update object
        update = Update.de_json(update_data, srv.bot_instance)
        
        if update and srv.application:
            # Process the update through the application
            await srv.application.process_update(update)
            return {"ok": True}
        else:
            logger.warning("No update or application not initialized")
            return {"ok": False, "error": "Application not ready"}
            
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}
