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
from utils.handler_decorators import with_user_session, safe_handler, with_typing_action

# These will be imported from server when handlers are called
# from server import (
#     session_manager, SecurityLogger, sanitize_string,
#     FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, 
#     FROM_STATE, FROM_ZIP, FROM_PHONE, TO_NAME
# )


# ============================================================
# FROM ADDRESS HANDLERS (7 steps)
# ============================================================

@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """
    Step 1/13: Collect sender name
    
    Decorators handle:
    - User session management + blocking check
    - Error handling
    - Typing indicator
    """
    from server import SecurityLogger, sanitize_string, FROM_NAME, FROM_ADDRESS, STATE_NAMES
    from repositories.session_repository import SessionRepository
    from server import db
    
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
    
    # Store in session AND context using service
    user_id = update.effective_user.id
    context.user_data['from_name'] = name
    
    # Update session via service
    await session_service.update_session_step(
        user_id,
        step="FROM_ADDRESS",
        data={'from_name': name}
    )
    
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
        context.user_data['last_state'] = STATE_NAMES[FROM_ADDRESS]
    
    logger.info(f"✅ order_from_name completed - name: '{name}'")
    return FROM_ADDRESS


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
async def order_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 2/13: Collect sender street address
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import SecurityLogger, sanitize_string, FROM_ADDRESS, FROM_ADDRESS2, STATE_NAMES
    from repositories.session_repository import SessionRepository
    from server import db
    
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
    
    # Update session via repository
    session_repo = SessionRepository(db)
    await session_repo.update_temp_data(user_id, {'from_address': address})
    await session_repo.update_step(user_id, "FROM_ADDRESS2")
    
    await SecurityLogger.log_action(
        "order_input",
        user_id,
        {"field": "from_address", "length": len(address)},
        "success"
    )
    
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Show next step with SKIP option
    reply_markup = get_skip_and_cancel_keyboard(CallbackData.SKIP_FROM_ADDRESS2)
    message_text = OrderStepMessages.FROM_ADDRESS2
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[FROM_ADDRESS2]
    
    return FROM_ADDRESS2


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
async def order_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 3/13: Collect sender address line 2 (optional)
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import sanitize_string, FROM_ADDRESS2, FROM_CITY, STATE_NAMES
    from repositories.session_repository import SessionRepository
    from server import db
    
    address2 = update.message.text.strip()
    address2 = sanitize_string(address2, max_length=100)
    
    if len(address2) > 100:
        await safe_telegram_call(update.message.reply_text("❌ Адрес 2 слишком длинный (максимум 100 символов)"))
        return FROM_ADDRESS2
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_address2'] = address2
    
    # Update session via repository
    session_repo = SessionRepository(db)
    await session_repo.update_temp_data(user_id, {'from_address2': address2})
    await session_repo.update_step(user_id, "FROM_CITY")
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.FROM_CITY
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[FROM_CITY]
    
    return FROM_CITY


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
async def order_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 4/13: Collect sender city
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import sanitize_string, FROM_CITY, FROM_STATE, STATE_NAMES
    from repositories.session_repository import SessionRepository
    from server import db
    
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
    
    # Update session via repository
    session_repo = SessionRepository(db)
    await session_repo.update_temp_data(user_id, {'from_city': city})
    await session_repo.update_step(user_id, "FROM_STATE")
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.FROM_STATE
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[FROM_STATE]
    
    return FROM_STATE


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
async def order_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 5/13: Collect sender state
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import FROM_STATE, FROM_ZIP, STATE_NAMES
    from repositories.session_repository import SessionRepository
    from server import db
    
    state = update.message.text.strip().upper()
    
    # Validate
    is_valid, error_msg = validate_state(state)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_STATE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_state'] = state
    
    # Update session via repository
    session_repo = SessionRepository(db)
    await session_repo.update_temp_data(user_id, {'from_state': state})
    await session_repo.update_step(user_id, "FROM_ZIP")
    
    asyncio.create_task(mark_message_as_selected(update, context))
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.FROM_ZIP
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[FROM_ZIP]
    
    return FROM_ZIP


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
async def order_from_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 6/13: Collect sender ZIP code
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import FROM_ZIP, FROM_PHONE, STATE_NAMES
    from repositories.session_repository import SessionRepository
    from server import db
    
    zip_code = update.message.text.strip()
    
    # Validate
    is_valid, error_msg = validate_zip(zip_code)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_ZIP
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_zip'] = zip_code
    
    # Update session via repository
    session_repo = SessionRepository(db)
    await session_repo.update_temp_data(user_id, {'from_zip': zip_code})
    await session_repo.update_step(user_id, "FROM_PHONE")
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Show with SKIP option
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData
    reply_markup = get_skip_and_cancel_keyboard(CallbackData.SKIP_FROM_PHONE)
    message_text = OrderStepMessages.FROM_PHONE
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[FROM_PHONE]
    
    return FROM_PHONE


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
async def order_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 7/13: Collect sender phone (optional)
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import FROM_PHONE, TO_NAME, STATE_NAMES
    from repositories.session_repository import SessionRepository
    from server import db
    
    phone = update.message.text.strip()
    
    # Validate and format
    is_valid, error_msg, formatted_phone = validate_phone(phone)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_PHONE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_phone'] = formatted_phone
    
    # Update session via repository
    session_repo = SessionRepository(db)
    await session_repo.update_temp_data(user_id, {'from_phone': formatted_phone})
    await session_repo.update_step(user_id, "TO_NAME")
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.TO_NAME
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[TO_NAME]
    
    return TO_NAME
