"""
Template Handlers
Manages address templates for quick order creation
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Template management functions extracted from server.py
# These handlers allow users to save, view, edit, delete and use address templates


async def my_templates_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show user's saved templates menu
    """
    from server import db, safe_telegram_call, mark_message_as_selected
    from handlers.common_handlers import check_user_blocked, send_blocked_message
    
    query = update.callback_query
    if query:
        await safe_telegram_call(query.answer())
        telegram_id = query.from_user.id
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        telegram_id = update.effective_user.id
        send_method = update.message.reply_text
    
    # Check if blocked
    if await check_user_blocked(telegram_id):
        await send_blocked_message(update)
        return
    
    # Get user's templates
    from utils.ui_utils import TemplateMessages, get_back_to_menu_keyboard, get_templates_list_keyboard
    
    templates = await db.templates.find({"telegram_id": telegram_id}).to_list(100)
    
    if not templates:
        message = TemplateMessages.no_templates()
        reply_markup = get_back_to_menu_keyboard()
    else:
        message = TemplateMessages.templates_list(len(templates))
        reply_markup = get_templates_list_keyboard(templates)
    
    bot_message = await send_method(message, reply_markup=reply_markup)
    
    if bot_message:
        context.user_data['last_bot_message_id'] = bot_message.message_id
        context.user_data['last_bot_message_text'] = message


async def view_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    View template details
    
    Shows full address information and action buttons
    """
    # Import required functions
    from server import db, safe_telegram_call
    from utils.db_operations import find_template_by_id
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Extract template ID from callback data
    template_id = query.data.replace('template_view_', '')
    
    # Get template from database
    from utils.ui_utils import TemplateMessages, get_template_view_keyboard
    
    template = await find_template_by_id(template_id)
    
    if not template:
        await query.message.reply_text(TemplateMessages.template_not_found())
        return
    
    # Format template info
    message = TemplateMessages.template_details(template)
    reply_markup = get_template_view_keyboard(template_id)
    
    await query.message.reply_text(message, reply_markup=reply_markup)


async def use_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Use template to start order with pre-filled addresses
    """
    # Import required functions
    from server import db, safe_telegram_call
    from utils.db_operations import find_template_by_id
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_use_', '')
    
    from utils.ui_utils import TemplateMessages, get_cancel_keyboard
    
    template = await find_template_by_id(template_id)
    
    if not template:
        await query.message.reply_text(TemplateMessages.template_not_found())
        return
    
    # Load template data into context
    context.user_data['from_name'] = template.get('from_name')
    context.user_data['from_address'] = template.get('from_street1')
    context.user_data['from_address2'] = template.get('from_street2', '')
    context.user_data['from_city'] = template.get('from_city')
    context.user_data['from_state'] = template.get('from_state')
    context.user_data['from_zip'] = template.get('from_zip')
    context.user_data['from_phone'] = template.get('from_phone')
    
    context.user_data['to_name'] = template.get('to_name')
    context.user_data['to_address'] = template.get('to_street1')
    context.user_data['to_address2'] = template.get('to_street2', '')
    context.user_data['to_city'] = template.get('to_city')
    context.user_data['to_state'] = template.get('to_state')
    context.user_data['to_zip'] = template.get('to_zip')
    context.user_data['to_phone'] = template.get('to_phone')
    
    message = TemplateMessages.template_loaded(template.get('name'))
    reply_markup = get_cancel_keyboard()
    
    await query.message.reply_text(message, reply_markup=reply_markup)
    
    # Transition to parcel weight step
    from server import PARCEL_WEIGHT
    return PARCEL_WEIGHT


async def delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Confirm template deletion
    """
    # Import required functions
    from server import db, safe_telegram_call
    from utils.db_operations import find_template_by_id
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_delete_', '')
    
    from utils.ui_utils import TemplateMessages, get_template_delete_confirmation_keyboard
    
    template = await find_template_by_id(template_id)
    
    if not template:
        await query.message.reply_text(TemplateMessages.template_not_found())
        return
    
    message = TemplateMessages.confirm_delete(template.get('name'))
    reply_markup = get_template_delete_confirmation_keyboard(template_id)
    
    await query.message.reply_text(message, reply_markup=reply_markup)


async def confirm_delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Actually delete the template
    """
    # Import required functions
    from server import db, safe_telegram_call
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_confirm_delete_', '')
    
    from utils.ui_utils import TemplateMessages
    
    result = await db.templates.delete_one({"id": template_id})
    
    if result.deleted_count > 0:
        await query.message.reply_text(TemplateMessages.template_deleted())
    else:
        await query.message.reply_text(TemplateMessages.delete_error())
    
    # Return to templates menu
    await my_templates_menu(update, context)


async def rename_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start template rename flow
    """
    # Import required functions
    from server import safe_telegram_call
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_rename_', '')
    
    from utils.ui_utils import TemplateMessages, get_template_rename_keyboard
    
    # Save template ID for next step
    context.user_data['renaming_template_id'] = template_id
    
    message = TemplateMessages.rename_prompt()
    reply_markup = get_template_rename_keyboard(template_id)
    
    await query.message.reply_text(message, reply_markup=reply_markup)
    
    # Transition to TEMPLATE_RENAME state
    return "TEMPLATE_RENAME"


async def rename_template_save(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """
    Save new template name
    """
    from utils.ui_utils import TemplateMessages
    
    new_name = update.message.text.strip()
    
    if len(new_name) > 50:
        await update.message.reply_text(TemplateMessages.name_too_long())
        return
    
    template_id = context.user_data.get('renaming_template_id')
    
    if not template_id:
        await update.message.reply_text("❌ Ошибка: шаблон не найден")
        return
    
    # Update template name
    result = await db.templates.update_one(
        {"id": template_id},
        {"$set": {"name": new_name}}
    )
    
    if result.modified_count > 0:
        await update.message.reply_text(f"✅ Шаблон переименован в '{new_name}'")
    else:
        await update.message.reply_text("❌ Ошибка при переименовании")
    
    # Clear state
    context.user_data.pop('renaming_template_id', None)
    
    # Return END to exit conversation
    return "END"


# Helper function to save new template after successful order
async def save_order_as_template(telegram_id: int, template_name: str, order_data: dict, db):
    """
    Save order data as template for future use
    
    Args:
        telegram_id: User's Telegram ID
        template_name: Name for the template
        order_data: Order data with addresses
        db: Database connection
    
    Returns:
        str: Template ID if successful, None otherwise
    """
    try:
        from uuid import uuid4
        
        template = {
            "id": str(uuid4()),
            "telegram_id": telegram_id,
            "name": template_name,
            "from_name": order_data.get('from_name'),
            "from_street1": order_data.get('from_address'),
            "from_street2": order_data.get('from_address2', ''),
            "from_city": order_data.get('from_city'),
            "from_state": order_data.get('from_state'),
            "from_zip": order_data.get('from_zip'),
            "from_phone": order_data.get('from_phone'),
            "to_name": order_data.get('to_name'),
            "to_street1": order_data.get('to_address'),
            "to_street2": order_data.get('to_address2', ''),
            "to_city": order_data.get('to_city'),
            "to_state": order_data.get('to_state'),
            "to_zip": order_data.get('to_zip'),
            "to_phone": order_data.get('to_phone'),
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.templates.insert_one(template)
        logger.info(f"✅ Template saved for user {telegram_id}: {template_name}")
        
        return template['id']
        
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        return None



async def handle_template_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user to enter a new template name"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from server import TEMPLATE_NAME
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    await safe_telegram_call(query.message.reply_text(
        """📝 Введите новое название для шаблона:

Например: Доставка маме 2, Офис NY"""
    ))
    # Clear last_bot_message to prevent interfering with text input
    context.user_data.pop('last_bot_message_id', None)
    context.user_data.pop('last_bot_message_text', None)
    return TEMPLATE_NAME

