"""
Order Flow: FROM Address Handlers
Handles collection of sender (FROM) address information through 7 steps
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.validators import (
    validate_name, validate_address, validate_city,
    validate_state, validate_zip, validate_phone
)

# These will be imported from server when handlers are called
# from server import (
#     session_manager, SecurityLogger, sanitize_string,
#     FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, 
#     FROM_STATE, FROM_ZIP, FROM_PHONE, TO_NAME
# )


# ============================================================
# FROM ADDRESS HANDLERS (7 steps)
# ============================================================

async def order_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1/13: Collect sender name"""
    from server import session_manager, SecurityLogger, sanitize_string, FROM_NAME, FROM_ADDRESS
    
    logger.info(f"🔵 order_from_name - User: {update.effective_user.id}")
    
    # Skip if user is in topup flow
    if context.user_data.get('awaiting_topup_amount'):
        logger.info("⏭️ Skipping - user in topup flow")
        return ConversationHandler.END
    
    name = update.message.text.strip()
    name = sanitize_string(name, max_length=50)
    
    # Validate using centralized validator
    is_valid, error_msg = validate_name(name)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_NAME
    
    # Store in session AND context
    user_id = update.effective_user.id
    context.user_data['from_name'] = name
    await session_manager.update_session_atomic(user_id, step="FROM_ADDRESS", data={'from_name': name})
    
    # Log action
    await SecurityLogger.log_action(
        "order_input",
        user_id,
        {"field": "from_name", "length": len(name)},
        "success"
    )
    
    # Mark previous message as selected
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Show next step
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.FROM_ADDRESS
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_ADDRESS
    
    logger.info(f"✅ order_from_name completed - name: '{name}'")
    return FROM_ADDRESS


async def order_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2/13: Collect sender street address"""
    from server import session_manager, SecurityLogger, sanitize_string, FROM_ADDRESS, FROM_ADDRESS2
    
    logger.info(f"🔵 order_from_address - User: {update.effective_user.id}")
    
    address = update.message.text.strip()
    address = sanitize_string(address, max_length=100)
    
    # Validate
    is_valid, error_msg = validate_address(address, "Адрес")
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_ADDRESS
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_address'] = address
    await session_manager.update_session_atomic(user_id, step="FROM_ADDRESS2", data={'from_address': address})
    
    await SecurityLogger.log_action(
        "order_input",
        user_id,
        {"field": "from_address", "length": len(address)},
        "success"
    )
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Show next step with SKIP option
    keyboard = [
        [InlineKeyboardButton("⏭️ Пропустить", callback_data='skip_from_address2')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 3/13: 🏢 Адрес 2 (опционально)
Например: Apt 4B или Suite 200
Или нажмите "Пропустить" """
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_ADDRESS2
    
    return FROM_ADDRESS2


async def order_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3/13: Collect sender address line 2 (optional)"""
    from server import session_manager, sanitize_string, FROM_ADDRESS2, FROM_CITY
    
    address2 = update.message.text.strip()
    address2 = sanitize_string(address2, max_length=100)
    
    if len(address2) > 100:
        await safe_telegram_call(update.message.reply_text("❌ Адрес 2 слишком длинный (максимум 100 символов)"))
        return FROM_ADDRESS2
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_address2'] = address2
    await session_manager.update_session_atomic(user_id, step="FROM_CITY", data={'from_address2': address2})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 4/13: 🏙 Город отправителя
Например: San Francisco"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_CITY
    
    return FROM_CITY


async def order_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4/13: Collect sender city"""
    from server import session_manager, sanitize_string, FROM_CITY, FROM_STATE
    
    city = update.message.text.strip()
    city = sanitize_string(city, max_length=50)
    
    # Validate
    is_valid, error_msg = validate_city(city)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_CITY
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_city'] = city
    await session_manager.update_session_atomic(user_id, step="FROM_STATE", data={'from_city': city})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 5/13: 📍 Штат отправителя (2 буквы)
Например: CA, NY, TX, FL"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_STATE
    
    return FROM_STATE


async def order_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 5/13: Collect sender state"""
    from server import session_manager, FROM_STATE, FROM_ZIP
    
    state = update.message.text.strip().upper()
    
    # Validate
    is_valid, error_msg = validate_state(state)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_STATE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_state'] = state
    await session_manager.update_session_atomic(user_id, step="FROM_ZIP", data={'from_state': state})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 6/13: 📮 ZIP код отправителя
Например: 94102"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_ZIP
    
    return FROM_ZIP


async def order_from_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 6/13: Collect sender ZIP code"""
    from server import session_manager, FROM_ZIP, FROM_PHONE
    
    zip_code = update.message.text.strip()
    
    # Validate
    is_valid, error_msg = validate_zip(zip_code)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_ZIP
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_zip'] = zip_code
    await session_manager.update_session_atomic(user_id, step="FROM_PHONE", data={'from_zip': zip_code})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Show with SKIP option
    keyboard = [
        [InlineKeyboardButton("⏭️ Пропустить", callback_data='skip_from_phone')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 7/13: 📞 Телефон отправителя (опционально)
Например: +11234567890 или 1234567890
Или нажмите "Пропустить" """
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_PHONE
    
    return FROM_PHONE


async def order_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 7/13: Collect sender phone (optional)"""
    from server import session_manager, FROM_PHONE, TO_NAME
    
    phone = update.message.text.strip()
    
    # Validate and format
    is_valid, error_msg, formatted_phone = validate_phone(phone)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_PHONE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_phone'] = formatted_phone
    await session_manager.update_session_atomic(user_id, step="TO_NAME", data={'from_phone': formatted_phone})
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 8/13: 👤 Имя получателя
Например: Jane Doe"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_NAME
    
    return TO_NAME
