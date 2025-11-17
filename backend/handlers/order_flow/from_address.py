"""
Order Flow: FROM Address Handlers
Handles collection of sender (FROM) address information through 7 steps
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.validators import (
    validate_name, validate_address, validate_city,
    validate_state, validate_zip, validate_phone
)
from utils.handler_decorators import with_user_session, safe_handler, with_typing_action, with_services

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
    
    logger.info(f"🔵 order_from_name - User: {update.effective_user.id}")
    logger.info(f"🔍 DEBUG: editing_template_from={context.user_data.get('editing_template_from')}, editing_template_id={context.user_data.get('editing_template_id')}")
    
    # Remove cancel button from prompt if exists
    if 'last_prompt_message_id' in context.user_data:
        try:
            await update.effective_chat.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['last_prompt_message_id'],
                reply_markup=None
            )
            context.user_data.pop('last_prompt_message_id', None)
        except Exception as e:
            logger.debug(f"Could not remove prompt button: {e}")
    
    # Skip if user is in topup flow
    if context.user_data.get('awaiting_topup_amount'):
        logger.info("⏭️ Skipping - user in topup flow")
        return ConversationHandler.END
    
    name = update.message.text.strip()
    name = sanitize_string(name, max_length=50)
    
    logger.info(f"📝 Validating name: '{name}' (length: {len(name)})")
    
    # Validate using centralized validator
    is_valid, error_msg = validate_name(name)
    logger.info(f"✅ Validation result: is_valid={is_valid}, error_msg='{error_msg}'")
    
    if not is_valid:
        logger.warning(f"❌ Name validation FAILED for '{name}': {error_msg}")
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_NAME
    
    # Store in session AND context using service
    user_id = update.effective_user.id
    context.user_data['from_name'] = name
    
    # CRITICAL: Check and restore flags from DB session if missing
    from server import db
    session = await db.user_sessions.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0, "editing_template_from": 1, "editing_template_id": 1}
    )
    if session and session.get('editing_template_from'):
        context.user_data['editing_template_from'] = True
        context.user_data['editing_template_id'] = session.get('editing_template_id')
        logger.info(f"🔄 RESTORED editing_template_from flag in order_from_name")
    
    # Update session via service (skip if editing template)
    if not context.user_data.get('editing_template_from'):
        logger.info(f"📝 Updating session for FROM_NAME (normal flow)")
        await session_service.update_session_step(
            user_id,
            step="FROM_ADDRESS",
            data={'from_name': name}
        )
    else:
        logger.info(f"⏭️ SKIPPING session update - editing template FROM address")
    
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
@with_services(session_service=True)
async def order_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """
    Step 2/13: Collect sender street address
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import SecurityLogger, sanitize_string, FROM_ADDRESS, FROM_ADDRESS2, STATE_NAMES
    
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
    
    # Update session via service (skip if editing template)
    if not context.user_data.get('editing_template_from'):
        await session_service.update_session_step(
            user_id,
            step="FROM_ADDRESS2",
            data={'from_address': address}
        )
    
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
@with_services(session_service=True)
async def order_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """
    Step 3/13: Collect sender address line 2 (optional)
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import sanitize_string, FROM_ADDRESS2, FROM_CITY, STATE_NAMES
    
    
    
    address2 = update.message.text.strip()
    address2 = sanitize_string(address2, max_length=100)
    
    if len(address2) > 100:
        await safe_telegram_call(update.message.reply_text("❌ Адрес 2 слишком длинный (максимум 100 символов)"))
        return FROM_ADDRESS2
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_address2'] = address2
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_address2', address2)
        await session_service.update_session_step(user_id, step="FROM_CITY")
    
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
@with_services(session_service=True)
async def order_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """
    Step 4/13: Collect sender city
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import sanitize_string, FROM_CITY, FROM_STATE, STATE_NAMES
    
    
    
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
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_city', city)
        await session_service.update_session_step(user_id, step="FROM_STATE")
    
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
@with_services(session_service=True)
async def order_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """
    Step 5/13: Collect sender state
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import FROM_STATE, FROM_ZIP, STATE_NAMES
    
    
    
    state = update.message.text.strip().upper()
    
    # Validate
    is_valid, error_msg = validate_state(state)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_STATE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_state'] = state
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_state', state)
        await session_service.update_session_step(user_id, step="FROM_ZIP")
    
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
@with_services(session_service=True)
async def order_from_zip(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """
    Step 6/13: Collect sender ZIP code
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import FROM_ZIP, FROM_PHONE, STATE_NAMES
    
    
    
    zip_code = update.message.text.strip()
    
    # Validate
    is_valid, error_msg = validate_zip(zip_code)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_ZIP
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_zip'] = zip_code
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_zip', zip_code)
        await session_service.update_session_step(user_id, step="FROM_PHONE")
    
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
@with_services(session_service=True)
async def order_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """
    Step 7/13: Collect sender phone (optional)
    
    Decorators handle: User session + error handling + typing indicator
    """
    from server import FROM_PHONE, TO_NAME, STATE_NAMES
    
    
    
    phone = update.message.text.strip()
    
    # Validate and format
    is_valid, error_msg, formatted_phone = validate_phone(phone)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return FROM_PHONE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_phone'] = formatted_phone
    
    # CRITICAL: Load flags from DB session (they are lost between handler calls)
    from server import db
    session = await db.user_sessions.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0, "editing_template_from": 1, "editing_template_id": 1}
    )
    if session:
        editing_template_from = session.get('editing_template_from', False)
        editing_template_id = session.get('editing_template_id')
        if editing_template_from:
            context.user_data['editing_template_from'] = editing_template_from
            context.user_data['editing_template_id'] = editing_template_id
            logger.info(f"🔄 RESTORED FLAGS from DB: editing_template_from={editing_template_from}, editing_template_id={editing_template_id}")
    
    logger.info(f"📞 FROM phone saved: {formatted_phone}")
    logger.info(f"🔍 DEBUG ALL FLAGS: editing_from_address={context.user_data.get('editing_from_address')}, editing_template_from={context.user_data.get('editing_template_from')}, editing_template_to={context.user_data.get('editing_template_to')}")
    logger.info(f"🔍 DEBUG: editing_template_id={context.user_data.get('editing_template_id')}")
    logger.info(f"🔍 DEBUG: All user_data keys: {list(context.user_data.keys())}")
    
    # Check if we're editing only FROM address in order
    if context.user_data.get('editing_from_address'):
        logger.info("✅ FROM address edit complete (ORDER), returning to confirmation")
        context.user_data.pop('editing_from_address', None)
        # Don't update session for editing mode
        from handlers.order_flow.confirmation import show_data_confirmation
        return await show_data_confirmation(update, context)
    
    # Check if we're editing template FROM address
    if context.user_data.get('editing_template_from'):
        logger.info("✅ Template FROM address edit complete, saving to template")
        template_id = context.user_data.get('editing_template_id')
        
        if template_id:
            from server import db
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            # Update template in DB
            await db.templates.update_one(
                {"id": template_id},
                {"$set": {
                    "from_name": context.user_data.get('from_name', ''),
                    "from_street1": context.user_data.get('from_address', ''),
                    "from_street2": context.user_data.get('from_address2', ''),
                    "from_city": context.user_data.get('from_city', ''),
                    "from_state": context.user_data.get('from_state', ''),
                    "from_zip": context.user_data.get('from_zip', ''),
                    "from_phone": context.user_data.get('from_phone', '')
                }}
            )
            
            # Clear editing flags from both context AND DB session
            context.user_data.pop('editing_template_from', None)
            context.user_data.pop('editing_template_id', None)
            
            # Clear from DB session
            await db.user_sessions.update_one(
                {"user_id": user_id, "is_active": True},
                {"$unset": {
                    "editing_template_from": "",
                    "editing_template_id": ""
                }}
            )
            
            # Show success message with navigation
            keyboard = [
                [InlineKeyboardButton("👁️ Просмотреть шаблон", callback_data=f'template_view_{template_id}')],
                [InlineKeyboardButton("📋 К списку шаблонов", callback_data='my_templates')],
                [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "✅ Адрес отправителя в шаблоне обновлён!",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        return ConversationHandler.END
    
    logger.info(f"⚠️ NORMAL FLOW: Proceeding to TO_NAME (no editing flags detected)")
    
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
    
    logger.info(f"🔵 order_from_phone returning TO_NAME")
    return TO_NAME
