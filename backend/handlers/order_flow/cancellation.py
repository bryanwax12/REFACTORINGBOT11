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
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Get the state we were in when cancel was pressed
    last_state = context.user_data.get('last_state')
    
    logger.info(f"return_to_order: last_state = {last_state}, type = {type(last_state)}")
    logger.info(f"return_to_order: user_data keys = {list(context.user_data.keys())}")
    
    # If no last_state - try to restore saved state before cancel
    if last_state is None:
        # Try to restore state that was saved before cancel
        saved_state = context.user_data.get('saved_state_before_cancel')
        if saved_state:
            logger.info(f"Restoring saved state: {saved_state}")
            last_state = saved_state
            context.user_data['last_state'] = saved_state
            # Clear saved state
            context.user_data.pop('saved_state_before_cancel', None)
        else:
            logger.warning("return_to_order: No last_state or saved_state found!")
            
            # Check if editing template
            if context.user_data.get('editing_template_from') or context.user_data.get('editing_template_to'):
                template_id = context.user_data.get('editing_template_id')
                if template_id:
                    logger.info(f"Returning to template edit menu for template {template_id}")
                    
                    # Get template from DB
                    from server import db
                    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
                    
                    if template:
                        # Show edit menu
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = [
                            [InlineKeyboardButton("📤 Редактировать адрес отправителя", callback_data=f'template_edit_from_{template_id}')],
                            [InlineKeyboardButton("📥 Редактировать адрес получателя", callback_data=f'template_edit_to_{template_id}')],
                            [InlineKeyboardButton("🔙 Назад к шаблону", callback_data=f'template_view_{template_id}')]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        message = f"""✅ Редактирование отменено.

📝 *Редактирование шаблона*
━━━━━━━━━━━━━━━━━━━━

📁 *Шаблон:* {template.get('name')}

Выберите, что хотите отредактировать:"""
                        
                        await safe_telegram_call(query.message.reply_text(
                            message, 
                            reply_markup=reply_markup, 
                            parse_mode='Markdown'
                        ))
                        return ConversationHandler.END
            
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
    
    keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(last_state)
    
    # Special handling for parcel dimension states: check weight to decide keyboard
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
