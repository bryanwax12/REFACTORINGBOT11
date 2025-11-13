"""
Order Flow: TO Address Handlers
Handles collection of recipient (TO) address information through 7 steps
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.validators import (
    validate_name, validate_address, validate_city,
    validate_state, validate_zip, validate_phone
)


# ============================================================
# TO ADDRESS HANDLERS (7 steps)
# ============================================================

async def order_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 8/13: Collect recipient name"""
    from server import session_manager, sanitize_string, TO_NAME, TO_ADDRESS, with_typing_indicator
    
    name = update.message.text.strip()
    name = sanitize_string(name, max_length=50)
    
    # Validate
    is_valid, error_msg = validate_name(name)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_NAME
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_name'] = name
    await session_manager.update_session_atomic(user_id, step="TO_ADDRESS", data={'to_name': name})
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.TO_ADDRESS
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_ADDRESS
    
    return TO_ADDRESS


async def order_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 9/13: Collect recipient street address"""
    from server import session_manager, sanitize_string, TO_ADDRESS, TO_ADDRESS2
    
    address = update.message.text.strip()
    address = sanitize_string(address, max_length=100)
    
    # Validate
    is_valid, error_msg = validate_address(address, "Адрес")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_ADDRESS
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_address'] = address
    await session_manager.update_session_atomic(user_id, step="TO_ADDRESS2", data={'to_address': address})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData
    
    reply_markup = get_skip_and_cancel_keyboard(CallbackData.SKIP_TO_ADDRESS2)
    message_text = OrderStepMessages.TO_ADDRESS2
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_ADDRESS2
    
    return TO_ADDRESS2


async def order_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 10/13: Collect recipient address line 2 (optional)"""
    from server import session_manager, sanitize_string, TO_ADDRESS2, TO_CITY
    
    address2 = update.message.text.strip()
    address2 = sanitize_string(address2, max_length=100)
    
    if len(address2) > 100:
        await safe_telegram_call(update.message.reply_text("❌ Адрес 2 слишком длинный (максимум 100 символов)"))
        return TO_ADDRESS2
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_address2'] = address2
    await session_manager.update_session_atomic(user_id, step="TO_CITY", data={'to_address2': address2})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.TO_CITY
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_CITY
    
    return TO_CITY


async def order_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 11/13: Collect recipient city"""
    from server import session_manager, sanitize_string, TO_CITY, TO_STATE
    
    city = update.message.text.strip()
    city = sanitize_string(city, max_length=50)
    
    # Validate
    is_valid, error_msg = validate_city(city)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_CITY
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_city'] = city
    await session_manager.update_session_atomic(user_id, step="TO_STATE", data={'to_city': city})
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.TO_STATE
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_STATE
    
    return TO_STATE


async def order_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 12/13: Collect recipient state"""
    from server import session_manager, TO_STATE, TO_ZIP
    
    state = update.message.text.strip().upper()
    
    # Validate
    is_valid, error_msg = validate_state(state)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_STATE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_state'] = state
    await session_manager.update_session_atomic(user_id, step="TO_ZIP", data={'to_state': state})
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.TO_ZIP
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_ZIP
    
    return TO_ZIP


async def order_to_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 13/13: Collect recipient ZIP code"""
    from server import session_manager, TO_ZIP, TO_PHONE
    
    zip_code = update.message.text.strip()
    
    # Validate
    is_valid, error_msg = validate_zip(zip_code)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_ZIP
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_zip'] = zip_code
    await session_manager.update_session_atomic(user_id, step="TO_PHONE", data={'to_zip': zip_code})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData
    
    reply_markup = get_skip_and_cancel_keyboard(CallbackData.SKIP_TO_PHONE)
    message_text = OrderStepMessages.TO_PHONE
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_PHONE
    
    return TO_PHONE


async def order_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 14/14: Collect recipient phone (optional) and move to parcel info"""
    from server import session_manager, TO_PHONE, PARCEL_WEIGHT
    
    phone = update.message.text.strip()
    
    # Validate and format
    is_valid, error_msg, formatted_phone = validate_phone(phone)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_PHONE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_phone'] = formatted_phone
    await session_manager.update_session_atomic(user_id, step="PARCEL_WEIGHT", data={'to_phone': formatted_phone})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """📦 Вес посылки (в фунтах)
Например: 5 или 5.5
Минимум: 0.1 фунта
Максимум: 150 фунтов"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = PARCEL_WEIGHT
    
    return PARCEL_WEIGHT
