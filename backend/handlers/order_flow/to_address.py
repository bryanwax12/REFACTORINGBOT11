"""
Order Flow: TO Address Handlers
Handles collection of recipient (TO) address information through 7 steps
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.validators import (
    validate_name, validate_address, validate_city,
    validate_state, validate_zip, validate_phone
)
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
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_name', name)
        await session_service.update_session_step(user_id, step="TO_ADDRESS")
    
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
        context.user_data['last_state'] = STATE_NAMES[TO_ADDRESS]
    
    return TO_ADDRESS


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 9/13: Collect recipient street address"""
    from server import sanitize_string, TO_ADDRESS, TO_ADDRESS2, STATE_NAMES
    
    
    
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
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_address', address)
        await session_service.update_session_step(user_id, step="TO_ADDRESS2")
    
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
        context.user_data['last_state'] = STATE_NAMES[TO_ADDRESS2]
    
    return TO_ADDRESS2


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 10/13: Collect recipient address line 2 (optional)"""
    from server import sanitize_string, TO_ADDRESS2, TO_CITY, STATE_NAMES
    
    
    
    address2 = update.message.text.strip()
    address2 = sanitize_string(address2, max_length=100)
    
    if len(address2) > 100:
        await safe_telegram_call(update.message.reply_text("❌ Адрес 2 слишком длинный (максимум 100 символов)"))
        return TO_ADDRESS2
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_address2'] = address2
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_address2', address2)
        await session_service.update_session_step(user_id, step="TO_CITY")
    
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
        context.user_data['last_state'] = STATE_NAMES[TO_CITY]
    
    return TO_CITY


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 11/13: Collect recipient city"""
    from server import sanitize_string, TO_CITY, TO_STATE, STATE_NAMES
    
    
    
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
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_city', city)
        await session_service.update_session_step(user_id, step="TO_STATE")
    
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
        context.user_data['last_state'] = STATE_NAMES[TO_STATE]
    
    return TO_STATE


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 12/13: Collect recipient state"""
    from server import TO_STATE, TO_ZIP, STATE_NAMES
    
    
    
    state = update.message.text.strip().upper()
    
    # Validate
    is_valid, error_msg = validate_state(state)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_STATE
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_state'] = state
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_state', state)
        await session_service.update_session_step(user_id, step="TO_ZIP")
    
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
        context.user_data['last_state'] = STATE_NAMES[TO_ZIP]
    
    return TO_ZIP


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_zip(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 13/13: Collect recipient ZIP code"""
    from server import TO_ZIP, TO_PHONE, STATE_NAMES
    
    
    
    zip_code = update.message.text.strip()
    
    # Validate
    is_valid, error_msg = validate_zip(zip_code)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_ZIP
    
    # Store
    user_id = update.effective_user.id
    context.user_data['to_zip'] = zip_code
    
    # Update session via repository (skip if editing template)
    # Session service injected via decorator
    if not context.user_data.get('editing_template_to'):
        await session_service.save_order_field(user_id, 'to_zip', zip_code)
        await session_service.update_session_step(user_id, step="TO_PHONE")
    
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
        context.user_data['last_state'] = STATE_NAMES[TO_PHONE]
    
    return TO_PHONE


@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=False, require_session=True)
@with_services(session_service=True)
async def order_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, session_service):
    """Step 14/13: Collect recipient phone (optional)"""
    from server import TO_PHONE, PARCEL_WEIGHT, STATE_NAMES
    
    
    
    phone = update.message.text.strip()
    
    # Validate and format
    is_valid, error_msg, formatted_phone = validate_phone(phone)
    if not is_valid:
        await safe_telegram_call(update.message.reply_text(error_msg))
        return TO_PHONE
    
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
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Check if we're editing only TO address in order
    if context.user_data.get('editing_to_address'):
        logger.info("✅ TO address edit complete, returning to confirmation")
        context.user_data.pop('editing_to_address', None)
        from handlers.order_flow.confirmation import show_data_confirmation
        return await show_data_confirmation(update, context)
    
    # Check if we're editing template TO address
    if context.user_data.get('editing_template_to'):
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
            
            await update.message.reply_text(
                "✅ Адрес получателя в шаблоне обновлён!",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        return ConversationHandler.END
    
    # Update session via repository (for normal order flow)
    # Session service injected via decorator
    await session_service.save_order_field(user_id, 'to_phone', formatted_phone)
    await session_service.update_session_step(user_id, step="PARCEL_WEIGHT")
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderStepMessages.PARCEL_WEIGHT
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[PARCEL_WEIGHT]
    
    return PARCEL_WEIGHT
