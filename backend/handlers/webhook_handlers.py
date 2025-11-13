"""
Webhook handlers for external services
Handles payment webhooks from Oxapay and Telegram bot updates
"""
import logging
from fastapi import Request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def handle_oxapay_webhook(request: Request, db, bot_instance, safe_telegram_call, find_user_by_telegram_id, find_pending_order, create_and_send_label):
    """
    Handle Oxapay payment webhooks
    
    Process payment notifications from Oxapay:
    - Update payment status in database
    - Handle top-up payments (add to user balance)
    - Handle order payments (trigger label creation)
    - Send notifications to users
    
    Args:
        request: FastAPI Request object with webhook payload
        db: MongoDB database connection
        bot_instance: Telegram Bot instance
        safe_telegram_call: Safe Telegram API wrapper
        find_user_by_telegram_id: User lookup function
        find_pending_order: Pending order lookup function
        create_and_send_label: Label creation function
    
    Returns:
        dict: Status response for Oxapay
    """
    try:
        body = await request.json()
        logger.info(f"Oxapay webhook received: {body}")
        
        # Extract payment info - Oxapay sends snake_case keys
        track_id = body.get('track_id') or body.get('trackId')  # Support both formats
        status = body.get('status')  # Waiting, Confirming, Paying, Paid, Expired, etc.
        order_id = body.get('order_id') or body.get('orderId')  # Support both formats
        paid_amount = body.get('paidAmount') or body.get('paid_amount') or body.get('amount', 0)  # Actual paid amount
        
        # Convert track_id to int if it's a string number
        if track_id and isinstance(track_id, str) and track_id.isdigit():
            track_id = int(track_id)
        
        if status == 'Paid':
            payment = await db.payments.find_one({"invoice_id": track_id}, {"_id": 0})
            if payment:
                # Update payment status
                await db.payments.update_one(
                    {"invoice_id": track_id},
                    {"$set": {"status": "paid", "paid_amount": paid_amount}}
                )
                
                # Check if it's a top-up
                if payment.get('type') == 'topup':
                    # Add to balance - use actual paid amount
                    telegram_id = payment.get('telegram_id')
                    requested_amount = payment.get('amount', 0)
                    actual_amount = paid_amount if paid_amount > 0 else requested_amount
                    
                    await db.users.update_one(
                        {"telegram_id": telegram_id},
                        {"$inc": {"balance": actual_amount}}
                    )
                    
                    # Remove "Оплатить" button from payment message
                    payment_message_id = payment.get('payment_message_id')
                    logger.info(f"Payment message_id for removal: {payment_message_id}")
                    if payment_message_id and bot_instance:
                        try:
                            await safe_telegram_call(bot_instance.edit_message_reply_markup(
                                chat_id=telegram_id,
                                message_id=payment_message_id,
                                reply_markup=None
                            ))
                            logger.info(f"Removed payment button from message {payment_message_id}")
                        except Exception as e:
                            logger.warning(f"Could not remove payment button: {e}")
                    
                    # Remove "Назад" and "Главное меню" buttons from topup input message
                    topup_input_message_id = payment.get('topup_input_message_id')
                    logger.info(f"Topup input message_id for removal: {topup_input_message_id}")
                    if topup_input_message_id and bot_instance:
                        try:
                            await safe_telegram_call(bot_instance.edit_message_reply_markup(
                                chat_id=telegram_id,
                                message_id=topup_input_message_id,
                                reply_markup=None
                            ))
                            logger.info(f"Removed topup input buttons from message {topup_input_message_id}")
                        except Exception as e:
                            # Ignore "message not modified" error (buttons already removed)
                            if "message is not modified" in str(e).lower():
                                logger.info(f"Topup input buttons already removed from message {topup_input_message_id}")
                            else:
                                logger.warning(f"Could not remove topup input buttons: {e}")
                    else:
                        logger.warning("No topup_input_message_id found in payment record")
                    
                    # Notify user
                    if bot_instance:
                        from utils.ui_utils import MessageTemplates, get_payment_success_keyboard
                        
                        user = await find_user_by_telegram_id(telegram_id)
                        new_balance = user.get('balance', 0)
                        
                        pending_order = await find_pending_order(telegram_id)
                        order_amount = 0.0
                        has_pending_order = False
                        
                        if pending_order and pending_order.get('selected_rate'):
                            has_pending_order = True
                            order_amount = pending_order.get('final_amount', pending_order['selected_rate']['amount'])
                        
                        # Build message using template
                        if has_pending_order:
                            message_text = MessageTemplates.balance_topped_up_with_order(
                                requested_amount, actual_amount, new_balance, order_amount
                            )
                        else:
                            message_text = MessageTemplates.balance_topped_up(
                                requested_amount, actual_amount, new_balance
                            )
                        
                        reply_markup = get_payment_success_keyboard(has_pending_order, order_amount)
                        
                        bot_msg = await safe_telegram_call(bot_instance.send_message(
                            chat_id=telegram_id,
                            text=message_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        ))
                        
                        # Save message context in pending_orders for button protection
                        await db.pending_orders.update_one(
                            {"telegram_id": telegram_id},
                            {"$set": {
                                "topup_success_message_id": bot_msg.message_id,
                                "topup_success_message_text": message_text
                            }}
                        )
                else:
                    # Regular order payment
                    # Update order
                    await db.orders.update_one(
                        {"id": payment['order_id']},
                        {"$set": {"payment_status": "paid"}}
                    )
                    
                    # Auto-create shipping label
                    try:
                        order = await db.orders.find_one({"id": payment['order_id']}, {"_id": 0})
                        if order:
                            await create_and_send_label(payment['order_id'], order['telegram_id'], None)
                    except Exception as e:
                        logger.error(f"Failed to create label: {e}")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Oxapay webhook error: {e}")
        return {"status": "error", "message": str(e)}


async def handle_telegram_webhook(request: Request, application):
    """
    Handle Telegram webhook updates
    
    Process incoming updates from Telegram Bot API and pass them to the application.
    
    Args:
        request: FastAPI Request object with Telegram Update
        application: Telegram Application instance
    
    Returns:
        dict: Status response
    """
    try:
        from telegram import Update
        
        # Get update data
        update_data = await request.json()
        update_id = update_data.get('update_id', 'unknown')
        logger.info(f"🔵 WEBHOOK RECEIVED: update_id={update_id}")
        
        # Log message details if present
        if 'message' in update_data:
            msg = update_data['message']
            logger.info(f"🔵 MESSAGE: user={msg.get('from',{}).get('id')}, text={msg.get('text','no text')}")
        
        # Check if application is initialized
        if not application:
            logger.error("🔴 WEBHOOK ERROR: Telegram application not initialized yet")
            return {"ok": True}
        
        logger.info(f"🔵 APPLICATION READY: Processing update {update_id}")
        
        # Process update through application
        try:
            update = Update.de_json(update_data, application.bot)
            logger.info(f"🔵 UPDATE PARSED: Starting process_update for {update_id}")
            await application.process_update(update)
            logger.info(f"🟢 UPDATE PROCESSED SUCCESSFULLY: {update_id}")
            return {"ok": True}
        except Exception as process_error:
            logger.error(f"🔴 PROCESSING ERROR for update {update_id}: {process_error}", exc_info=True)
            return {"ok": True}
            
    except Exception as e:
        logger.error(f"🔴 WEBHOOK ENDPOINT ERROR: {e}", exc_info=True)
        return {"ok": True}
