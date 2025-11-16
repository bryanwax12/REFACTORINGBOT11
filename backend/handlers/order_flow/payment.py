"""
Order Flow: Payment Handlers
Handles payment method selection and processing
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler


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
    asyncio.create_task(mark_message_as_selected(update, context))
    
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
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
        message,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
    
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
    from repositories import get_user_repo
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
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
    
    # Get user balance
    telegram_id = query.from_user.id
    user_repo = get_user_repo()
    balance = await user_repo.get_balance(telegram_id)
    
    # Build keyboard
    keyboard = []
    keyboard.append([InlineKeyboardButton("💳 Перейти к оплате", callback_data='proceed_to_payment')])
    keyboard.append([InlineKeyboardButton("🔄 Выбрать другой тариф", callback_data='back_to_rates')])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(query.message.reply_text(
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
    asyncio.create_task(mark_message_as_selected(update, context))
    
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
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    # Handle back to rates
    if query.data == 'back_to_rates':
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        # Return to rate selection - call fetch_shipping_rates again
        return await fetch_shipping_rates(update, context)
    
    # Mark previous message as selected (remove buttons)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    from repositories import get_user_repo
    user_repo = get_user_repo()
    user = await user_repo.find_by_telegram_id(telegram_id)
    data = context.user_data
    selected_rate = data['selected_rate']
    amount = context.user_data.get('final_amount', selected_rate['amount'])  # Use discounted amount
    
    # Get user discount (should be already calculated and stored in context)
    user_discount = context.user_data.get('user_discount', 0)
    discount_amount = context.user_data.get('discount_amount', 0)
    
    try:
        if query.data == 'pay_from_balance':
            # Pay from balance
            from utils.ui_utils import PaymentFlowUI
            if user.get('balance', 0) < amount:
                await safe_telegram_call(query.message.reply_text(PaymentFlowUI.insufficient_balance_error()))
                return ConversationHandler.END
            
            # Create order
            order = await create_order_in_db(user, data, selected_rate, amount, user_discount, discount_amount)
            
            # Try to create shipping label first
            label_created = await create_and_send_label(order['id'], telegram_id, query.message)
            
            if label_created:
                # Only deduct balance if label was created successfully using payment service
                success, new_balance, error = await payment_service.process_balance_payment(
                    telegram_id=telegram_id,
                    amount=amount,
                    order_id=order['id'],
                    db=db,
                    find_user_func=find_user_by_telegram_id,
                    update_order_func=update_order
                )
                
                if not success:
                    logger.error(f"Failed to process payment: {error}")
                    # This shouldn't happen as we checked balance earlier
                    await safe_telegram_call(query.message.reply_text(f"❌ Ошибка обработки платежа: {error}"))
                    return ConversationHandler.END
                
                from utils.ui_utils import PaymentFlowUI
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(query.message.reply_text(
                    PaymentFlowUI.payment_success_balance(amount, new_balance, order.get('order_id')),
                    reply_markup=reply_markup
                ))
                
                # Mark order as completed to prevent stale button interactions
                context.user_data.clear()
                context.user_data['order_completed'] = True
            else:
                # Label creation failed - don't charge user
                from repositories import get_repositories
                repos = get_repositories()
                await repos.orders.update_by_id(
                    order['id'],
                    {"payment_status": "failed", "shipping_status": "failed"}
                )
                
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(query.message.reply_text(
            """❌ Не удалось создать shipping label.
            Оплата не списана. Ваш баланс не изменился.
            Пожалуйста, свяжитесь с администратором.""",
            reply_markup=reply_markup
        ))
                
                # Mark order as completed to prevent stale button interactions
                context.user_data.clear()
                context.user_data['order_completed'] = True
            
        elif query.data == 'pay_with_crypto':
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
                
                await safe_telegram_call(query.message.reply_text(
                    f"""✅ Заказ создан!{order_id_display}

💰 Сумма к оплате: ${amount}
🪙 Криптовалюта: BTC, ETH, USDT, USDC и др.

Нажмите кнопку "Оплатить" для перехода на страницу оплаты.

После успешной оплаты мы автоматически создадим shipping label.""",
                    reply_markup=reply_markup
                ))
            else:
                error_msg = invoice_result.get('error', 'Unknown error')
                await safe_telegram_call(query.message.reply_text(f"❌ Ошибка создания инвойса: {error_msg}"))
        elif query.data == 'top_up_balance':
            # Save order data to database before top-up so user can return to payment after
            pending_order = {
                'telegram_id': telegram_id,
                'selected_rate': data.get('selected_rate'),
                'final_amount': context.user_data.get('final_amount'),
                'user_discount': context.user_data.get('user_discount', 0),
                'discount_amount': context.user_data.get('discount_amount', 0),
                'from_name': data.get('from_name'),
                'from_street': data.get('from_street'),
                'from_street2': data.get('from_street2'),
                'from_city': data.get('from_city'),
                'from_state': data.get('from_state'),
                'from_zip': data.get('from_zip'),
                'from_phone': data.get('from_phone'),
                'to_name': data.get('to_name'),
                'to_street': data.get('to_street'),
                'to_street2': data.get('to_street2'),
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
            await insert_pending_order(pending_order)
            
            context.user_data['last_state'] = STATE_NAMES[TOPUP_AMOUNT]  # Save state for cancel return
            
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        
        message_text = """💵 Пополнение баланса

Введите сумму пополнения в долларах США (USD):

Например: 50

Минимальная сумма: $5
Максимальная сумма: $1000"""
        
        bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
        
        # Save message context for button protection
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        
        return TOPUP_AMOUNT
    
    except Exception as e:
        logger.error(f"Payment error: {e}")
        await safe_telegram_call(query.message.reply_text(f"❌ Ошибка при оплате: {str(e)}"))
        return ConversationHandler.END

