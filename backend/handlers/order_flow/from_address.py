"""
Order Flow: FROM Address Handlers
Handles collection of sender (FROM) address information through 7 steps
"""
import asyncio
import logging
from telegram import Update, ForceReply
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
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
    
    user_id = update.effective_user.id
    message_text = update.effective_message.text if update.message else "N/A"
    
    logger.info(f"🔵 ORDER_FROM_NAME - User: {user_id}, Message: '{message_text[:50]}'")
    
    # Skip if user is in topup flow
    if context.user_data.get('awaiting_topup_amount'):
        logger.info("⏭️ Skipping - user in topup flow")
        return ConversationHandler.END
    
    name = update.effective_message.text.strip()
    
    # Validate name
    from utils.validation import validate_name
    is_valid, error_msg = validate_name(name)
    if not is_valid:
        await safe_telegram_call(update.effective_message.reply_text(
            error_msg + "\n\nПожалуйста, введите имя отправителя:"
        ))
        return FROM_NAME
    
    name = sanitize_string(name, max_length=50)
    
    # Store in context
    user_id = update.effective_user.id
    context.user_data['from_name'] = name
    
    # Log action in background (don't wait)
    asyncio.create_task(SecurityLogger.log_action(
        "order_input",
        user_id,
        {"field": "from_name", "length": len(name)},
        "success"
    ))
    
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    
    # ✅ CRITICAL: Mark previous message with EXPLICIT old text (avoids race condition)
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # ✅ 2025: ForceReply + return состояния
    from utils.ui_utils import ask_with_cancel_and_focus, OrderStepMessages, TemplateEditMessages
    
    if context.user_data.get('editing_template_from') or context.user_data.get('editing_from_address'):
        message_text = TemplateEditMessages.FROM_ADDRESS
    else:
        message_text = OrderStepMessages.FROM_ADDRESS
    
    logger.info(f"✅ order_from_name completed - name: '{name}'")
    
    # Отправляем запрос пользователю (НЕ возвращаем состояние из функции)
    await ask_with_cancel_and_focus(
        update,
        context,
        message_text,
        placeholder="Например: 215 Clayton St.",
        next_state=FROM_ADDRESS,
        safe_telegram_call_func=safe_telegram_call
    )
    
    # ConversationHandler сам дождется ответа пользователя
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
    
    address = update.effective_message.text.strip()
    
    # Validate address
    from utils.validation import validate_address
    is_valid, error_msg = validate_address(address)
    if not is_valid:
        await safe_telegram_call(update.effective_message.reply_text(
            error_msg + "\n\nПожалуйста, введите адрес отправителя:"
        ))
        return FROM_ADDRESS
    
    address = sanitize_string(address, max_length=100)
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_address'] = address
    
    # Update session via service (skip if editing template)
    if not context.user_data.get('editing_template_from'):
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(
        #     user_id,
        #     step="FROM_ADDRESS2",
        #     data={'from_address': address}
        # )
        pass
    
    await SecurityLogger.log_action(
        "order_input",
        user_id,
        {"field": "from_address", "length": len(address)},
        "success"
    )
    
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData, TemplateEditMessages
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # Use different messages for template editing vs order creation
    if context.user_data.get('editing_template_from') or context.user_data.get('editing_from_address'):
        message_text = TemplateEditMessages.FROM_ADDRESS2
    else:
        message_text = OrderStepMessages.FROM_ADDRESS2
    
    # ✅ МАГИЧЕСКИЙ ГИБРИД 2025 (опциональное поле)
    from utils.ui_utils import ask_with_skip_cancel_and_focus
    
    await ask_with_skip_cancel_and_focus(
        update,
        context,
        message_text,
        skip_callback=CallbackData.SKIP_FROM_ADDRESS2,
        next_state=FROM_ADDRESS2,
        safe_telegram_call_func=safe_telegram_call
    )
    
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
    
    
    
    address2 = update.effective_message.text.strip()
    address2 = sanitize_string(address2, max_length=100)
    
    if len(address2) > 100:
        await safe_telegram_call(update.effective_message.reply_text("❌ Адрес 2 слишком длинный (максимум 100 символов)"))
        return FROM_ADDRESS2
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_address2'] = address2
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_address2', address2)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="FROM_CITY")
    
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # ✅ МАГИЧЕСКИЙ ГИБРИД 2025
    from utils.ui_utils import ask_with_cancel_and_focus, OrderStepMessages, TemplateEditMessages
    
    if context.user_data.get('editing_template_from') or context.user_data.get('editing_from_address'):
        message_text = TemplateEditMessages.FROM_CITY
    else:
        message_text = OrderStepMessages.FROM_CITY
    
    await ask_with_cancel_and_focus(
        update,
        context,
        message_text,
        placeholder="Например: San Francisco",
        next_state=FROM_CITY,
        safe_telegram_call_func=safe_telegram_call
    )
    
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
    
    
    
    city = update.effective_message.text.strip()
    
    # Validate city
    from utils.validation import validate_city
    is_valid, error_msg = validate_city(city)
    if not is_valid:
        await safe_telegram_call(update.effective_message.reply_text(
            error_msg + "\n\nПожалуйста, введите город отправителя:"
        ))
        return FROM_CITY
    
    city = sanitize_string(city, max_length=50)
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_city'] = city
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_city', city)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="FROM_STATE")
    
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages, TemplateEditMessages
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # Use different messages for template editing vs order creation
    if context.user_data.get('editing_template_from') or context.user_data.get('editing_from_address'):
        message_text = TemplateEditMessages.FROM_STATE
    else:
        message_text = OrderStepMessages.FROM_STATE
    
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(message_text))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
    
    asyncio.create_task(safe_background_task(send_next_step()))
    
    # Save current state for cancel button (UI-only, does NOT interfere with ConversationHandler)
    from server import STATE_NAMES
    
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
    
    
    
    state = update.effective_message.text.strip().upper()
    
    # Validate state code
    from utils.validation import validate_state
    is_valid, error_msg = validate_state(state)
    if not is_valid:
        await safe_telegram_call(update.effective_message.reply_text(error_msg))
        return FROM_STATE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_state'] = state
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_state', state)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="FROM_ZIP")
    
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    # ✅ МАГИЧЕСКИЙ ГИБРИД 2025
    from utils.ui_utils import ask_with_cancel_and_focus, OrderStepMessages, TemplateEditMessages
    
    if context.user_data.get('editing_template_from') or context.user_data.get('editing_from_address'):
        message_text = TemplateEditMessages.FROM_ZIP
    else:
        message_text = OrderStepMessages.FROM_ZIP
    
    await ask_with_cancel_and_focus(
        update,
        context,
        message_text,
        placeholder="Например: 94102",
        next_state=FROM_ZIP,
        safe_telegram_call_func=safe_telegram_call
    )
    
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
    
    
    
    zip_code = update.effective_message.text.strip()
    
    # Validate ZIP code
    from utils.validation import validate_zip
    is_valid, error_msg = validate_zip(zip_code)
    if not is_valid:
        await safe_telegram_call(update.effective_message.reply_text(error_msg + "\n\nПожалуйста, введите почтовый индекс:"))
        return FROM_ZIP
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_zip'] = zip_code
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_from'):
        await session_service.save_order_field(user_id, 'from_zip', zip_code)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="FROM_PHONE")
    
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # Show with SKIP option
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData, TemplateEditMessages
    
    # ✅ МАГИЧЕСКИЙ ГИБРИД 2025 (опциональное поле)
    from utils.ui_utils import ask_with_skip_cancel_and_focus
    
    if context.user_data.get('editing_template_from') or context.user_data.get('editing_from_address'):
        message_text = TemplateEditMessages.FROM_PHONE
    else:
        message_text = OrderStepMessages.FROM_PHONE
    
    await ask_with_skip_cancel_and_focus(
        update,
        context,
        message_text,
        skip_callback=CallbackData.SKIP_FROM_PHONE,
        next_state=FROM_PHONE,
        safe_telegram_call_func=safe_telegram_call
    )
    
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
    
    
    
    phone = update.effective_message.text.strip()
    
    # Validate phone (optional field)
    from utils.validation import validate_phone
    is_valid, error_msg = validate_phone(phone, required=False)
    if not is_valid:
        await safe_telegram_call(update.effective_message.reply_text(error_msg + "\n\nПожалуйста, введите номер телефона:"))
        return FROM_PHONE
    
    # Format phone (basic formatting without validation)
    digits_only = ''.join(filter(str.isdigit, phone))
    if len(digits_only) == 10:
        formatted_phone = f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only[0] == '1':
        formatted_phone = f"+{digits_only}"
    else:
        formatted_phone = f"+{digits_only}" if digits_only else phone
    
    # Store
    user_id = update.effective_user.id
    context.user_data['from_phone'] = formatted_phone
    
    logger.info(f"📞 FROM phone saved: {formatted_phone}")
    
    # ✅ CRITICAL: Mark previous message with checkmark (add emoji)
    old_prompt_text = context.user_data.get('last_bot_message_text', '')
    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # CRITICAL: Check DB session DIRECTLY for editing flags (don't rely on context.user_data)
    from server import db
    session = await db.user_sessions.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0, "editing_template_from": 1, "editing_template_to": 1, "editing_template_id": 1}
    )
    
    logger.info(f"🔍 DEBUG: DB session found: {session is not None}")
    if session:
        logger.info(f"🔍 DEBUG: DB session editing_template_from={session.get('editing_template_from')}, editing_template_id={session.get('editing_template_id')}")
    
    editing_template_from_db = session.get('editing_template_from', False) if session else False
    editing_template_id_db = session.get('editing_template_id') if session else None
    
    logger.info(f"🔍 DEBUG: FROM DB - editing_template_from={editing_template_from_db}, editing_template_id={editing_template_id_db}")
    logger.info(f"🔍 DEBUG: FROM context - editing_from_address={context.user_data.get('editing_from_address')}, editing_template_from={context.user_data.get('editing_template_from')}")
    
    # Check if we're editing only FROM address in order
    if context.user_data.get('editing_from_address'):
        logger.info("✅ FROM address edit complete (ORDER), returning to confirmation")
        context.user_data.pop('editing_from_address', None)
        # Don't update session for editing mode
        from handlers.order_flow.confirmation import show_data_confirmation
        return await show_data_confirmation(update, context)
    
    # Check if we're editing template FROM address (CHECK DB DIRECTLY, not context.user_data)
    if editing_template_from_db and editing_template_id_db:
        logger.info(f"✅ Template FROM address edit complete, saving to template_id={editing_template_id_db}")
        template_id = editing_template_id_db
        
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
            
            # 🚀 PERFORMANCE: Send message in background
            asyncio.create_task(update.effective_message.reply_text(
                "✅ Адрес отправителя в шаблоне обновлён!",
                reply_markup=reply_markup
            ))
            
            return ConversationHandler.END
        
        return ConversationHandler.END
    
    logger.info("⚠️ NORMAL FLOW: Proceeding to TO_NAME (no editing flags detected)")
    
    from utils.ui_utils import OrderStepMessages
    message_text = OrderStepMessages.TO_NAME
    
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(message_text))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
    
    asyncio.create_task(safe_background_task(send_next_step()))
    
    logger.info("🔵 order_from_phone returning TO_NAME")
    # Save current state for cancel button (UI-only, does NOT interfere with ConversationHandler)
    from server import STATE_NAMES
    
    return TO_NAME
