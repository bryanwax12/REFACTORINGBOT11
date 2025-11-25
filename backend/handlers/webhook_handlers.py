"""
Webhook handlers for external services
Handles payment webhooks from Oxapay and Telegram bot updates
"""
import logging
from fastapi import Request
from datetime import datetime, timezone

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
        paid_amount_raw = body.get('paidAmount') or body.get('paid_amount') or body.get('amount', 0)  # Actual paid amount
        # Convert to float (Oxapay may send as string)
        paid_amount = float(paid_amount_raw) if paid_amount_raw else 0.0
        
        # Try to find payment by invoice_id (could be string or int in DB)
        logger.info(f"🔍 Looking for payment with track_id: {track_id}")
        
        # CRITICAL: Oxapay может отправлять status в разных регистрах (Paid, paid, PAID)
        if status and status.lower() == 'paid':
            # Search by both invoice_id and track_id to support different payment flows
            payment = await db.payments.find_one({
                "$or": [
                    {"invoice_id": track_id},
                    {"track_id": track_id}
                ]
            }, {"_id": 0})
            
            if not payment and track_id:
                # Try as integer if string search failed
                try:
                    track_id_int = int(track_id)
                    payment = await db.payments.find_one({
                        "$or": [
                            {"invoice_id": track_id_int},
                            {"track_id": track_id_int}
                        ]
                    }, {"_id": 0})
                    logger.info(f"🔄 Retried with int type: {track_id_int}")
                except (ValueError, TypeError):
                    pass
            
            logger.info(f"💾 Payment found: {payment is not None}")
            logger.info(f"🔍 Payment object: {payment}")
            if payment:
                logger.info("✅ Inside 'if payment' block")
                
                # CRITICAL: Check if payment was already processed (duplicate webhook protection)
                current_status = payment.get('status')
                if current_status == 'paid':
                    logger.warning(f"⚠️ DUPLICATE WEBHOOK DETECTED: Payment {track_id} already processed with status 'paid'. Ignoring.")
                    return {"status": "ok", "message": "Payment already processed"}
                
                # Update payment status (use same invoice_id format that was used to find it)
                invoice_id_for_update = payment.get('invoice_id')  # Use actual value from DB
                logger.info(f"📝 invoice_id_for_update: {invoice_id_for_update}")
                await db.payments.update_one(
                    {"invoice_id": invoice_id_for_update},
                    {"$set": {"status": "paid", "paid_amount": paid_amount}}
                )
                logger.info(f"✅ Payment status updated to 'paid' for invoice_id={invoice_id_for_update}")
                
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
                    logger.info(f"📤 Attempting to send notification. bot_instance exists: {bot_instance is not None}")
                    logger.info(f"📤 Attempting to send notification. bot_instance exists: {bot_instance is not None}")
                    if bot_instance:
                        logger.info(f"✅ Bot instance available, sending notification to {telegram_id}")
                        logger.info(f"✅ Bot instance available, sending notification to {telegram_id}")
                        
                        try:
                            from utils.ui_utils import MessageTemplates, get_payment_success_keyboard
                            logger.info("📦 Imported MessageTemplates and keyboard")
                            
                            user = await find_user_by_telegram_id(telegram_id)
                            logger.info(f"👤 Found user: {user is not None}")
                            if not user:
                                logger.error(f"❌ User not found for telegram_id={telegram_id}")
                                return
                            
                            new_balance = user.get('balance', 0)
                            logger.info(f"💰 User balance: ${new_balance}")
                            logger.info(f"💰 User balance: ${new_balance}")
                            
                            pending_order = await find_pending_order(telegram_id)
                            logger.info(f"🔍 Pending order search: telegram_id={telegram_id}, found={pending_order is not None}")
                            if pending_order:
                                logger.info(f"📦 Pending order details: telegram_id={pending_order.get('telegram_id')}, has_selected_rate={pending_order.get('selected_rate') is not None}")
                            
                            order_amount = 0.0
                            has_pending_order = False
                            
                            if pending_order and pending_order.get('selected_rate'):
                                has_pending_order = True
                                order_amount = pending_order.get('final_amount', pending_order['selected_rate']['amount'])
                                logger.info(f"✅ Has pending order! amount=${order_amount}")
                            
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
                            logger.info("⌨️ Keyboard created")
                            
                            logger.info(f"📨 Sending message to chat_id={telegram_id}")
                            logger.info("📨 About to call bot_instance.send_message...")
                            bot_msg = await safe_telegram_call(bot_instance.send_message(
                                chat_id=telegram_id,
                                text=message_text,
                                reply_markup=reply_markup,
                                parse_mode='Markdown'
                            ))
                            
                            if bot_msg:
                                logger.info(f"✅ Message sent! message_id={bot_msg.message_id}")
                                logger.info(f"✅ Notification sent successfully! message_id={bot_msg.message_id}")
                            else:
                                logger.info("❌ bot_msg is None")
                                logger.error("❌ Failed to send notification - bot_msg is None")
                        
                        except Exception as notify_ex:
                            logger.error(f"❌ Exception while sending notification: {notify_ex}", exc_info=True)
                            logger.info(f"❌ Exception: {notify_ex}")
                        
                        # Save message context in pending_orders for button protection
                        if bot_msg:
                            await db.pending_orders.update_one(
                                {"telegram_id": telegram_id},
                                {"$set": {
                                    "topup_success_message_id": bot_msg.message_id,
                                    "topup_success_message_text": message_text
                                }}
                            )
                        
                        # Notify admin about balance top-up
                        try:
                            from server import ADMIN_TELEGRAM_ID
                            if ADMIN_TELEGRAM_ID and bot_instance:
                                user_display = f"{user.get('first_name', 'Unknown')}"
                                if user.get('username'):
                                    user_display += f" (@{user.get('username')})"
                                else:
                                    user_display += f" (ID: {telegram_id})"
                                
                                admin_notification = f"""💰 *Пополнение баланса*

👤 *Пользователь:* {user_display}

💵 *Сумма:* ${actual_amount:.2f}
💳 *Новый баланс:* ${new_balance:.2f}

🔖 *Track ID:* `{track_id}`
🕐 *Время:* {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}"""
                                
                                await safe_telegram_call(bot_instance.send_message(
                                    chat_id=int(ADMIN_TELEGRAM_ID),
                                    text=admin_notification,
                                    parse_mode='Markdown'
                                ))
                                logger.info("✅ Admin notified about balance top-up")
                        except Exception as admin_notify_error:
                            logger.error(f"Failed to notify admin about top-up: {admin_notify_error}")
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
                            label_created = await create_and_send_label(payment['order_id'], order['telegram_id'], None)
                            
                            if label_created:
                                # Get user balance after payment
                                from repositories import get_user_repo
                                user_repo = get_user_repo()
                                new_balance = await user_repo.get_balance(order['telegram_id'])
                                
                                # Send balance info to user
                                from utils.ui_utils import PaymentFlowUI
                                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                
                                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                
                                await safe_telegram_call(bot_instance.send_message(
                                    chat_id=order['telegram_id'],
                                    text=PaymentFlowUI.payment_success_balance(order['amount'], new_balance, payment['order_id']),
                                    reply_markup=reply_markup
                                ))
                                
                                # Send AI-generated thank you message
                                try:
                                    from utils.telegram_utils import generate_thank_you_message
                                    thank_you_msg = await generate_thank_you_message()
                                    await safe_telegram_call(bot_instance.send_message(
                                        chat_id=order['telegram_id'],
                                        text=thank_you_msg
                                    ))
                                    logger.info(f"AI thank you message sent to user {order['telegram_id']}")
                                except Exception as e:
                                    logger.error(f"Error generating/sending thank you message: {e}")
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
