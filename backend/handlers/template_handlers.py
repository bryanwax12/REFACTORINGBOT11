"""
Template Handlers
Manages address templates for quick order creation
"""
import asyncio
import logging
from telegram import Update

# ⚡ Performance: Import preloaded keyboards
from utils.ui_utils import PRELOADED_BACK_TO_MENU_KEYBOARD
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
        reply_markup = PRELOADED_BACK_TO_MENU_KEYBOARD  # ⚡ Performance
        bot_message = await send_method(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        message = TemplateMessages.templates_list(len(templates), max_templates=10)
        reply_markup = get_templates_list_keyboard(templates)
        bot_message = await send_method(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    if bot_message:
        context.user_data['last_bot_message_id'] = bot_message.message_id
        context.user_data['last_bot_message_text'] = message


async def view_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    View template details
    
    Shows full address information and action buttons
    """
    # Import required functions
    from server import safe_telegram_call
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    logger.info(f"🔵 view_template CALLED with callback_data: {query.data}")
    await safe_telegram_call(query.answer())
    
    # Remove buttons from template list message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.debug(f"Could not remove template list buttons: {e}")
    
    # Extract template ID from callback data
    template_id = query.data.replace('template_view_', '')
    
    logger.info(f"📋 Viewing template: template_id={template_id}")
    
    # Get template from database
    from utils.ui_utils import TemplateMessages, get_template_view_keyboard
    from server import db
    
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
    if not template:
        logger.error(f"❌ Template {template_id} not found")
        asyncio.create_task(query.message.reply_text(TemplateMessages.template_not_found()))
        return
    
    logger.info(f"✅ Template found: {template.get('name')}")
    
    # Format template info
    message = TemplateMessages.template_details(template)
    reply_markup = get_template_view_keyboard(template_id)
    
    # 🚀 PERFORMANCE: Send message in background
    async def send_template_view():
        bot_msg = await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message
    
    asyncio.create_task(send_template_view())
    
    # Return TEMPLATE_VIEW state
    from server import TEMPLATE_VIEW
    return TEMPLATE_VIEW


async def use_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Use template to start order with pre-filled addresses
    """
    # Import required functions
    from server import safe_telegram_call, db
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_use_', '')
    
    logger.info(f"🔵 use_template called with template_id: {template_id}")
    
    from utils.ui_utils import TemplateMessages, get_cancel_keyboard, OrderStepMessages
    
    # Get template directly from DB
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
    if not template:
        logger.error(f"❌ Template {template_id} not found")
        asyncio.create_task(query.message.reply_text(TemplateMessages.template_not_found()))
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
    
    logger.info(f"✅ Template data loaded into context: from_name={context.user_data.get('from_name')}, to_name={context.user_data.get('to_name')}")
    
    # Remove buttons from template view message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.debug(f"Could not remove template buttons: {e}")
    
    message = TemplateMessages.template_loaded(template.get('name'))
    
    # Send prompt for weight input
    weight_prompt = f"{message}\n\n{OrderStepMessages.PARCEL_WEIGHT}"
    
    # Save UI state ONLY (NOT conversation state - ConversationHandler manages that)
    from server import PARCEL_WEIGHT
    context.user_data['last_bot_message_text'] = weight_prompt
    logger.info(f"✅ use_template: transitioning to PARCEL_WEIGHT")
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_weight_prompt():
        bot_msg = await query.message.reply_text(weight_prompt)
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
    
    asyncio.create_task(send_weight_prompt())
    
    # Transition to parcel weight step
    logger.info(f"🔵 use_template returning PARCEL_WEIGHT state (value: {PARCEL_WEIGHT})")
    return PARCEL_WEIGHT


async def delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Confirm template deletion
    """
    # Import required functions
    from server import safe_telegram_call, db
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_delete_', '')
    
    logger.info(f"🗑️ Delete template requested: template_id={template_id}")
    
    # Remove buttons from template view message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.debug(f"Could not remove template buttons: {e}")
    
    from utils.ui_utils import TemplateMessages, get_template_delete_confirmation_keyboard
    
    # Get template directly from DB
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
    if not template:
        logger.error(f"❌ Template {template_id} not found")
        asyncio.create_task(query.message.reply_text(TemplateMessages.template_not_found()))
        return
    
    logger.info(f"✅ Template found: {template.get('name')}")
    
    message = TemplateMessages.confirm_delete(template.get('name'))
    reply_markup = get_template_delete_confirmation_keyboard(template_id)
    
    # Send confirmation message
    async def send_confirmation():
        bot_msg = await query.message.reply_text(message, reply_markup=reply_markup)
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message
    
    asyncio.create_task(send_confirmation())


async def confirm_delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Actually delete the template
    """
    # Import required functions
    from server import db, safe_telegram_call
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_confirm_delete_', '')
    
    logger.info(f"🗑️ Confirming template deletion: template_id={template_id}")
    
    from utils.ui_utils import TemplateMessages
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    result = await db.templates.delete_one({"id": template_id})
    
    if result.deleted_count > 0:
        logger.info(f"✅ Template {template_id} deleted successfully")
        
        # Remove buttons from confirmation message
        try:
            await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
        except Exception as e:
            logger.debug(f"Could not remove confirmation buttons: {e}")
        
        # Show success message with navigation buttons
        keyboard = [
            [InlineKeyboardButton("📋 Мои шаблоны", callback_data='my_templates')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            TemplateMessages.template_deleted(),
            reply_markup=reply_markup
        )
    else:
        logger.error(f"❌ Failed to delete template {template_id}")
        await query.message.reply_text(TemplateMessages.delete_error())


async def rename_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start template rename flow
    """
    # Import required functions
    from server import safe_telegram_call, TEMPLATE_RENAME
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    template_id = query.data.replace('template_rename_', '')
    
    logger.info(f"🔄 Starting template rename for template_id: {template_id}")
    
    # Remove buttons from template view message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.debug(f"Could not remove template buttons: {e}")
    
    from utils.ui_utils import TemplateMessages, get_template_rename_keyboard
    
    # Save template ID for next step
    context.user_data['renaming_template_id'] = template_id
    
    message = TemplateMessages.rename_prompt()
    reply_markup = get_template_rename_keyboard(template_id)
    
    # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
    async def send_rename_prompt():
        bot_msg = await query.message.reply_text(message, reply_markup=reply_markup)
        if bot_msg:
            context.user_data['rename_prompt_message_id'] = bot_msg.message_id
            context.user_data['rename_prompt_chat_id'] = bot_msg.chat_id
    
    asyncio.create_task(send_rename_prompt())
    
    # Transition to TEMPLATE_RENAME state
    logger.info(f"✅ Returning TEMPLATE_RENAME state (value: {TEMPLATE_RENAME})")
    return TEMPLATE_RENAME


async def rename_template_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Save new template name
    """
    # Import required functions
    from server import db
    from utils.ui_utils import TemplateMessages
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("🟢 rename_template_save CALLED")
    logger.info(f"   User ID: {update.effective_user.id}")
    logger.info(f"   Message text: {update.message.text}")
    logger.info(f"   context.user_data keys: {list(context.user_data.keys())}")
    
    # Remove buttons from the prompt message using bot instance
    rename_prompt_msg_id = context.user_data.get('rename_prompt_message_id')
    rename_prompt_chat_id = context.user_data.get('rename_prompt_chat_id')
    
    if rename_prompt_msg_id and rename_prompt_chat_id:
        try:
            # Use the bot from context
            bot = context.bot
            await bot.edit_message_reply_markup(
                chat_id=rename_prompt_chat_id,
                message_id=rename_prompt_msg_id,
                reply_markup=None
            )
            logger.info(f"✅ Removed buttons from prompt message {rename_prompt_msg_id}")
        except Exception as e:
            logger.warning(f"Could not remove prompt buttons: {e}")
    else:
        logger.warning("No prompt message IDs found in context")
    
    new_name = update.message.text.strip()
    
    if len(new_name) > 50:
        logger.warning(f"❌ Template name too long: {len(new_name)} chars")
        asyncio.create_task(update.message.reply_text(TemplateMessages.name_too_long()))
        return
    
    template_id = context.user_data.get('renaming_template_id')
    
    if not template_id:
        logger.error("❌ No template_id in context.user_data")
        await update.message.reply_text("❌ Ошибка: шаблон не найден")
        return
    
    logger.info(f"📝 Updating template {template_id} with new name: {new_name}")
    
    # Update template name
    result = await db.templates.update_one(
        {"id": template_id},
        {"$set": {"name": new_name}}
    )
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    if result.modified_count > 0:
        logger.info("✅ Template renamed successfully")
        
        # Create keyboard with navigation buttons
        keyboard = [
            [InlineKeyboardButton("📋 Вернуться к шаблонам", callback_data='my_templates')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Шаблон переименован в '{new_name}'",
            reply_markup=reply_markup
        )
    else:
        logger.error(f"❌ Template update failed - modified_count: {result.modified_count}")
        
        # Even on error, provide navigation
        keyboard = [
            [InlineKeyboardButton("📋 Вернуться к шаблонам", callback_data='my_templates')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ Ошибка при переименовании",
            reply_markup=reply_markup
        )
    
    # Clear state
    context.user_data.pop('renaming_template_id', None)
    context.user_data.pop('rename_prompt_message_id', None)
    context.user_data.pop('rename_prompt_chat_id', None)
    
    # Return END to exit conversation
    from telegram.ext import ConversationHandler
    logger.info("✅ Exiting template rename conversation")
    return ConversationHandler.END


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



async def edit_template_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show menu for editing template addresses
    """
    from server import safe_telegram_call, db
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Extract template_id - callback is 'template_edit_<id>' (not template_edit_from_ or template_edit_to_)
    template_id = query.data.replace('template_edit_', '')
    
    # Double check this is the main edit menu, not from/to specific
    if template_id.startswith('from_') or template_id.startswith('to_'):
        logger.error(f"Wrong handler called for {query.data}")
        return
    
    logger.info(f"📝 Edit template menu: template_id={template_id}")
    
    # Remove buttons from template view message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.debug(f"Could not remove template buttons: {e}")
    
    # Get template to show current name
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
    if not template:
        await query.message.reply_text("❌ Шаблон не найден")
        return
    
    # Create edit menu
    keyboard = [
        [InlineKeyboardButton("📤 Редактировать адрес отправителя", callback_data=f'template_edit_from_{template_id}')],
        [InlineKeyboardButton("📥 Редактировать адрес получателя", callback_data=f'template_edit_to_{template_id}')],
        [InlineKeyboardButton("🔙 Назад к шаблону", callback_data=f'template_view_{template_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""📝 *Редактирование шаблона*
━━━━━━━━━━━━━━━━━━━━

📁 *Шаблон:* {template.get('name')}

Выберите, что хотите отредактировать:"""
    
    await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')


async def edit_template_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """NOTE: This handler needs session_service but doesn't use decorators to avoid conflicts"""
    """
    Start editing FROM address in template
    """
    from server import safe_telegram_call, db, FROM_NAME
    from utils.ui_utils import get_cancel_keyboard
    from telegram.ext import ConversationHandler
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        template_id = query.data.replace('template_edit_from_', '')
        logger.info(f"🚀 edit_template_from_address STARTED for template_id: {template_id}")
        
        logger.info(f"📤 Editing FROM address for template: {template_id}")
        
        # Remove buttons
        try:
            await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
        except Exception as e:
            logger.debug(f"Could not remove buttons: {e}")
        
        # Load current template data into context
        template = await db.templates.find_one({"id": template_id}, {"_id": 0})
        
        if not template:
            await query.message.reply_text("❌ Шаблон не найден")
            return ConversationHandler.END
        
        # Clear any previous order data to prevent conflicts
        order_fields = ['from_name', 'from_address', 'from_address2', 'from_city', 'from_state', 'from_zip', 'from_phone',
                       'to_name', 'to_address', 'to_address2', 'to_city', 'to_state', 'to_zip', 'to_phone',
                       'parcel_weight', 'parcel_length', 'parcel_width', 'parcel_height']
        for field in order_fields:
            context.user_data.pop(field, None)
        
        # Save template ID and mark editing mode IN BOTH context AND DB session
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_template_from'] = True
        
        # CRITICAL: Save flags to DB session so they persist across handler calls
        from server import db
        user_id = update.effective_user.id
        from datetime import datetime, timezone
        
        # Save editing flags as TOP-LEVEL session fields (not in temp_data)
        # Use upsert to create session if it doesn't exist
        result = await db.user_sessions.update_one(
            {"user_id": user_id},
            {"$set": {
                "editing_template_id": template_id,
                "editing_template_from": True,
                "editing_template_to": False,
                "current_step": "FROM_NAME",
                "is_active": True,
                "timestamp": datetime.now(timezone.utc)
            }},
            upsert=True  # Create if doesn't exist
        )
        
        logger.info(f"📝 Session flags set: matched={result.matched_count}, modified={result.modified_count}, upserted={result.upserted_id}")
        
        logger.info(f"✅ FLAGS SET: editing_template_from=True, editing_template_id={template_id}")
        logger.info("📝 Flags saved to BOTH context.user_data AND DB session")
        
        # Load current FROM data
        context.user_data['from_name'] = template.get('from_name', '')
        context.user_data['from_address'] = template.get('from_street1', '')
        context.user_data['from_address2'] = template.get('from_street2', '')
        context.user_data['from_city'] = template.get('from_city', '')
        context.user_data['from_state'] = template.get('from_state', '')
        context.user_data['from_zip'] = template.get('from_zip', '')
        context.user_data['from_phone'] = template.get('from_phone', '')
        
        # Start FROM address input (no cancel button for template editing)
        
        # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
        async def send_edit_prompt():
            bot_msg = await query.message.reply_text(
                "📤 Редактирование адреса отправителя\n\nШаг 1/7: Имя отправителя\nНапример: John Smith"
            )
            
            # Save message ID to remove button later (both in context and DB)
            if bot_msg:
                context.user_data['last_prompt_message_id'] = bot_msg.message_id
                # Also save to DB session so it persists
                await db.user_sessions.update_one(
                    {"user_id": user_id, "is_active": True},
                    {"$set": {"last_prompt_message_id": bot_msg.message_id}}
                )
                logger.info(f"💾 Saved last_prompt_message_id={bot_msg.message_id} to both context and DB")
            else:
                logger.warning("⚠️ bot_msg is None, cannot save message_id")
        
        asyncio.create_task(send_edit_prompt())
        
        logger.info("✅ edit_template_from_address COMPLETED - returning FROM_NAME state")
        return FROM_NAME
    
    except Exception as e:
        logger.error(f"❌ ERROR in edit_template_from_address: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.message.reply_text(f"❌ Ошибка: {str(e)}")
        return ConversationHandler.END


async def edit_template_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start editing TO address in template
    """
    from server import safe_telegram_call, db, TO_NAME
    from utils.ui_utils import get_cancel_keyboard
    from telegram.ext import ConversationHandler
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        template_id = query.data.replace('template_edit_to_', '')
        logger.info(f"🚀 edit_template_to_address STARTED for template_id: {template_id}")
        
        logger.info(f"📥 Editing TO address for template: {template_id}")
        
        # Remove buttons
        try:
            await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
        except Exception as e:
            logger.debug(f"Could not remove buttons: {e}")
        
        # Load current template data into context
        template = await db.templates.find_one({"id": template_id}, {"_id": 0})
        
        if not template:
            await query.message.reply_text("❌ Шаблон не найден")
            return ConversationHandler.END
        
        # Save template ID and mark editing mode IN BOTH context AND DB session
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_template_to'] = True
        
        # CRITICAL: Save flags to DB session so they persist across handler calls
        user_id = update.effective_user.id
        from datetime import datetime, timezone
        
        result = await db.user_sessions.update_one(
            {"user_id": user_id},
            {"$set": {
                "editing_template_id": template_id,
                "editing_template_to": True,
                "editing_template_from": False,
                "current_step": "TO_NAME",
                "is_active": True,
                "timestamp": datetime.now(timezone.utc)
            }},
            upsert=True  # Create if doesn't exist
        )
        
        logger.info(f"✅ FLAGS SET: editing_template_to=True, editing_template_id={template_id}")
        logger.info(f"📝 Session flags set: matched={result.matched_count}, modified={result.modified_count}, upserted={result.upserted_id}")
        
        # Load current TO data
        context.user_data['to_name'] = template.get('to_name', '')
        context.user_data['to_address'] = template.get('to_street1', '')
        context.user_data['to_address2'] = template.get('to_street2', '')
        context.user_data['to_city'] = template.get('to_city', '')
        context.user_data['to_state'] = template.get('to_state', '')
        context.user_data['to_zip'] = template.get('to_zip', '')
        context.user_data['to_phone'] = template.get('to_phone', '')
        
        # Start TO address input (no cancel button for template editing)
        
        # 🚀 PERFORMANCE: Send message in background - don't wait for Telegram response
        async def send_edit_prompt():
            bot_msg = await query.message.reply_text(
                "📥 Редактирование адреса получателя\n\nШаг 1/7: Имя получателя\nНапример: Jane Doe"
            )
            
            # Save message ID to remove button later (both in context and DB)
            if bot_msg:
                context.user_data['last_prompt_message_id'] = bot_msg.message_id
                # Also save to DB session so it persists
                await db.user_sessions.update_one(
                    {"user_id": user_id, "is_active": True},
                    {"$set": {"last_prompt_message_id": bot_msg.message_id}}
                )
                logger.info(f"💾 Saved last_prompt_message_id={bot_msg.message_id} to both context and DB")
        
        asyncio.create_task(send_edit_prompt())
        
        logger.info("✅ edit_template_to_address COMPLETED - returning TO_NAME state")
        return TO_NAME
    
    except Exception as e:
        logger.error(f"❌ ERROR in edit_template_to_address: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.message.reply_text(f"❌ Ошибка: {str(e)}")
        return ConversationHandler.END
