"""
Order Flow: Data Confirmation Handlers
Handles order data confirmation, editing, and template saving
"""
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected, check_stale_interaction
from handlers.order_flow.cancellation import cancel_order


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
    message += DataConfirmationUI.format_parcel_section(data)
    message += DataConfirmationUI.format_address_section("Получатель", data, "to")
    message += "\n" + "─" * 30 + "\n"
    message += "✅ *Подтвердите данные или отредактируйте*"
    
    # Build keyboard using UI utils
    reply_markup = DataConfirmationUI.build_confirmation_keyboard()
    
    # Use effective_message to handle both regular messages and callback queries
    effective_msg = update.effective_message
    
    # Save last bot message context for button protection
    bot_msg = await safe_telegram_call(effective_msg.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown'))
    
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



async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu to select what to edit"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from utils.ui_utils import DataConfirmationUI
    from server import EDIT_MENU
    import asyncio
    
    query = update.callback_query
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    message = "✏️ Что вы хотите изменить?"
    
    # Build keyboard using UI utils
    reply_markup = DataConfirmationUI.build_edit_menu_keyboard()
    
    await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup))
    return EDIT_MENU




async def handle_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's choice on data confirmation"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🎯 handle_data_confirmation called with query.data={update.callback_query.data if update.callback_query else 'None'}")
    
    query = update.callback_query
    
    # Check for stale interaction
    if await check_stale_interaction(query, context):
        return ConversationHandler.END
    
    await safe_telegram_call(query.answer())
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    # Mark previous message as selected (remove buttons)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    if query.data == 'confirm_data':
        # User confirmed data, proceed to fetch rates
        logger.info("✅ User confirmed data, calling fetch_shipping_rates...")
        from handlers.order_flow.rates import fetch_shipping_rates
        return await fetch_shipping_rates(update, context)
    
    if query.data == 'save_template':
        # Save current order data as template
        await safe_telegram_call(query.message.reply_text(
            """💾 Сохранить как шаблон,
            Введите название для шаблона (до 30 символов):,
            *Например:* "Склад NY", "Доставка маме", "Офис",
            _Шаблон сохранит оба адреса для быстрого использования в будущем._""",
            parse_mode='Markdown',
        ))
        return TEMPLATE_NAME
    
    if query.data == 'edit_data':
        # Show edit menu
        return await show_edit_menu(update, context)
    
    if query.data == 'edit_addresses_error':
        # Show edit menu after rate error
        return await show_edit_menu(update, context)
    
    if query.data == 'edit_from_address':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit from address
        context.user_data['editing_from_address'] = True
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📤 Редактирование адреса отправителя\n\nШаг 1/6: Имя отправителя\nНапример: John Smith",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = STATE_NAMES[FROM_NAME]
        return FROM_NAME
    
    if query.data == 'edit_to_address':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit to address
        context.user_data['editing_to_address'] = True
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📥 Редактирование адреса получателя\n\nШаг 1/6: Имя получателя\nНапример: Jane Doe",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = STATE_NAMES[TO_NAME]
        return TO_NAME
    
    if query.data == 'edit_parcel':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit parcel dimensions
        context.user_data['editing_parcel'] = True
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📦 Редактирование посылки\n\nВведите вес посылки в фунтах:\nНапример: 5 или 2.5",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = STATE_NAMES[PARCEL_WEIGHT]
        return PARCEL_WEIGHT
    
    if query.data == 'back_to_confirmation':
        # Return to confirmation screen
        return await show_data_confirmation(update, context)
