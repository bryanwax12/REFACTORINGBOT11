"""
Order Flow: Data Confirmation Handlers
Handles order data confirmation, editing, and template saving
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def show_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show summary of entered data with edit option"""
    from server import CONFIRM_DATA
    from utils.ui_utils import DataConfirmationUI
    
    data = context.user_data
    
    # Format the summary message using UI utils
    message = DataConfirmationUI.confirmation_header()
    message += DataConfirmationUI.format_address_section("Отправитель", data, "from")
    message += DataConfirmationUI.format_address_section("Получатель", data, "to")
    message += DataConfirmationUI.format_parcel_section(data)
    
    # Build keyboard using UI utils
    reply_markup = DataConfirmationUI.build_confirmation_keyboard()
    
    # Save last bot message context for button protection
    bot_msg = await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
    
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
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Prompt for template name
    await safe_telegram_call(query.message.reply_text(
        TemplateManagementUI.template_name_prompt()
    ))
    
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
