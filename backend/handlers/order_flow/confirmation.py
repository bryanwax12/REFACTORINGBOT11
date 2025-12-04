"""
Order Flow: Data Confirmation Handlers
Handles order data confirmation, editing, and template saving
"""
import logging
import asyncio
from telegram import Update, ForceReply
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected, check_stale_interaction
from handlers.order_flow.cancellation import cancel_order, confirm_cancel_order, return_to_order


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def show_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show summary of entered data with edit option"""
    from server import CONFIRM_DATA
    from utils.ui_utils import DataConfirmationUI
    
    data = context.user_data
    
    # Format the summary message using UI utils
    message = DataConfirmationUI.confirmation_header()
    message += "📤 " + DataConfirmationUI.format_address_section("ОТПРАВИТЕЛЬ", data, "from")
    message += "📥 " + DataConfirmationUI.format_address_section("ПОЛУЧАТЕЛЬ", data, "to")
    message += DataConfirmationUI.format_parcel_section(data)
    message += "\n✅ *Подтвердите данные или отредактируйте*"
    
    # Build keyboard using UI utils
    reply_markup = DataConfirmationUI.build_confirmation_keyboard()
    
    # Use effective_message to handle both regular messages and callback queries
    effective_msg = update.effective_message
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_confirmation():
        bot_msg = await safe_telegram_call(effective_msg.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown'))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message
    
    asyncio.create_task(send_confirmation())
    
    return CONFIRM_DATA


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_data_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit data button"""
    from server import show_edit_menu
    return await show_edit_menu(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_save_as_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle save as template button"""
    from server import TEMPLATE_NAME, safe_telegram_call, mark_message_as_selected
    from utils.ui_utils import TemplateManagementUI
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    # Prompt for template name with custom back button
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import logging
    logger = logging.getLogger(__name__)
    
    keyboard = [[InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='cancel_template_save')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    logger.info("📝 Creating template save prompt with callback_data='cancel_template_save'")
    
    # 🚀 PERFORMANCE: Send message in background
    async def send_template_prompt():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            TemplateManagementUI.template_name_prompt(),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
        # Save prompt message ID to remove button later
        if bot_msg:
            context.user_data['last_prompt_message_id'] = bot_msg.message_id
    
    asyncio.create_task(send_template_prompt())
    
    # Clear last_bot_message to not interfere with text input
    context.user_data.pop('last_bot_message_id', None)
    context.user_data.pop('last_bot_message_text', None)
    
    return TEMPLATE_NAME


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirm data button - proceed to fetch shipping rates"""
    from server import fetch_shipping_rates
    return await fetch_shipping_rates(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def check_data_from_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to data confirmation screen from cancel dialog"""
    query = update.callback_query
    from server import safe_telegram_call
    await safe_telegram_call(query.answer())
    
    # Go back to data confirmation screen
    return await show_data_confirmation(update, context)


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    'show_data_confirmation',
    'handle_data_edit',
    'handle_save_as_template',
    'handle_confirm_data',
    'check_data_from_cancel'
]



@safe_handler(fallback_state=ConversationHandler.END)
async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu to select what to edit"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from utils.ui_utils import DataConfirmationUI
    from server import EDIT_MENU
    import asyncio
    
    query = update.callback_query
    
    # Mark previous message as selected (non-blocking)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    message = "✏️ Что вы хотите изменить?"
    
    # Build keyboard using UI utils
    reply_markup = DataConfirmationUI.build_edit_menu_keyboard()
    
    await safe_telegram_call(update.effective_message.reply_text(message, reply_markup=reply_markup))
    return EDIT_MENU




@safe_handler(fallback_state=ConversationHandler.END)
async def handle_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's choice on data confirmation"""
    import logging
    from server import (
        FROM_NAME, TO_NAME, PARCEL_WEIGHT, TEMPLATE_NAME, STATE_NAMES
    )
    
    logger = logging.getLogger(__name__)
    logger.debug("🎯 handle_data_confirmation CALLED!")
    logger.info(f"🎯 handle_data_confirmation called with query.data={update.callback_query.data if update.callback_query else 'None'}")
    logger.info(f"🎯 user_data keys at start: {list(context.user_data.keys())}")
    
    query = update.callback_query
    logger.debug(f"🎯 Query data: {query.data if query else 'None'}")
    
    # Skip stale check for edit buttons - they should always work if we're in CONFIRM_DATA state
    edit_buttons = ['edit_from_address', 'edit_to_address', 'edit_parcel', 'edit_data']
    if query.data not in edit_buttons:
        # Check for stale interaction
        if await check_stale_interaction(query, context):
            logger.warning(f"❌ Stale interaction detected for query.data={query.data}")
            return ConversationHandler.END
    else:
        logger.info(f"✅ Skipping stale check for edit button: {query.data}")
    
    await safe_telegram_call(query.answer())
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    # Mark previous message as selected (remove buttons)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    if query.data == 'confirm_data':
        # User confirmed data, proceed to fetch rates
        logger.info("✅ User confirmed data, calling fetch_shipping_rates...")
        from handlers.order_flow.rates import fetch_shipping_rates
        return await fetch_shipping_rates(update, context)
    
    # Note: 'save_template' is now handled by handle_save_as_template function
    # This case should not be reached anymore
    
    if query.data == 'edit_data':
        # Show edit menu
        return await show_edit_menu(update, context)
    
    if query.data == 'edit_addresses_error':
        # Show edit menu after rate error
        return await show_edit_menu(update, context)
    
    if query.data == 'edit_from_address':
        # Mark previous message as selected (non-blocking)
        # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

        old_prompt_text = context.user_data.get('last_bot_message_text', '')

        asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
        
        logger.info(f"🔧 Starting FROM address edit - user_data keys: {list(context.user_data.keys())}")
        
        # Edit from address
        context.user_data['editing_from_address'] = True
        
        # 🚀 PERFORMANCE: Send message in background
        async def send_edit_prompt():
            bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                "📤 Редактирование адреса отправителя\n\nШаг 1/7: Имя отправителя\nНапример: John Smith"
            ))
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
        
        asyncio.create_task(send_edit_prompt())
        logger.info("✅ Returning FROM_NAME state for editing")
        return FROM_NAME
    
    if query.data == 'edit_to_address':
        # Mark previous message as selected (non-blocking)
        # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

        old_prompt_text = context.user_data.get('last_bot_message_text', '')

        asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
        
        logger.info(f"🔧 Starting TO address edit - user_data keys: {list(context.user_data.keys())}")
        
        # Edit to address
        context.user_data['editing_to_address'] = True
        
        # 🚀 PERFORMANCE: Send message in background
        async def send_edit_prompt():
            bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                "📥 Редактирование адреса получателя\n\nШаг 1/7: Имя получателя\nНапример: Jane Doe"
            ))
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
        
        asyncio.create_task(send_edit_prompt())
        logger.info("✅ Returning TO_NAME state for editing")
        return TO_NAME
    
    if query.data == 'edit_parcel':
        # Mark previous message as selected (non-blocking)
        # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

        old_prompt_text = context.user_data.get('last_bot_message_text', '')

        asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
        
        logger.info(f"🔧 Starting PARCEL edit - user_data keys: {list(context.user_data.keys())}")
        
        # Edit parcel dimensions
        context.user_data['editing_parcel'] = True
        
        # 🚀 PERFORMANCE: Send message in background
        async def send_edit_prompt():
            bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                "📦 Редактирование посылки\n\nВведите вес посылки в фунтах:\nНапример: 5 или 2.5"
            ))
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
        
        asyncio.create_task(send_edit_prompt())
        logger.info("✅ Returning PARCEL_WEIGHT state for editing")
        return PARCEL_WEIGHT
    
    if query.data == 'back_to_confirmation':
        # Return to confirmation screen
        return await show_data_confirmation(update, context)
