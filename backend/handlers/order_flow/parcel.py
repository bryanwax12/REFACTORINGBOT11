"""
Order Flow: Parcel Information Handlers
Handles collection of parcel dimensions and weight (4 steps)
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.validators import validate_weight, validate_dimension
from utils.decorators import with_typing_indicator


# ============================================================
# PARCEL INFORMATION HANDLERS (4 steps)
# ============================================================

@with_typing_indicator
async def order_parcel_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 15/17: Collect parcel weight"""
    from server import session_manager, PARCEL_WEIGHT, PARCEL_LENGTH, STATE_NAMES
    
    weight_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, weight = validate_weight(weight_str)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_WEIGHT
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_weight'] = weight
    await session_manager.update_session_atomic(user_id, step="PARCEL_LENGTH", data={'parcel_weight': weight})
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.PARCEL_LENGTH
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = PARCEL_LENGTH
    
    return PARCEL_LENGTH


@with_typing_indicator
async def order_parcel_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 16/17: Collect parcel length"""
    from server import session_manager, PARCEL_LENGTH, PARCEL_WIDTH
    
    length_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, length = validate_dimension(length_str, "Длина")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_LENGTH
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_length'] = length
    await session_manager.update_session_atomic(user_id, step="PARCEL_WIDTH", data={'parcel_length': length})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.PARCEL_WIDTH
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = PARCEL_WIDTH
    
    return PARCEL_WIDTH


@with_typing_indicator
async def order_parcel_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 17/17: Collect parcel width"""
    from server import session_manager, PARCEL_WIDTH, PARCEL_HEIGHT
    
    width_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, width = validate_dimension(width_str, "Ширина")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_WIDTH
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_width'] = width
    await session_manager.update_session_atomic(user_id, step="PARCEL_HEIGHT", data={'parcel_width': width})
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.PARCEL_HEIGHT
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = PARCEL_HEIGHT
    
    return PARCEL_HEIGHT


@with_typing_indicator
async def order_parcel_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 18/18: Collect parcel height and trigger rate calculation"""
    from server import session_manager, PARCEL_HEIGHT, fetch_shipping_rates
    
    height_str = update.message.text.strip()
    
    # Validate
    is_valid, error_msg, height = validate_dimension(height_str, "Высота")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return PARCEL_HEIGHT
    
    # Store
    user_id = update.effective_user.id
    context.user_data['parcel_height'] = height
    await session_manager.update_session_atomic(user_id, step="CALCULATING_RATES", data={'parcel_height': height})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # All parcel info collected - proceed to rate calculation
    logger.info(f"✅ All parcel info collected for user {user_id}, fetching rates...")
    
    # Call fetch_shipping_rates which will validate and get rates
    return await fetch_shipping_rates(update, context)
