"""
Order Flow: Cancellation Handlers
Handles order cancellation and returning to order
"""
import logging
import asyncio
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup

# ⚡ Performance: Import preloaded keyboards
from utils.ui_utils import PRELOADED_CANCEL_KEYBOARD
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler, with_services

# Export public functions
__all__ = ['cancel_order', 'confirm_cancel_order', 'return_to_order', 'check_order_data']


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Show cancellation confirmation"""
    from server import (
        SELECT_CARRIER, PAYMENT_METHOD, STATE_NAMES,
        safe_telegram_call, mark_message_as_selected, db
    )
    from datetime import datetime, timezone
    
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

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    # Get current state from context.user_data (more reliable than DB lookup)
    user_id = update.effective_user.id
    current_state = context.user_data.get('current_conversation_state')
    
    # If not in context, assume we're at CONFIRM_DATA based on where cancel_order is called from
    if not current_state:
        from server import CONFIRM_DATA
        current_state = CONFIRM_DATA
        logger.info(f"⚠️ State not in context, assuming CONFIRM_DATA")
    
    logger.info(f"✅ Current state: {current_state}")
    
    # Save state to DB for return_to_order to retrieve
    result = await db.user_sessions.update_one(
        {"user_id": user_id},
        {"$set": {
            "session_data.state_before_cancel": current_state,
            "is_active": True,
            "timestamp": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    logger.info(f"📝 Saved state_before_cancel={current_state}, matched={result.matched_count}, modified={result.modified_count}")
    
    # Add "Check Data" button only if on shipping rates selection screen
    if current_state == SELECT_CARRIER:
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
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                message_text,
                reply_markup=reply_markup
            ))
        # Save last bot message context for button protection
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
    
    asyncio.create_task(send_cancel_prompt())
    
    # Return current state (MongoDBPersistence will handle it)
    return current_state if current_state else PAYMENT_METHOD


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

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
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
    
    await safe_telegram_call(update.effective_message.reply_text("❌ Создание заказа отменено.", reply_markup=reply_markup))
    return ConversationHandler.END


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def return_to_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order after cancel button - restore exact screen"""
    from server import FROM_NAME, ORDER_FLOW_STATES, safe_telegram_call, mark_message_as_selected, db
    from utils.ui_utils import OrderStepMessages, get_cancel_keyboard
    from utils.state_validation import validate_and_log_transition
    
    logger.info(f"return_to_order called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    # ✅ 2025 ПРАВИЛЬНЫЙ СПОСОБ: Получить состояние из сессии (которое было сохранено при отмене)
    user_id = update.effective_user.id
    session = await db.user_sessions.find_one(
        {"user_id": user_id, "is_active": True},
        {"session_data.state_before_cancel": 1}
    )
    
    saved_state = None
    if session:
        saved_state = session.get("session_data", {}).get("state_before_cancel")
        logger.info(f"📍 Retrieved state from session: {saved_state}")
        
        # ✅ VALIDATE STATE before returning - prevents confusion!
        saved_state = validate_and_log_transition(
            user_id=user_id,
            saved_state=saved_state,
            valid_states=ORDER_FLOW_STATES,
            handler_name="return_to_order",
            fallback_state=FROM_NAME
        )
        
        # Очистить сохраненное состояние
        await db.user_sessions.update_one(
            {"user_id": user_id, "is_active": True},
            {"$unset": {"session_data.state_before_cancel": ""}}
        )
    
    if not saved_state:
        logger.warning("⚠️ No saved state found - checking for template editing")
        
        # Check if editing template - return to first step of editing
        if context.user_data.get('editing_template_from'):
            logger.info("Returning to first step of FROM address editing")
            from server import FROM_NAME
            from utils.ui_utils import TemplateEditMessages
            
            await safe_telegram_call(update.effective_message.reply_text(
                TemplateEditMessages.FROM_NAME,
                reply_markup=PRELOADED_CANCEL_KEYBOARD  # ⚡ Performance
            ))
            return FROM_NAME
            
        elif context.user_data.get('editing_template_to'):
            logger.info("Returning to first step of TO address editing")
            from server import TO_NAME
            from utils.ui_utils import TemplateEditMessages
            
            await safe_telegram_call(update.effective_message.reply_text(
                TemplateEditMessages.TO_NAME,
                reply_markup=PRELOADED_CANCEL_KEYBOARD  # ⚡ Performance
            ))
            return TO_NAME
        
        # Try to detect state from context.user_data
        logger.warning("⚠️ Trying to detect state from context.user_data")
        
        # Check what data we have to determine the state
        if context.user_data.get('selected_carrier_id'):
            # User was at payment method selection
            logger.info("🔄 Detected PAYMENT_METHOD state from context")
            from server import PAYMENT_METHOD
            from handlers.order_flow.payment import ask_payment_method
            return await ask_payment_method(update, context)
        
        elif context.user_data.get('rates'):
            # User was at carrier selection
            logger.info("🔄 Detected SELECT_CARRIER state from context")
            from server import SELECT_CARRIER
            from services.shipping_service import display_shipping_rates
            from repositories import get_user_repo
            from server import STATE_NAMES
            
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
        
        elif context.user_data.get('parcel_dimensions'):
            # User was at parcel step or later, refetch rates
            logger.info("🔄 Refetching shipping rates")
            from handlers.order_flow.rates import fetch_shipping_rates
            return await fetch_shipping_rates(update, context)
        
        logger.error("❌ No state found - returning to FROM_NAME")
        await safe_telegram_call(update.effective_message.reply_text(
            "Продолжаем оформление заказа...",
            reply_markup=PRELOADED_CANCEL_KEYBOARD  # ⚡ Performance
        ))
        return FROM_NAME
    
    # saved_state is an integer (state constant from ConversationHandler)
    logger.info(f"✅ Returning to saved state: {saved_state}")
    
    # Special handling for SELECT_CARRIER (shipping rates screen)
    from server import SELECT_CARRIER, PAYMENT_METHOD, TEMPLATE_NAME, CONFIRM_DATA
    
    # If user was saving template or at confirmation screen, return to confirmation
    if saved_state == TEMPLATE_NAME or saved_state == CONFIRM_DATA:
        logger.info("🔄 Returning to order confirmation screen")
        from handlers.order_flow.confirmation import show_data_confirmation
        return await show_data_confirmation(update, context)
    
    if saved_state == SELECT_CARRIER:
        logger.info("🔄 Returning to shipping rates screen")
        from services.shipping_service import display_shipping_rates
        from repositories import get_user_repo
        from server import STATE_NAMES
        
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
    
    elif saved_state == PAYMENT_METHOD:
        logger.info("🔄 Returning to payment method screen")
        from handlers.order_flow.payment import ask_payment_method
        return await ask_payment_method(update, context)
    
    # For other states, just show continuation message and return the state
    # MongoDBPersistence will restore the proper handler
    await safe_telegram_call(update.effective_message.reply_text(
        "Продолжаем оформление заказа...",
        reply_markup=PRELOADED_CANCEL_KEYBOARD  # ⚡ Performance
    ))
    
    return saved_state


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    'cancel_order',
    'confirm_cancel_order',
    'return_to_order'
]
