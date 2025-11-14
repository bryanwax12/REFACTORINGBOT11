"""
Common handlers for Telegram bot commands and callbacks
Includes: start, help, faq, button routing, and utility functions
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import telegram.error

# Logger
logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS ====================

async def safe_telegram_call(coro, timeout=10, error_message="❌ Превышено время ожидания. Попробуйте еще раз.", chat_id=None):
    """
    Universal wrapper with rate limiting and timeout protection
    Fast responses + ban prevention
    
    Usage:
        await safe_telegram_call(update.message.reply_text("Hello"), chat_id=update.effective_chat.id)
    """
    try:
        # Import rate_limiter from server module when needed
        from server import rate_limiter
        
        # Apply rate limiting if chat_id provided
        if chat_id:
            await rate_limiter.acquire(chat_id)
        
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Telegram API timeout after {timeout}s")
        return None
    except telegram.error.RetryAfter as e:
        # Telegram rate limit hit - wait and retry
        logger.warning(f"Telegram rate limit: waiting {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception as e:
        logger.error(f"Telegram API error: {e}")
        return None


async def mark_message_as_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Add checkmark ✅ to selected message and remove buttons
    Runs async - doesn't block bot response
    """
    try:
        # Handle callback query (button press)
        if update.callback_query:
            message = update.callback_query.message
            try:
                # Get current text and add checkmark if not already there
                current_text = message.text or ""
                if not current_text.startswith("✅"):
                    new_text = f"✅ {current_text}"
                    # Edit message with checkmark and remove buttons
                    await message.edit_text(text=new_text, reply_markup=None)
                else:
                    # Just remove buttons if checkmark already exists
                    await message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return
        
        # Handle text input messages
        if update.message and 'last_bot_message_id' in context.user_data:
            last_msg_id = context.user_data.get('last_bot_message_id')
            last_text = context.user_data.get('last_bot_message_text', '')
            
            if not last_msg_id:
                return
            
            try:
                # Add checkmark to last bot message
                if not last_text.startswith("✅"):
                    new_text = f"✅ {last_text}"
                    await safe_telegram_call(context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=last_msg_id,
                        text=new_text,
                        reply_markup=None
                    ))
                else:
                    # Just remove buttons if checkmark already exists
                    await safe_telegram_call(context.bot.edit_message_reply_markup(
                        chat_id=update.effective_chat.id,
                        message_id=last_msg_id,
                        reply_markup=None
                    ))
            except Exception:
                pass
        
    except Exception:
        pass


async def check_user_blocked(telegram_id: int) -> bool:
    """Check if user is blocked"""
    from repositories import get_user_repo
    user_repo = get_user_repo()
    user = await user_repo.find_by_telegram_id(telegram_id)
    return user.get('blocked', False) if user else False


async def send_blocked_message(update: Update):
    """Send blocked message to user"""
    from utils.ui_utils import MessageTemplates
    message = MessageTemplates.user_blocked()
    
    if update.message:
        await safe_telegram_call(update.message.reply_text(message, parse_mode='Markdown'))
    elif update.callback_query:
        await safe_telegram_call(update.callback_query.message.reply_text(message, parse_mode='Markdown'))


async def check_maintenance_mode(update: Update) -> bool:
    """Check if bot is in maintenance mode and user is not admin"""
    try:
        from server import db, ADMIN_TELEGRAM_ID
        settings = await db.settings.find_one({"key": "maintenance_mode"})
        is_maintenance = settings.get("value", False) if settings else False
        
        # Allow admin to use bot even in maintenance mode
        if is_maintenance and str(update.effective_user.id) != ADMIN_TELEGRAM_ID:
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking maintenance mode: {e}")
        return False


# ==================== COMMAND HANDLERS ====================

from utils.handler_decorators import with_user_session, safe_handler, with_typing_action

@safe_handler(fallback_state=ConversationHandler.END)
@with_typing_action()
@with_user_session(create_user=True, require_session=False)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start command handler - Main menu
    Handles both direct command and callback query
    
    Decorators handle:
    - User creation/retrieval + blocking check
    - Error handling
    - Typing indicator
    """
    # CRITICAL: Clear old conversation state for this user to prevent stuck dialogs
    try:
        from server import db
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        conv_key = str((chat_id, user_id))
        
        # Clear from MongoDB
        doc = await db.bot_persistence.find_one({"_id": "conversation_order_conv_handler"})
        if doc and 'data' in doc and conv_key in doc['data']:
            del doc['data'][conv_key]
            await db.bot_persistence.update_one(
                {"_id": "conversation_order_conv_handler"},
                {"$set": {"data": doc['data'], "updated_at": datetime.now(timezone.utc)}}
            )
            logger.info(f"🧹 Cleared old conversation state for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing conversation state: {e}")
    
    # Get user from context (injected by decorator)
    user = context.user_data['db_user']
    user_balance = user.get('balance', 0.0)
    first_name = user.get('first_name', 'Пользователь')
    
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    # Check if bot is in maintenance mode
    if await check_maintenance_mode(update):
        from utils.ui_utils import MessageTemplates
        await send_method(
            MessageTemplates.maintenance_mode(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
        
    # Import UI utilities
    from utils.ui_utils import MessageTemplates, get_main_menu_keyboard
    
    welcome_message = MessageTemplates.welcome(first_name)
    reply_markup = get_main_menu_keyboard(user_balance)
    
    # Send welcome message with inline keyboard
    bot_msg = await send_method(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Save last bot message context for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = welcome_message


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help command handler
    Handles both direct command and callback query
    """
    from server import ADMIN_TELEGRAM_ID
    from utils.ui_utils import MessageTemplates, get_help_keyboard
    
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    help_text = MessageTemplates.help_text()
    reply_markup = get_help_keyboard(ADMIN_TELEGRAM_ID)
    bot_msg = await send_method(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Save message ID and text for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = help_text


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    FAQ command handler
    Handles both direct command and callback query
    """
    from utils.ui_utils import MessageTemplates, get_back_to_menu_keyboard
    
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    faq_text = MessageTemplates.faq_text()
    reply_markup = get_back_to_menu_keyboard()
    bot_msg = await send_method(faq_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Save message ID and text for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = faq_text


# ==================== BUTTON CALLBACK ROUTER ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main callback query router for inline keyboard buttons
    Routes button presses to appropriate handlers
    """
    from server import db
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    if query.data == 'start' or query.data == 'main_menu':
        # Check if user has pending order
        telegram_id = query.from_user.id
        pending_order = await db.pending_orders.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        if pending_order and pending_order.get('selected_rate'):
            # Show warning about losing order data
            from utils.ui_utils import MessageTemplates, get_exit_confirmation_keyboard
            asyncio.create_task(mark_message_as_selected(update, context))
            
            order_amount = pending_order.get('selected_rate', {}).get('shipmentCost', 0.0)
            warning_text = MessageTemplates.exit_warning(order_amount)
            reply_markup = get_exit_confirmation_keyboard()
            
            bot_msg = await safe_telegram_call(query.message.reply_text(
                warning_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            ))
            
            # Save message context for button protection
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = warning_text
            return
        
        await start_command(update, context)
    elif query.data == 'my_balance':
        # Import from payment_handlers module
        from handlers.payment_handlers import my_balance_command
        await my_balance_command(update, context)
    elif query.data == 'my_templates':
        # Import from template_handlers module
        from handlers.template_handlers import my_templates_menu
        await my_templates_menu(update, context)
    elif query.data == 'help':
        await help_command(update, context)
    elif query.data == 'faq':
        await faq_command(update, context)
    elif query.data == 'confirm_exit_to_menu':
        # User confirmed exit to main menu - clear pending order
        asyncio.create_task(mark_message_as_selected(update, context))
        telegram_id = query.from_user.id
        await db.pending_orders.delete_one({"telegram_id": telegram_id})
        context.user_data.clear()
        await start_command(update, context)
    elif query.data == 'new_order':
        # Import from server (will be moved to order_handlers later)
        from server import new_order_start
        # Starting new order - this is intentional, so clear previous data
        context.user_data.clear()
        await new_order_start(update, context)
    elif query.data == 'cancel_order':
        # Import from order_handlers module
        from handlers.order_handlers import cancel_order
        # Check if this is an orphaned cancel button (order already completed)
        if context.user_data.get('order_completed'):
            logger.info(f"Orphaned cancel button detected from user {update.effective_user.id}")
            await safe_telegram_call(query.answer("⚠️ Этот заказ уже завершён"))
            await safe_telegram_call(query.message.reply_text(
                "⚠️ *Этот заказ уже завершён или отменён.*\n\n"
                "Для создания нового заказа используйте меню в нижней части экрана.",
                parse_mode='Markdown'
            ))
        else:
            # Always allow cancel - even if context is empty (user just started)
            await cancel_order(update, context)
    elif query.data.startswith('create_label_'):
        # Import from server (will be moved to order_handlers later)
        from server import handle_create_label_request
        # Handle create label button
        order_id = query.data.replace('create_label_', '')
        await handle_create_label_request(update, context, order_id)
