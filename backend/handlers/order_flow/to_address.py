"""
Order Flow: TO Address Handlers
Handles collection of recipient (TO) address information through 7 steps
"""
import asyncio
import logging
from telegram import Update, ForceReply
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.handler_decorators import with_user_session, safe_handler, with_typing_action, with_services
from telegram.ext import ConversationHandler


# ============================================================
# TO ADDRESS HANDLERS (7 steps)
# ============================================================

@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 8/13: Collect recipient name"""
    from server import sanitize_string, TO_NAME, TO_ADDRESS, STATE_NAMES
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔵 order_to_name CALLED - User: {update.effective_user.id}")
    logger.info(f"🔍 DEBUG: editing_template_from={context.user_data.get('editing_template_from')}, editing_template_to={context.user_data.get('editing_template_to')}")
    logger.info(f"🔍 DEBUG: All user_data keys: {list(context.user_data.keys())}")
    
    # Remove cancel button from prompt if exists
    # Try to get message_id from context first, then from DB
    message_id_to_remove = context.user_data.get('last_prompt_message_id')
    
    if not message_id_to_remove:
        # Load from DB if not in context
        from server import db
        session = await db.user_sessions.find_one(
            {"user_id": update.effective_user.id, "is_active": True},
            {"_id": 0, "last_prompt_message_id": 1}
        )
        if session:
            message_id_to_remove = session.get('last_prompt_message_id')
            logger.info(f"🔄 Loaded last_prompt_message_id from DB: {message_id_to_remove}")
    
    if message_id_to_remove:
        try:
            logger.info(f"🗑️ Attempting to remove cancel button from message_id={message_id_to_remove}")
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=message_id_to_remove,
                reply_markup=None
            )
            context.user_data.pop('last_prompt_message_id', None)
            
            # Remove from DB too
            from server import db
            await db.user_sessions.update_one(
                {"user_id": update.effective_user.id, "is_active": True},
                {"$unset": {"last_prompt_message_id": ""}}
            )
            logger.info("✅ Cancel button removed successfully")
        except Exception as e:
            logger.warning(f"⚠️ Could not remove cancel button: {e}")
    
    name = update.effective_message.text.strip()
    name = sanitize_string(name, max_length=50)
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_name'] = name
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_name', name)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="TO_ADDRESS")
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages, TemplateEditMessages
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # ✅ МАГИЧЕСКИЙ ГИБРИД 2025
    from utils.ui_utils import ask_with_cancel_and_focus
    
    if context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address'):
        message_text = TemplateEditMessages.TO_ADDRESS
    else:
        message_text = OrderStepMessages.TO_ADDRESS
    
    await ask_with_cancel_and_focus(
        update,
        context,
        message_text,
        placeholder="Например: 456 Oak Ave.",
        safe_telegram_call_func=safe_telegram_call
    )
    
    return TO_ADDRESS


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 9/13: Collect recipient street address"""
    from server import sanitize_string, TO_ADDRESS, TO_ADDRESS2, STATE_NAMES
    
    
    
    address = update.effective_message.text.strip()
    address = sanitize_string(address, max_length=100)
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_address'] = address
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_address', address)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="TO_ADDRESS2")
    
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    
    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    
    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData, TemplateEditMessages
    
    # Use different messages for template editing vs order creation
    if context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address'):
        message_text = TemplateEditMessages.TO_ADDRESS2
    else:
        message_text = OrderStepMessages.TO_ADDRESS2
    
    reply_markup = get_skip_and_cancel_keyboard(CallbackData.SKIP_TO_ADDRESS2)
    
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    

    asyncio.create_task(send_next_step())

    return TO_ADDRESS2


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 10/13: Collect recipient address line 2 (optional)"""
    from server import sanitize_string, TO_ADDRESS2, TO_CITY, STATE_NAMES
    
    
    
    address2 = update.effective_message.text.strip()
    address2 = sanitize_string(address2, max_length=100)
    
    if len(address2) > 100:
        await safe_telegram_call(update.effective_message.reply_text("❌ Адрес 2 слишком длинный (максимум 100 символов)"))
        return TO_ADDRESS2
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_address2'] = address2
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_address2', address2)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="TO_CITY")
    
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    
    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    
    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages, TemplateEditMessages
    
    # Use different messages for template editing vs order creation
    if context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address'):
        message_text = TemplateEditMessages.TO_CITY
    else:
        message_text = OrderStepMessages.TO_CITY
    
    reply_markup = get_cancel_keyboard()
    
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))

    asyncio.create_task(send_next_step())

    # Save current state for cancel button (UI-only, does NOT interfere with ConversationHandler)
    from server import STATE_NAMES
    
    return TO_CITY


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 11/13: Collect recipient city"""
    from server import sanitize_string, TO_CITY, TO_STATE, STATE_NAMES
    
    
    
    city = update.effective_message.text.strip()
    city = sanitize_string(city, max_length=50)
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_city'] = city
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_city', city)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="TO_STATE")
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages, TemplateEditMessages
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    from utils.ui_utils import get_cancel_keyboard
    
    # Use different messages for template editing vs order creation
    if context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address'):
        message_text = TemplateEditMessages.TO_STATE
    else:
        message_text = OrderStepMessages.TO_STATE
    
    reply_markup = get_cancel_keyboard()
    
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
    
    asyncio.create_task(send_next_step())
    
    # Save current state for cancel button (UI-only, does NOT interfere with ConversationHandler)
    from server import STATE_NAMES
    
    return TO_STATE


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 12/13: Collect recipient state"""
    from server import TO_STATE, TO_ZIP, STATE_NAMES
    
    
    
    state = update.effective_message.text.strip().upper()
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_state'] = state
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_state', state)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="TO_ZIP")
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages, TemplateEditMessages
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    from utils.ui_utils import get_cancel_keyboard
    
    # Use different messages for template editing vs order creation
    if context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address'):
        message_text = TemplateEditMessages.TO_ZIP
    else:
        message_text = OrderStepMessages.TO_ZIP
    
    reply_markup = get_cancel_keyboard()
    
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))

    asyncio.create_task(send_next_step())

    # Save current state for cancel button (UI-only, does NOT interfere with ConversationHandler)
    from server import STATE_NAMES
    
    return TO_ZIP


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_zip(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 13/13: Collect recipient ZIP code"""
    from server import TO_ZIP, TO_PHONE, STATE_NAMES
    
    
    
    zip_code = update.effective_message.text.strip()
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_zip'] = zip_code
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_zip', zip_code)
        # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="TO_PHONE")
    
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    
    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    
    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    from utils.ui_utils import get_skip_and_cancel_keyboard, OrderStepMessages, CallbackData, TemplateEditMessages
    
    # Use different messages for template editing vs order creation
    if context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address'):
        message_text = TemplateEditMessages.TO_PHONE
    else:
        message_text = OrderStepMessages.TO_PHONE
    
    reply_markup = get_skip_and_cancel_keyboard(CallbackData.SKIP_TO_PHONE)
    
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    

    asyncio.create_task(send_next_step())

    # Save current state for cancel button (UI-only, does NOT interfere with ConversationHandler)
    from server import STATE_NAMES
    
    return TO_PHONE


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 14/13: Collect recipient phone (optional)"""
    from server import TO_PHONE, PARCEL_WEIGHT, STATE_NAMES
    
    
    
    phone = update.effective_message.text.strip()
    
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
    context.user_data['to_phone'] = formatted_phone
    
    # CRITICAL: Load flags from DB session (they are lost between handler calls)
    from server import db
    session = await db.user_sessions.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0, "editing_template_to": 1, "editing_template_id": 1}
    )
    if session:
        editing_template_to = session.get('editing_template_to', False)
        editing_template_id = session.get('editing_template_id')
        if editing_template_to:
            context.user_data['editing_template_to'] = editing_template_to
            context.user_data['editing_template_id'] = editing_template_id
            logger.info(f"🔄 RESTORED FLAGS from DB: editing_template_to={editing_template_to}, editing_template_id={editing_template_id}")
    
    from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text))
    
    # Check if we're editing only TO address in order
    if context.user_data.get('editing_to_address'):
        logger.info("✅ TO address edit complete, returning to confirmation")
        context.user_data.pop('editing_to_address', None)
        from handlers.order_flow.confirmation import show_data_confirmation
        return await show_data_confirmation(update, context)
    
    # Check if we're editing template TO address
    if context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address'):
        logger.info("✅ Template TO address edit complete, saving to template")
        template_id = context.user_data.get('editing_template_id')
        
        if template_id:
            from server import db
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            # Update template in DB
            await db.templates.update_one(
                {"id": template_id},
                {"$set": {
                    "to_name": context.user_data.get('to_name', ''),
                    "to_street1": context.user_data.get('to_address', ''),
                    "to_street2": context.user_data.get('to_address2', ''),
                    "to_city": context.user_data.get('to_city', ''),
                    "to_state": context.user_data.get('to_state', ''),
                    "to_zip": context.user_data.get('to_zip', ''),
                    "to_phone": context.user_data.get('to_phone', '')
                }}
            )
            
            # Clear editing flags from both context AND DB session
            context.user_data.pop('editing_template_to', None)
            context.user_data.pop('editing_template_id', None)
            
            # Clear from DB session
            await db.user_sessions.update_one(
                {"user_id": user_id, "is_active": True},
                {"$unset": {
                    "editing_template_to": "",
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
                "✅ Адрес получателя в шаблоне обновлён!",
                reply_markup=reply_markup
            ))
            
            return ConversationHandler.END
        
        return ConversationHandler.END
    
    # Update session via repository (for normal order flow)
    # Session service injected via decorator
    await session_service.save_order_field(user_id, 'to_phone', formatted_phone)
    # REMOVED: ConversationHandler manages state via Persistence
        # await session_service.update_session_step(user_id, step="PARCEL_WEIGHT")
    
    from utils.ui_utils import get_cancel_keyboard
    message_text = OrderStepMessages.PARCEL_WEIGHT
    reply_markup = get_cancel_keyboard()
    
    # Save last_state BEFORE sending (so it's saved even if send fails)
    context.user_data['last_bot_message_text'] = message_text
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_next_step():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
    

    asyncio.create_task(send_next_step())

    # Save current state for cancel button (UI-only, does NOT interfere with ConversationHandler)
    from server import STATE_NAMES
    
    return PARCEL_WEIGHT
