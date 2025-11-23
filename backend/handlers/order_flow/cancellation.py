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
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # Check if we're on shipping rates screen
    last_state = context.user_data.get('last_state')
    
    # SAVE last_state for return_to_order to restore
    context.user_data['saved_state_before_cancel'] = last_state
    
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
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_cancel_prompt():
        bot_msg = await safe_telegram_call(query.message.reply_text(
                message_text,
                reply_markup=reply_markup
            ))
        # Save last bot message context for button protection
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
    
    asyncio.create_task(send_cancel_prompt())
    
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
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # Cancel pending order if exists (NEW LOGIC)
    order_id = context.user_data.get('order_id')
    if order_id:
        from server import db
        
        # Find order
        order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
        
        if order and order.get('payment_status') == 'pending':
            # Update status to "cancelled"
            await db.orders.update_one(
                {"order_id": order_id},
                {"$set": {"payment_status": "cancelled", "shipping_status": "cancelled"}}
            )
            logger.info(f"✅ Order {order_id} cancelled")
        elif order and order.get('payment_status') == 'paid':
            logger.warning(f"⚠️ Cannot cancel paid order {order_id}")
        else:
            logger.info(f"ℹ️ Order {order_id} not found or already cancelled")
    
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
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # Get the state we were in when cancel was pressed
    last_state = context.user_data.get('last_state')
    logger.error(f'🔍 DEBUG return_to_order: last_state={last_state}, user_data keys={list(context.user_data.keys())}')
    
    logger.info(f"return_to_order: last_state = {last_state}, type = {type(last_state)}")
    logger.info(f"return_to_order: user_data keys = {list(context.user_data.keys())}")
    
    # If no last_state - try to restore saved state before cancel
    if last_state is None:
        # Try to restore state that was saved before cancel
        saved_state = context.user_data.get('saved_state_before_cancel')
        if saved_state:
            logger.info(f"Restoring saved state: {saved_state}")
            last_state = saved_state
            # Clear saved state
            context.user_data.pop('saved_state_before_cancel', None)
            # Continue to use this state below - don't return here!
        else:
            logger.warning("return_to_order: No last_state or saved_state found!")
            
            # Check if editing template - return to first step of editing
            if context.user_data.get('editing_template_from'):
                logger.info("Returning to first step of FROM address editing")
                from server import FROM_NAME
                from utils.ui_utils import TemplateEditMessages, get_cancel_keyboard
                
                await safe_telegram_call(query.message.reply_text(
                    TemplateEditMessages.FROM_NAME,
                    reply_markup=get_cancel_keyboard()
                ))
                return FROM_NAME
                
            elif context.user_data.get('editing_template_to'):
                logger.info("Returning to first step of TO address editing")
                from server import TO_NAME
                from utils.ui_utils import TemplateEditMessages, get_cancel_keyboard
                
                await safe_telegram_call(query.message.reply_text(
                    TemplateEditMessages.TO_NAME,
                    reply_markup=get_cancel_keyboard()
                ))
                return TO_NAME
            
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
        
        # 🚀 PERFORMANCE: Send message in background
        async def send_continue():
            bot_msg = await safe_telegram_call(query.message.reply_text(
                message_text if message_text else "Продолжаем оформление заказа...",
                reply_markup=reply_markup
            ))
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
                context.user_data['last_bot_message_text'] = message_text if message_text else "Продолжаем..."
        
        asyncio.create_task(send_continue())
        
        return last_state
    
    # last_state is a string (state name like "FROM_CITY")
    
    # Special handling for SELECT_CARRIER (shipping rates screen)
    if last_state == 'SELECT_CARRIER':
        logger.info("🔄 Returning to shipping rates screen")
        from services.shipping_service import display_shipping_rates
        from repositories import get_user_repo
        from server import STATE_NAMES, SELECT_CARRIER
        
        # Check if we have cached rates
        if 'rates' in context.user_data:
            user_repo = get_user_repo()
            return await display_shipping_rates(
                update, 
                context, 
                context.user_data['rates'],
                find_user_by_telegram_id_func=user_repo.find_by_telegram_id,
                safe_telegram_call_func=safe_telegram_call,
                STATE_NAMES=STATE_NAMES,
                SELECT_CARRIER=SELECT_CARRIER
            )
        else:
            # No cached rates, fetch new ones
            from handlers.order_flow.rates import fetch_shipping_rates
            return await fetch_shipping_rates(update, context)
    
    # Check if editing template - use TemplateEditMessages
    editing_template = context.user_data.get('editing_template_from') or context.user_data.get('editing_template_to')
    if editing_template:
        from utils.ui_utils import TemplateEditMessages
        # Map state name to TemplateEditMessages method
        state_to_message = {
            'FROM_NAME': TemplateEditMessages.FROM_NAME,
            'FROM_ADDRESS': TemplateEditMessages.FROM_ADDRESS,
            'FROM_ADDRESS2': TemplateEditMessages.FROM_ADDRESS2,
            'FROM_CITY': TemplateEditMessages.FROM_CITY,
            'FROM_STATE': TemplateEditMessages.FROM_STATE,
            'FROM_ZIP': TemplateEditMessages.FROM_ZIP,
            'FROM_PHONE': TemplateEditMessages.FROM_PHONE,
            'TO_NAME': TemplateEditMessages.TO_NAME,
            'TO_ADDRESS': TemplateEditMessages.TO_ADDRESS,
            'TO_ADDRESS2': TemplateEditMessages.TO_ADDRESS2,
            'TO_CITY': TemplateEditMessages.TO_CITY,
            'TO_STATE': TemplateEditMessages.TO_STATE,
            'TO_ZIP': TemplateEditMessages.TO_ZIP,
            'TO_PHONE': TemplateEditMessages.TO_PHONE,
        }
        message_text = state_to_message.get(last_state, "Продолжаем редактирование...")
        keyboard = None  # Will use cancel keyboard
    else:
        keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(last_state)
    
    # Special handling for parcel dimension states: check weight to decide keyboard
    weight = context.user_data.get('parcel_weight', 0)
    
    if last_state in ['PARCEL_LENGTH', 'PARCEL_WIDTH', 'PARCEL_HEIGHT'] and weight > 10:
        # Weight > 10 lbs, don't show "Use standard sizes" button
        logger.info(f"⚠️ Weight {weight} lbs > 10, hiding standard size button in return_to_order")
        keyboard = get_cancel_keyboard()
    
    # 🚀 PERFORMANCE: Send message in background
    async def send_return_message():
        if keyboard:
            bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=keyboard))
        else:
            reply_markup = get_cancel_keyboard()
            bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        
        # Save context
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
    
    asyncio.create_task(send_return_message())
    
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
