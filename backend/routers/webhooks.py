"""
Webhooks Router
Эндпоинты для обработки вебхуков
"""
from fastapi import APIRouter, Request, BackgroundTasks
import logging
from collections import deque

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["webhooks"])

# ✅ DUPLICATE PROTECTION: Cache of last 1000 processed update_id
# Prevents duplicate processing if Telegram resends the same update
_processed_updates = deque(maxlen=1000)


def is_duplicate_update(update_id: int) -> bool:
    """
    Check if update_id was already processed
    
    Args:
        update_id: Telegram update ID
    
    Returns:
        bool: True if duplicate, False if new
    """
    if update_id in _processed_updates:
        return True
    
    # Add to cache
    _processed_updates.append(update_id)
    return False


@router.post("/oxapay/webhook")
async def oxapay_webhook(request: Request):
    """Handle Oxapay payment webhooks"""
    logger.info("🔔 [OXAPAY_WEBHOOK] Webhook endpoint called!")
    
    try:
        from handlers.webhook_handlers import handle_oxapay_webhook
        from repositories import get_user_repo
        # Import from server inside function to avoid circular import
        import server as srv
        
        # Get bot_instance from app.state instead of server module
        bot_instance = getattr(request.app.state, 'bot_instance', None)
        logger.info(f"🔔 [OXAPAY_WEBHOOK] bot_instance from app.state: {'AVAILABLE' if bot_instance else 'NONE'}")
        
        user_repo = get_user_repo()
        
        # Simple pending order lookup by telegram_id (for topup flow) or order_id (for order flow)
        async def find_pending_order(identifier):
            # Try telegram_id first (for topup), then order_id (for order payment)
            result = await srv.db.pending_orders.find_one({"telegram_id": identifier}, {"_id": 0})
            if not result:
                result = await srv.db.pending_orders.find_one({"order_id": identifier}, {"_id": 0})
            return result
        
        logger.info("🔔 [OXAPAY_WEBHOOK] About to call handle_oxapay_webhook")
        result = await handle_oxapay_webhook(
            request, 
            srv.db, 
            bot_instance,  # Use bot_instance from app.state
            srv.safe_telegram_call, 
            user_repo.find_by_telegram_id,
            find_pending_order,
            srv.create_and_send_label
        )
        logger.info(f"✅ [OXAPAY_WEBHOOK] Webhook processed: {result}")
        return result
    except Exception as e:
        logger.info(f"❌ [OXAPAY_WEBHOOK] Webhook error: {e}")
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.head("/telegram/webhook")
async def telegram_webhook_head():
    """Health check for webhook endpoint"""
    from fastapi.responses import Response
    return Response(status_code=200)

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    logger.info("📨 TELEGRAM WEBHOOK CALLED")
    try:
        import server as srv
        from telegram import Update
        
        # Get the update data from the request
        update_data = await request.json()
        update_id = update_data.get('update_id')
        logger.info(f"📦 Update data received: update_id={update_id}")
        
        # ✅ DUPLICATE PROTECTION: Check if this update was already processed
        if update_id and is_duplicate_update(update_id):
            logger.warning(f"⚠️ Duplicate update_id={update_id} detected, skipping processing")
            from fastapi.responses import Response
            return Response(status_code=200)
        
        # Check if application is initialized
        if not srv.application:
            logger.error("❌ Application not initialized")
            # ✅ Return 200 OK to prevent Telegram from retrying
            from fastapi.responses import Response
            return Response(status_code=200)
        
        # Check if application was initialized properly (PTB requirement)
        if not srv.application.running:
            logger.error("❌ Application not running - initialize() was not called")
            # ✅ Return 200 OK to prevent Telegram from retrying
            from fastapi.responses import Response
            return Response(status_code=200)
        
        # Fix missing 'is_bot' field in user data (Telegram API compatibility)
        if 'message' in update_data and 'from' in update_data['message']:
            if 'is_bot' not in update_data['message']['from']:
                update_data['message']['from']['is_bot'] = False
        if 'callback_query' in update_data and 'from' in update_data['callback_query']:
            if 'is_bot' not in update_data['callback_query']['from']:
                update_data['callback_query']['from']['is_bot'] = False
        
        # Create a Telegram Update object using application's bot
        update = Update.de_json(update_data, srv.application.bot)
        
        if update:
            logger.info(f"✅ Processing update {update.update_id}")
            # Process update ASYNCHRONOUSLY - return 200 immediately
            # This prevents Telegram timeout and duplicate updates
            import asyncio
            asyncio.create_task(srv.application.process_update(update))
            logger.info(f"✅ Update {update.update_id} queued for processing")
            # Return 200 OK immediately (Telegram recommendation)
            from fastapi.responses import Response
            return Response(status_code=200)
        else:
            logger.error("⚠️ Update is None")
            from fastapi.responses import Response
            return Response(status_code=200)  # Still return 200 to avoid retries
            
    except Exception as e:
        logger.error(f"❌ Error processing Telegram webhook: {e}", exc_info=True)
        # Return 200 even on error to prevent Telegram from retrying
        from fastapi.responses import Response
        return Response(status_code=200)
