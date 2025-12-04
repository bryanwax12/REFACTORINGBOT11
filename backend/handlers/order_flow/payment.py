"""
Order Flow: Payment Handlers
Handles payment method selection and processing
"""
import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler
from handlers.common_handlers import check_stale_interaction
from server import safe_telegram_call, mark_message_as_selected


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show payment method selection screen
    
    This function is typically called after carrier selection.
    Shows options: Pay from balance, Pay with crypto, Top-up balance
    """
    from server import (
        safe_telegram_call,
        PAYMENT_METHOD,
        mark_message_as_selected
    )
    from repositories import get_user_repo
    from utils.ui_utils import PaymentFlowUI
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    telegram_id = query.from_user.id
    
    # Get balance using Repository Pattern
    user_repo = get_user_repo()
    balance = await user_repo.get_balance(telegram_id)
    
    # Get order amount
    selected_rate = context.user_data.get('selected_rate', {})
    amount = context.user_data.get('final_amount', selected_rate.get('amount', 0))
    
    # Build message
    message = PaymentFlowUI.payment_method_selection(amount, balance)
    
    # Build keyboard
    keyboard = []
    
    if balance >= amount:
        keyboard.append([InlineKeyboardButton(
            f"💳 Оплатить с баланса (${balance:.2f})",
            callback_data='pay_from_balance'
        )])
    else:
        deficit = amount - balance
        keyboard.append([InlineKeyboardButton(
            f"➕ Пополнить баланс (не хватает ${deficit:.2f})",
            callback_data='topup_for_order'
        )])
    
    keyboard.append([InlineKeyboardButton("📋 Информация о заказе", callback_data='order_summary')])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_message():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message,
            reply_markup=reply_markup
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message
    
    asyncio.create_task(send_message())
    
    return PAYMENT_METHOD


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_pay_from_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment from user balance"""
    # Call process_payment from this module
    return await process_payment(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_order_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle order summary button"""
    return await show_order_summary(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_proceed_to_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle proceed to payment button - return to payment screen"""
    return await show_payment_methods(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_topup_for_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle top-up balance before payment"""
    from server import my_balance_command
    
    # Save that we're in order flow for return
    context.user_data['return_to_order_after_topup'] = True
    
    return await my_balance_command(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def show_order_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show order summary with selected rate details"""
    from server import safe_telegram_call, PAYMENT_METHOD
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Remove buttons from the previous message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.warning(f"Could not remove buttons from previous message: {e}")
    
    # Get order data
    data = context.user_data
    selected_carrier = data.get('selected_carrier', 'Unknown')
    selected_service = data.get('selected_service', 'Standard')
    amount = data.get('final_amount', 0)
    
    # Format addresses with proper field names
    from_name = data.get('from_name', 'N/A')
    from_street = data.get('from_address', data.get('from_street', 'N/A'))
    from_street2 = data.get('from_address2', data.get('from_street2', ''))
    from_city = data.get('from_city', 'N/A')
    from_state = data.get('from_state', 'N/A')
    from_zip = data.get('from_zip', 'N/A')
    from_phone = data.get('from_phone', '')
    
    to_name = data.get('to_name', 'N/A')
    to_street = data.get('to_address', data.get('to_street', 'N/A'))
    to_street2 = data.get('to_address2', data.get('to_street2', ''))
    to_city = data.get('to_city', 'N/A')
    to_state = data.get('to_state', 'N/A')
    to_zip = data.get('to_zip', 'N/A')
    to_phone = data.get('to_phone', '')
    
    # Parcel details
    weight = data.get('parcel_weight', 0)
    length = data.get('parcel_length', '')
    width = data.get('parcel_width', '')
    height = data.get('parcel_height', '')
    
    # Build summary message
    summary = f"""📦 <b>Информация о заказе</b>
{'='*30}

<b>📍 Отправитель:</b>
👤 {from_name}
📍 {from_street}"""
    
    if from_street2 and from_street2.strip():
        summary += f"\n🏢 {from_street2}"
    
    summary += f"\n🏙️ {from_city}, {from_state} {from_zip}"
    
    if from_phone:
        summary += f"\n📱 {from_phone}"
    
    summary += f"""

<b>📍 Получатель:</b>
👤 {to_name}
📍 {to_street}"""
    
    if to_street2 and to_street2.strip():
        summary += f"\n🏢 {to_street2}"
    
    summary += f"\n🏙️ {to_city}, {to_state} {to_zip}"
    
    if to_phone:
        summary += f"\n📱 {to_phone}"
    
    summary += f"""

<b>📦 Посылка:</b>
⚖️ Вес: {weight} lbs"""
    
    if length and width and height:
        summary += f"\n📐 Размеры: {length}\" × {width}\" × {height}\""
    
    summary += f"""

<b>🚚 Выбранный тариф:</b>
{selected_carrier} - {selected_service}
💰 Стоимость: ${amount:.2f}

{'='*30}"""
    
    # Build keyboard
    keyboard = []
    keyboard.append([InlineKeyboardButton("💳 Перейти к оплате", callback_data='proceed_to_payment')])
    keyboard.append([InlineKeyboardButton("🔄 Выбрать другой тариф", callback_data='back_to_rates')])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(update.effective_message.reply_text(
        summary,
        reply_markup=reply_markup,
        parse_mode='HTML'
    ))
    
    return PAYMENT_METHOD


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_back_to_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to rates button - return to rate selection"""
    from server import fetch_shipping_rates, mark_message_as_selected
    import asyncio
    
    # Mark previous message as selected (remove buttons)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    # Return to rate selection
    return await fetch_shipping_rates(update, context)


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    'show_payment_methods',
    'show_order_summary',
    'handle_pay_from_balance',
    'handle_order_summary',
    'handle_proceed_to_payment',
    'handle_topup_for_order',
    'handle_back_to_rates',
    'process_payment'
]
async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Check for stale interaction
    if await check_stale_interaction(query, context):
        return ConversationHandler.END
    
    await safe_telegram_call(query.answer())
    
    if query.data == 'cancel_order':
        from handlers.order_flow.cancellation import cancel_order
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        from handlers.order_flow.cancellation import confirm_cancel_order
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        from handlers.order_flow.cancellation import return_to_order
        return await return_to_order(update, context)
    
    # Handle back to rates
    if query.data == 'back_to_rates':
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

        old_prompt_text = context.user_data.get('last_bot_message_text', '')

        asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
        # Return to rate selection - call fetch_shipping_rates again
        from handlers.order_flow.rates import fetch_shipping_rates
        return await fetch_shipping_rates(update, context)
    
    # Mark previous message as selected (remove buttons)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    telegram_id = query.from_user.id
    from repositories import get_user_repo
    user_repo = get_user_repo()
    data = context.user_data
    selected_rate = data['selected_rate']
    amount = context.user_data.get('final_amount', selected_rate['amount'])  # Use discounted amount
    
    # Get user discount (should be already calculated and stored in context)
    user_discount = context.user_data.get('user_discount', 0)
    discount_amount = context.user_data.get('discount_amount', 0)
    
    try:
        if query.data == 'pay_from_balance':
            # Import required functions
            from server import create_and_send_label, db
            from services.service_factory import ServiceFactory
            from utils.ui_utils import PaymentFlowUI
            
            # Get payment service
            service_factory = ServiceFactory(db)
            payment_service = service_factory.get_payment_service()
            
            # ✅ OPTIMIZATION: Fetch user and order in parallel
            order_id = context.user_data.get('order_id')
            
            if order_id:
                # Fetch user and order in parallel
                user, order = await asyncio.gather(
                    user_repo.find_by_telegram_id(telegram_id),
                    db.orders.find_one({"order_id": order_id})
                )
            else:
                # Need to find order first
                logger.warning("⚠️ order_id not found in context, searching in DB...")
                user, order = await asyncio.gather(
                    user_repo.find_by_telegram_id(telegram_id),
                    db.orders.find_one(
                        {"telegram_id": telegram_id, "payment_status": "pending"},
                        sort=[("created_at", -1)]
                    )
                )
                
                if order:
                    order_id = order.get('order_id')
                    context.user_data['order_id'] = order_id
                    logger.info(f"✅ Restored order_id from DB: {order_id}")
                else:
                    logger.error("❌ No pending orders found in database!")
                    await safe_telegram_call(update.effective_message.reply_text(
                        "❌ Ошибка: заказ не найден. Пожалуйста, начните заново."
                    ))
                    return ConversationHandler.END
            
            if user.get('balance', 0) < amount:
                await safe_telegram_call(update.effective_message.reply_text(PaymentFlowUI.insufficient_balance_error()))
                return ConversationHandler.END
            
            if not order:
                
                if not order:
                    logger.error(f"❌ Order {order_id} not found in database!")
                    await safe_telegram_call(update.effective_message.reply_text(
                        "❌ Ошибка: заказ не найден в базе данных."
                    ))
                    return ConversationHandler.END
            
            # Check order status - must be "pending"
            order_status = order.get('payment_status', 'pending')
            if order_status == 'paid':
                logger.warning(f"⚠️ Order {order_id} already paid!")
                await safe_telegram_call(update.effective_message.reply_text(
                    "✅ Этот заказ уже оплачен!"
                ))
                return ConversationHandler.END
            
            logger.info(f"✅ Found pending order {order_id}, proceeding with payment")
            
            # Show progress indicator while creating label
            progress_msg = await safe_telegram_call(update.effective_message.reply_text(
                "⏳ Создаем shipping label... 0 сек",
                parse_mode='Markdown'
            ))
            
            # Start progress updater in background
            progress_task = None
            if progress_msg:
                async def update_progress():
                    seconds = 0
                    try:
                        while True:
                            await asyncio.sleep(1.0)  # Sleep 1 second
                            seconds += 1
                            await safe_telegram_call(progress_msg.edit_text(
                                f"⏳ Создаем shipping label... {seconds} сек",
                                parse_mode='Markdown'
                            ))
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.debug(f"Progress update error: {e}")
                
                progress_task = asyncio.create_task(update_progress())
            
            # Try to create shipping label (pass order_id string, not MongoDB _id)
            label_created = await create_and_send_label(order['order_id'], telegram_id, query.message)
            
            # Stop progress indicator and delete message
            if progress_task:
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
            
            if progress_msg:
                try:
                    await safe_telegram_call(progress_msg.delete())
                except Exception as e:
                    logger.debug(f"Failed to delete progress message: {e}")
            
            if label_created:
                # Only deduct balance if label was created successfully using payment service
                success, error = await payment_service.process_balance_payment(
                    telegram_id=telegram_id,
                    order_id=order['order_id'],
                    amount=amount
                )
                
                if not success:
                    logger.error(f"Failed to process payment: {error}")
                    # This shouldn't happen as we checked balance earlier
                    await safe_telegram_call(update.effective_message.reply_text(f"❌ Ошибка обработки платежа: {error}"))
                    return ConversationHandler.END
                
                # Update order status to "paid" (NEW LOGIC)
                await db.orders.update_one(
                    {"order_id": order_id},
                    {"$set": {"payment_status": "paid"}}
                )
                logger.info(f"✅ Order {order_id} status updated to 'paid'")
                
                # Get new balance after payment
                from repositories import get_user_repo
                user_repo = get_user_repo()
                new_balance = await user_repo.get_balance(telegram_id)
                
                from utils.ui_utils import PaymentFlowUI
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(update.effective_message.reply_text(
                    PaymentFlowUI.payment_success_balance(amount, new_balance, order.get('order_id')),
                    reply_markup=reply_markup
                ))
                
                # Send AI-generated thank you message
                try:
                    from utils.telegram_utils import generate_thank_you_message
                    thank_you_msg = await generate_thank_you_message()
                    await safe_telegram_call(update.effective_message.reply_text(thank_you_msg))
                    logger.info(f"AI thank you message sent to user {telegram_id}")
                except Exception as e:
                    logger.error(f"Error generating/sending thank you message: {e}")
                    # Don't fail the whole flow if AI message fails
                
                # Mark order as completed to prevent stale button interactions
                context.user_data.clear()
                context.user_data['order_completed'] = True
            else:
                # Label creation failed - don't charge user
                from repositories import get_repositories
                repos = get_repositories()
                await repos.orders.update_one(
                    {"order_id": order['order_id']},
                    {"$set": {"payment_status": "failed", "shipping_status": "failed"}}
                )
                
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(update.effective_message.reply_text(
            """❌ Не удалось создать shipping label.
            Оплата не списана. Ваш баланс не изменился.
            Пожалуйста, свяжитесь с администратором.""",
            reply_markup=reply_markup
        ))
                
                # Mark order as completed to prevent stale button interactions
                context.user_data.clear()
                context.user_data['order_completed'] = True
            
        elif query.data == 'pay_with_crypto':
            # Import required functions
            from server import create_order_in_db, Payment, session_manager
            from services.api_services import create_oxapay_invoice
            from utils.db_operations import insert_payment
            
            # Create order
            order = await create_order_in_db(user, data, selected_rate, amount, user_discount, discount_amount)
            
            # Create Oxapay invoice
            invoice_result = await create_oxapay_invoice(
                amount=amount,
                order_id=order['id'],
                description=f"Shipping Label - Order {order['id'][:8]}"
            )
            
            if invoice_result.get('success'):
                track_id = invoice_result['trackId']
                pay_link = invoice_result['payLink']
                
                payment = Payment(
                    order_id=order['id'],
                    amount=amount,
                    invoice_id=track_id,
                    pay_url=pay_link
                )
                payment_dict = payment.model_dump()
                payment_dict['created_at'] = payment_dict['created_at'].isoformat()
                payment_dict['track_id'] = track_id  # Store track_id for webhook lookup
                await insert_payment(payment_dict)
                
                keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)],
                           [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Get order_id from session for display
                from utils.order_utils import format_order_id_for_display
                session = await session_manager.get_session(telegram_id)
                order_id_display = ""
                if session and session.get('order_id'):
                    display_id = format_order_id_for_display(session['order_id'])
                    order_id_display = f"\n📦 Номер заказа: #{display_id}\n"
                
                await safe_telegram_call(update.effective_message.reply_text(
                    f"""✅ Заказ создан!{order_id_display}

💰 Сумма к оплате: ${amount}
🪙 Криптовалюта: BTC, ETH, USDT, USDC и др.

Нажмите кнопку "Оплатить" для перехода на страницу оплаты.

После успешной оплаты мы автоматически создадим shipping label.""",
                    reply_markup=reply_markup
                ))
            else:
                error_msg = invoice_result.get('error', 'Unknown error')
                await safe_telegram_call(update.effective_message.reply_text(f"❌ Ошибка создания инвойса: {error_msg}"))
        elif query.data == 'topup_for_order':
            # Import db and insert function
            from server import db
            from utils.db_operations import insert_pending_order
            
            # Save order data to database before top-up so user can return to payment after
            pending_order = {
                'telegram_id': telegram_id,
                'selected_rate': data.get('selected_rate'),
                'final_amount': context.user_data.get('final_amount'),
                'user_discount': context.user_data.get('user_discount', 0),
                'discount_amount': context.user_data.get('discount_amount', 0),
                'from_name': data.get('from_name'),
                'from_address': data.get('from_address'),  # Use 'from_address' not 'from_street'
                'from_address2': data.get('from_address2'),
                'from_city': data.get('from_city'),
                'from_state': data.get('from_state'),
                'from_zip': data.get('from_zip'),
                'from_phone': data.get('from_phone'),
                'to_name': data.get('to_name'),
                'to_address': data.get('to_address'),  # Use 'to_address' not 'to_street'
                'to_address2': data.get('to_address2'),
                'to_city': data.get('to_city'),
                'to_state': data.get('to_state'),
                'to_zip': data.get('to_zip'),
                'to_phone': data.get('to_phone'),
                'parcel_weight': data.get('parcel_weight'),
                'parcel_length': data.get('parcel_length'),
                'parcel_width': data.get('parcel_width'),
                'parcel_height': data.get('parcel_height'),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Delete any existing pending order for this user
            await db.pending_orders.delete_many({"telegram_id": telegram_id})
            # Save new pending order
            logger.info(f"💾 Saving pending order: telegram_id={telegram_id}, has_selected_rate={pending_order.get('selected_rate') is not None}, final_amount={pending_order.get('final_amount')}")
            await insert_pending_order(pending_order)
            logger.info("✅ Pending order saved!")
            
            from server import TOPUP_AMOUNT, STATE_NAMES
            
            from utils.ui_utils import get_cancel_keyboard
            reply_markup = get_cancel_keyboard()
            
            message_text = """💵 Пополнение баланса

Введите сумму пополнения в долларах США (USD):

Например: 50

Минимальная сумма: $10
Максимальная сумма: $1000"""
            
            # 🚀 PERFORMANCE: Send message in background
            async def send_topup_prompt():
                bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                    message_text,
                    reply_markup=reply_markup
                ))
                # Save message context for button protection
                if bot_msg:
                    context.user_data['last_bot_message_id'] = bot_msg.message_id
                    context.user_data['last_bot_message_text'] = message_text
            
            asyncio.create_task(send_topup_prompt())
            
            from server import TOPUP_AMOUNT
            return TOPUP_AMOUNT
    
    except Exception as e:
        logger.error(f"Payment error: {e}")
        await safe_telegram_call(update.effective_message.reply_text(f"❌ Ошибка при оплате: {str(e)}"))
        return ConversationHandler.END

