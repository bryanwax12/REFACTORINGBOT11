"""
Order Flow: Entry Points
Handles all entry points for order conversation
"""
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)


from utils.handler_decorators import with_user_session, safe_handler

@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=True, require_session=False)
async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start new order flow
    
    Decorators handle:
    - User session management + blocking check
    - Error handling
    """
    from server import (
        FROM_NAME, STATE_NAMES,
        safe_telegram_call,
        mark_message_as_selected
    )
    from utils.maintenance_check import check_maintenance_mode
    from utils.db_operations import count_user_templates
    from utils.ui_utils import MessageTemplates
    import asyncio
    
    # Get user from context (injected by decorator)
    user = context.user_data['db_user']
    telegram_id = user['telegram_id']
    
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    logger.info(f"📝 User {telegram_id} starting new order flow")
    
    # Session is already handled by @with_user_session decorator
    # Available in context.user_data['session']
    session = context.user_data.get('session', {})
    current_step = session.get('current_step', 'START')
    temp_data = session.get('temp_data', {})
    
    if current_step != 'START' and temp_data:
        logger.info(f"🔄 Resuming session for user {telegram_id} from step {current_step}")
        context.user_data.update(temp_data)
    else:
        logger.info(f"🆕 New session for user {telegram_id}")
    
    # Check if bot is in maintenance mode
    if await check_maintenance_mode(update):
        await safe_telegram_call(send_method(
            MessageTemplates.maintenance_mode(),
            parse_mode='Markdown'
        ))
        return ConversationHandler.END
    
    # Check if user has templates
    templates_count = await count_user_templates(telegram_id)
    
    from utils.ui_utils import get_new_order_choice_keyboard, get_cancel_keyboard, OrderFlowMessages
    
    if templates_count > 0:
        # Show choice: New order or From template
        reply_markup = get_new_order_choice_keyboard()
        
        await safe_telegram_call(send_method(
            OrderFlowMessages.create_order_choice(),
            reply_markup=reply_markup
        ))
        return FROM_NAME  # Waiting for choice
    else:
        # No templates, go straight to new order
        reply_markup = get_cancel_keyboard()
        
        message_text = OrderFlowMessages.new_order_start()
        bot_msg = await safe_telegram_call(send_method(
            message_text,
            reply_markup=reply_markup
        ))
        
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
            context.user_data['last_state'] = STATE_NAMES[FROM_NAME]
        return FROM_NAME


async def start_order_with_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start order creation with pre-loaded template data"""
    from server import PARCEL_WEIGHT, STATE_NAMES, safe_telegram_call, mark_message_as_selected
    
    query = update.callback_query
    
    # Clear topup flag to prevent conflict with parcel weight input
    context.user_data['awaiting_topup_amount'] = False
    
    # Template data already loaded in context.user_data
    # Ask for parcel weight (first thing not in template)
    from utils.ui_utils import get_cancel_keyboard
    reply_markup = get_cancel_keyboard()
    
    template_name = context.user_data.get('template_name', 'шаблон')
    
    message_text = f"""📦 Создание заказа по шаблону \"{template_name}\"

Теперь введите данные посылки:

*Вес посылки в фунтах (lb)*
Например: 5.5"""
    
    # Execute answer and mark selected, then send new message
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Send new message immediately without waiting for mark_message_as_selected
    bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    
    context.user_data['last_state'] = STATE_NAMES[PARCEL_WEIGHT]
    return PARCEL_WEIGHT


async def return_to_payment_after_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return user to payment screen after topping up balance"""
    print("🔵 return_to_payment_after_topup: START")
    from server import (
        PAYMENT_METHOD,
        safe_telegram_call, mark_message_as_selected,
        find_pending_order, delete_pending_order
    )
    from repositories import get_user_repo
    
    logger.info(f"return_to_payment_after_topup called - user_id: {update.effective_user.id}")
    print(f"🔵 User ID: {update.effective_user.id}")
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    print("🔵 Query answered")
    
    telegram_id = query.from_user.id
    
    # Get pending order data from database to load message context
    pending_order = await find_pending_order(telegram_id)
    logger.info(f"Pending order data found: {pending_order is not None}")
    print(f"🔵 Pending order found: {pending_order is not None}")
    
    # Load message context for button protection
    if pending_order:
        context.user_data['last_bot_message_id'] = pending_order.get('topup_success_message_id')
        context.user_data['last_bot_message_text'] = pending_order.get('topup_success_message_text')
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    if not pending_order or not pending_order.get('selected_rate'):
        await safe_telegram_call(query.message.reply_text(
            "❌ Не найдены данные незавершенного заказа.\n\nПожалуйста, создайте новый заказ."
        ))
        return ConversationHandler.END
    
    # Restore order data to context
    context.user_data.update(pending_order)
    
    # Get user balance using Repository Pattern
    user_repo = get_user_repo()
    user_balance = await user_repo.get_balance(telegram_id)
    
    selected_rate = pending_order['selected_rate']
    logger.info(f"Selected rate keys: {selected_rate.keys()}")
    amount = pending_order.get('final_amount', selected_rate.get('amount', selected_rate.get('totalAmount', 0)))
    
    # Handle different rate structures - use correct keys
    carrier_name = selected_rate.get('carrier') or selected_rate.get('carrier_name') or selected_rate.get('carrierName', 'Unknown Carrier')
    service_type = selected_rate.get('service') or selected_rate.get('service_type') or selected_rate.get('serviceType', 'Standard Service')
    
    user_discount = pending_order.get('user_discount', 0)
    discount_text = f"\n🎉 *Ваша скидка:* {user_discount}%" if user_discount > 0 else ""
    
    # Show payment options - only balance payment if sufficient
    keyboard = []
    
    if user_balance >= amount:
        # User has enough balance, only show balance payment option
        keyboard.append([InlineKeyboardButton(f"💰 Оплатить с баланса (${user_balance:.2f})", callback_data='pay_from_balance')])
        
        message_text = f"""💳 *Оплата заказа*

📦 *Выбранный тариф:* {carrier_name} - {service_type}
💰 *Стоимость:* ${amount:.2f}{discount_text}
💵 *Ваш баланс:* ${user_balance:.2f}"""
    else:
        # Not enough balance
        keyboard.append([InlineKeyboardButton("🪙 Оплатить криптовалютой", callback_data='pay_with_crypto')])
        keyboard.append([InlineKeyboardButton("💵 Пополнить баланс", callback_data='topup_for_order')])
        
        message_text = f"""💳 *Выберите способ оплаты*

📦 *Выбранный тариф:* {carrier_name} - {service_type}
💰 *Стоимость:* ${amount:.2f}{discount_text}
💵 *Ваш баланс:* ${user_balance:.2f}

Выберите способ оплаты:"""
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к тарифам", callback_data='back_to_rates')])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
    
    # Delete pending order after restoring
    await delete_pending_order(telegram_id)
    
    return PAYMENT_METHOD


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    'new_order_start',
    'start_order_with_template',
    'return_to_payment_after_topup'
]



async def order_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new order (without template)"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from utils.ui_utils import get_cancel_keyboard, OrderFlowMessages
    from server import FROM_NAME, STATE_NAMES
    import asyncio
    
    logger.info(f"order_new called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Clear topup flag to prevent conflict with order input
    context.user_data['awaiting_topup_amount'] = False
    
    # Mark previous message as selected (remove buttons from choice screen)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderFlowMessages.new_order_start()
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[FROM_NAME]
    
    logger.info("order_new returning FROM_NAME state")
    return FROM_NAME


async def order_from_template_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show template list for order creation"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from utils.ui_utils import get_template_selection_keyboard, OrderFlowMessages
    from server import TEMPLATE_LIST
    from utils.db_operations import find_user_templates
    from telegram.ext import ConversationHandler
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    templates = await find_user_templates(telegram_id, limit=10)
    
    if not templates:
        await safe_telegram_call(query.message.reply_text(OrderFlowMessages.no_templates_error()))
        return ConversationHandler.END
    
    message = OrderFlowMessages.select_template()
    
    for i, template in enumerate(templates, 1):
        message += OrderFlowMessages.template_item(i, template)
    
    reply_markup = get_template_selection_keyboard(templates)
    
    bot_msg = await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown'))
    
    # Save last bot message context for button protection
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
    
    return TEMPLATE_LIST


async def continue_order_after_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Continue order creation after saving template - return to data confirmation"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from handlers.order_flow.confirmation import show_data_confirmation
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Since template was saved from CONFIRM_DATA screen, we have all data including weight/dimensions
    # Return to data confirmation screen
    return await show_data_confirmation(update, context)

