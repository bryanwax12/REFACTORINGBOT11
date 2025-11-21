"""
Order Flow: Parcel Information Handlers
Handles collection of parcel dimensions and weight (4 steps)
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.validators import validate_weight, validate_dimension
from utils.handler_decorators import with_user_session, safe_handler, with_typing_action, with_services
from utils.debounce import debounce_input
from telegram.ext import ConversationHandler


# ============================================================
# PARCEL INFORMATION HANDLERS (4 steps)
# ============================================================

@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_parcel_weight(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 15/17: Collect parcel weight"""
    from server import PARCEL_WEIGHT, PARCEL_LENGTH, STATE_NAMES
    
    logger.info("🟢 order_parcel_weight HANDLER INVOKED")
    logger.info(f"   User ID: {update.effective_user.id}")
    logger.info(f"   Message text: {update.message.text}")
    logger.info(f"   context.user_data keys: {list(context.user_data.keys())}")
    logger.info(f"   Has template data? from_name={context.user_data.get('from_name')}, to_name={context.user_data.get('to_name')}")
    
    weight_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, weight = validate_weight(weight_str)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_WEIGHT
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_weight'] = weight
    
    # Update session via repository
    # Session service injected via decorator
    await session_service.save_order_field(user_id, 'parcel_weight', weight)
    await session_service.update_session_step(user_id, step="PARCEL_LENGTH")
    
    from utils.ui_utils import get_standard_size_and_cancel_keyboard, get_cancel_keyboard, OrderStepMessages, CallbackData
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # If weight > 10 lbs, don't show "Use standard sizes" button (package is too heavy for 10x10x10)
    if weight > 10:
        reply_markup = get_cancel_keyboard()
        logger.info(f"⚠️ Weight {weight} lbs > 10, hiding standard size button")
    else:
        reply_markup = get_standard_size_and_cancel_keyboard(CallbackData.SKIP_PARCEL_DIMENSIONS)
    
    message_text = OrderStepMessages.PARCEL_LENGTH
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        # Save CURRENT step (PARCEL_LENGTH) so cancel can return here
        context.user_data['last_state'] = STATE_NAMES[PARCEL_LENGTH]
    
    return PARCEL_LENGTH


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_parcel_length(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 16/17: Collect parcel length"""
    from server import PARCEL_LENGTH, PARCEL_WIDTH, STATE_NAMES
    
    
    
    length_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, length = validate_dimension(length_str, "Длина")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_LENGTH
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_length'] = length
    
    # Update session via repository
    # Session service injected via decorator
    await session_service.save_order_field(user_id, 'parcel_length', length)
    await session_service.update_session_step(user_id, step="PARCEL_WIDTH")
    
    asyncio.create_task(mark_message_as_selected(update, context))
    from utils.ui_utils import get_standard_size_and_cancel_keyboard, get_cancel_keyboard, OrderStepMessages, CallbackData
    
    # Check weight to decide if we show "Use standard sizes" button
    weight = context.user_data.get('parcel_weight', 0)
    if weight > 10:
        reply_markup = get_cancel_keyboard()
        logger.info(f"⚠️ Weight {weight} lbs > 10, hiding standard size button")
    else:
        reply_markup = get_standard_size_and_cancel_keyboard(CallbackData.SKIP_PARCEL_WIDTH_HEIGHT)
    
    message_text = OrderStepMessages.PARCEL_WIDTH
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[PARCEL_WIDTH]
    
    return PARCEL_WIDTH


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_parcel_width(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 17/17: Collect parcel width"""
    from server import PARCEL_WIDTH, PARCEL_HEIGHT, STATE_NAMES
    
    
    
    width_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, width = validate_dimension(width_str, "Ширина")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_WIDTH
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_width'] = width
    
    # Update session via repository
    # Session service injected via decorator
    await session_service.save_order_field(user_id, 'parcel_width', width)
    await session_service.update_session_step(user_id, step="PARCEL_HEIGHT")
    
    from utils.ui_utils import get_standard_size_and_cancel_keyboard, get_cancel_keyboard, OrderStepMessages, CallbackData
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Check weight to decide if we show "Use standard sizes" button
    weight = context.user_data.get('parcel_weight', 0)
    if weight > 10:
        reply_markup = get_cancel_keyboard()
        logger.info(f"⚠️ Weight {weight} lbs > 10, hiding standard size button")
    else:
        reply_markup = get_standard_size_and_cancel_keyboard(CallbackData.SKIP_PARCEL_HEIGHT)
    
    message_text = OrderStepMessages.PARCEL_HEIGHT
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[PARCEL_HEIGHT]
    
    return PARCEL_HEIGHT


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_parcel_height(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 18/17: Collect parcel height and calculate shipping rates"""
    from server import PARCEL_HEIGHT
    
    
    
    height_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, height = validate_dimension(height_str, "Высота")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_HEIGHT
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_height'] = height
    
    # Update session via repository
    # Session service injected via decorator
    await session_service.save_order_field(user_id, 'parcel_height', height)
    await session_service.update_session_step(user_id, step="CALCULATING_RATES")
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    from handlers.order_flow.confirmation import show_data_confirmation
    
    # Показываем экран подтверждения данных перед получением тарифов
    return await show_data_confirmation(update, context)
