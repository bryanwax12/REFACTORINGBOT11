"""
Order Flow: Cancellation Handlers
Handles order cancellation and returning to order
"""
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler, with_services


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show cancellation confirmation"""
    from server import (
        SELECT_CARRIER, PAYMENT_METHOD, STATE_NAMES,
        safe_telegram_call, mark_message_as_selected
    )
    
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        # Remove buttons from the message that triggered cancel
        try:
            await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
        except Exception as e:
            logger.warning(f"Could not remove buttons from previous message: {e}")
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Check if we're on shipping rates screen
    last_state = context.user_data.get('last_state')
    
    # Add "Check Data" button only if on shipping rates selection screen
    if last_state == STATE_NAMES[SELECT_CARRIER]:
        keyboard = [
            [InlineKeyboardButton("📋 Проверить данные", callback_data='check_data')],
            [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='return_to_order')],
            [InlineKeyboardButton("✅ Да, отменить заказ", callback_data='confirm_cancel')]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='return_to_order')],
            [InlineKeyboardButton("✅ Да, отменить заказ", callback_data='confirm_cancel')]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "⚠️ Вы уверены, что хотите отменить создание заказа?\n\nВсе введённые данные будут потеряны."
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    # Save last bot message context for button protection
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
    
    # Return the state we were in before cancel
    last_state = context.user_data.get('last_state')
    if isinstance(last_state, str):
        from server import STATE_CONSTANTS, FROM_NAME
        return STATE_CONSTANTS.get(last_state, FROM_NAME)
    return last_state if last_state else PAYMENT_METHOD


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def confirm_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Confirm order cancellation"""
    from server import safe_telegram_call, mark_message_as_selected
    
    
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Clear session and context data
    user_id = update.effective_user.id
    
    # Clear session via service
    await session_service.clear_session(user_id)
    context.user_data.clear()
    logger.info(f"🗑️ Session cleared after order cancellation for user {user_id}")
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(query.message.reply_text("❌ Создание заказа отменено.", reply_markup=reply_markup))
    return ConversationHandler.END


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
@safe_handler(fallback_state=ConversationHandler.END)
async def return_to_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order after cancel button - restore exact screen"""
    from server import FROM_NAME, safe_telegram_call, mark_message_as_selected
    from utils.ui_utils import OrderStepMessages, get_cancel_keyboard
    
    logger.info(f"return_to_order called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Get the state we were in when cancel was pressed
    last_state = context.user_data.get('last_state')
    
    logger.info(f"return_to_order: last_state = {last_state}, type = {type(last_state)}")
    logger.info(f"return_to_order: user_data keys = {list(context.user_data.keys())}")
    
    # If no last_state - just continue
    if last_state is None:
        logger.warning("return_to_order: No last_state found!")
        await safe_telegram_call(query.message.reply_text("Продолжаем оформление заказа..."))
        return FROM_NAME
    
    # If last_state is a number (state constant), we need the string name
    # Check if it's a string (state name) or int (state constant)
    if isinstance(last_state, int):
        # It's a state constant - return it directly
        keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(str(last_state))
        logger.warning(f"return_to_order: last_state is int ({last_state}), should be string!")
        
        # Show next step
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text if message_text else "Продолжаем оформление заказа...",
            reply_markup=reply_markup
        ))
        
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text if message_text else "Продолжаем..."
        
        return last_state
    
    # last_state is a string (state name like "FROM_CITY")
    
    # Special handling for SELECT_CARRIER (shipping rates screen)
    if last_state == 'SELECT_CARRIER':
        logger.info("🔄 Returning to shipping rates screen")
        from handlers.order_flow.rates import display_shipping_rates
        # Show rates again using cached data
        return await display_shipping_rates(update, context)
    
    keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(last_state)
    
    # Special handling for parcel dimension states: check weight to decide keyboard
    from utils.ui_utils import CallbackData, get_standard_size_and_cancel_keyboard
    weight = context.user_data.get('parcel_weight', 0)
    
    if last_state in ['PARCEL_LENGTH', 'PARCEL_WIDTH', 'PARCEL_HEIGHT'] and weight > 10:
        # Weight > 10 lbs, don't show "Use standard sizes" button
        logger.info(f"⚠️ Weight {weight} lbs > 10, hiding standard size button in return_to_order")
        keyboard = get_cancel_keyboard()
    
    # Send message with or without keyboard
    if keyboard:
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=keyboard))
    else:
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
    
    # Save context
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
    
    # Return the state constant - import from server
    from server import STATE_CONSTANTS
    return STATE_CONSTANTS.get(last_state, FROM_NAME)


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    'cancel_order',
    'confirm_cancel_order',
    'return_to_order'
]
