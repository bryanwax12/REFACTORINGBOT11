"""
Common handlers for Telegram bot commands and callbacks
Includes: start, help, faq, button routing, and utility functions
"""
import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import telegram.error

# Semaphore to limit concurrent background tasks (max 10)
_background_task_semaphore = asyncio.Semaphore(10)

# Logger
logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS ====================

async def safe_telegram_call(coro, timeout=10, error_message="❌ Превышено время ожидания. Попробуйте еще раз.", chat_id=None):
    """
    Universal wrapper with timeout protection
    Fast responses + error handling
    
    Usage:
        await safe_telegram_call(update.message.reply_text("Hello"), chat_id=update.effective_chat.id)
    """
    try:
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


async def mark_message_as_selected(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt_text: str = None):
    """
    Add checkmark ✅ to selected message and remove buttons
    Runs async - doesn't block bot response
    
    Args:
        update: Telegram update
        context: Bot context
        prompt_text: EXPLICIT prompt text to mark (avoids race condition with context updates)
                     If None, falls back to context.user_data['last_bot_message_text']
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
            except Exception as e:
                # Silently ignore "Message can't be edited" and similar errors
                pass
            return
        
        # Handle text input messages
        if update.effective_message and 'last_bot_message_id' in context.user_data:
            last_msg_id = context.user_data.get('last_bot_message_id')
            
            # ✅ 2025 FIX: Use explicit prompt_text to avoid race condition
            last_text = prompt_text if prompt_text is not None else context.user_data.get('last_bot_message_text', '')
            
            if not last_msg_id or not last_text:
                return
            
            try:
                # Add checkmark to last bot message
                if not last_text.startswith("✅"):
                    new_text = f"✅ {last_text}"
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=last_msg_id,
                        text=new_text,
                        reply_markup=None
                    )
                else:
                    # Just remove buttons if checkmark already exists
                    await context.bot.edit_message_reply_markup(
                        chat_id=update.effective_chat.id,
                        message_id=last_msg_id,
                        reply_markup=None
                    )
            except Exception as e:
                # Silently ignore "Message can't be edited" and similar errors
                # These are normal when message is too old or already edited
                pass
        
    except Exception:
        pass


async def check_user_blocked(telegram_id: int) -> bool:
    """Check if user is blocked from using the bot (ALWAYS fetch fresh from DB!)"""
    from repositories import get_user_repo
    user_repo = get_user_repo()
    is_blocked_result = await user_repo.is_blocked(telegram_id)
    if is_blocked_result:
        logger.warning(f"🚫 User {telegram_id} is blocked")
    return is_blocked_result


async def send_blocked_message(update: Update):
    """Send blocked message to user"""
    from utils.ui_utils import MessageTemplates
    message = MessageTemplates.user_blocked()
    
    if update.message:
        await safe_telegram_call(update.message.reply_text(message, parse_mode='Markdown'))
    elif update.callback_query:
        await safe_telegram_call(update.callback_query.message.reply_text(message, parse_mode='Markdown'))


async def check_maintenance_mode(update: Update) -> bool:
    """
    Check if bot is in maintenance mode and user is not admin
    DEPRECATED: Use utils.maintenance_check.check_maintenance_mode instead
    This wrapper is kept for backwards compatibility
    """
    from utils.maintenance_check import check_maintenance_mode as _check
    return await _check(update)


# ==================== COMMAND HANDLERS ====================

from utils.handler_decorators import with_user_session, safe_handler, with_typing_action

@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=True, require_session=False)  # Check blocking FIRST
@with_typing_action()  # Then send typing action if not blocked
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start command handler - Main menu
    Handles both direct command and callback query
    
    Decorators handle:
    - User creation/retrieval + blocking check
    - Error handling
    - Typing indicator
    """
    telegram_id = update.effective_user.id if update.effective_user else None
    logger.info(f"📍 START command from user {telegram_id}")
    
    # CRITICAL: Double-check blocked status (in case decorator didn't run in webhook mode)
    from repositories import get_user_repo
    user_repo = get_user_repo()
    is_blocked = await user_repo.is_blocked(telegram_id)
    logger.info(f"🔍 Block check for user {telegram_id}: is_blocked={is_blocked}")
    
    if is_blocked:
        logger.error(f"🚫🚫🚫 User {telegram_id} is BLOCKED - denying access in start_command")
        await send_blocked_message(update)
        return ConversationHandler.END
    
    # NOTE: Maintenance mode is already checked by @safe_handler decorator
    # No need to check again here
    
    # Get user from context (injected by decorator)
    user = context.user_data.get('db_user')
    if not user:
        logger.error("db_user not found in context!")
        return ConversationHandler.END
    
    # CRITICAL: Clear any active conversation state to prevent dialog conflicts
    # This ensures /start always brings user to main menu, not mid-conversation
    try:
        logger.info(f"🧹 Clearing conversation state for user {update.effective_user.id}")
        # Save db_user before clearing
        saved_user = user
        # Clear ALL conversation data for this user
        context.user_data.clear()
        # Restore db_user for this handler to use
        context.user_data['db_user'] = saved_user
        user = saved_user
        
        # Additionally, signal to ConversationHandler that we want to end any active conversation
        # This happens via the return value ConversationHandler.END at the end of this function
    except Exception as e:
        logger.error(f"Error clearing conversation state: {e}")
    # ALWAYS get fresh balance from DB (not from cached user)
    from server import db
    telegram_id = user.get('telegram_id')
    fresh_user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0, "balance": 1, "first_name": 1})
    user_balance = fresh_user.get('balance', 0.0) if fresh_user else 0.0
    first_name = user.get('first_name', 'Пользователь')
    
    logger.info(f"💰 Fresh balance from DB: ${user_balance:.2f}")
    
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    # Import UI utilities
    from utils.ui_utils import MessageTemplates, get_main_menu_keyboard
    
    welcome_message = MessageTemplates.welcome(first_name)
    reply_markup = get_main_menu_keyboard(user_balance)
    
    # Send welcome message with inline keyboard
    bot_msg = await send_method(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Save last bot message context for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = welcome_message
    
    # CRITICAL: Return END to exit any active conversation
    return ConversationHandler.END


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=False)  # Check blocking FIRST
@with_typing_action()  # Then send typing action if not blocked
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help command handler
    Handles both direct command and callback query
    
    Decorators handle:
    - User session management + blocking check
    - Error handling
    - Typing indicator
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


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=False)  # Check blocking FIRST
@with_typing_action()  # Then send typing action if not blocked
async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    FAQ command handler
    Handles both direct command and callback query
    
    Decorators handle:
    - User session management + blocking check
    - Error handling
    - Typing indicator
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
    telegram_id = query.from_user.id
    logger.info(f"🔵 Button: {query.data} from user {telegram_id}")
    await safe_telegram_call(query.answer())
    
    # CRITICAL: Check if user is blocked FIRST (before maintenance check)
    logger.info(f"🔍 Checking block status for user {telegram_id} in button_callback")
    if await check_user_blocked(telegram_id):
        logger.error(f"🚫🚫🚫 User {telegram_id} is BLOCKED - denying button access")
        await send_blocked_message(update)
        return ConversationHandler.END
    logger.info(f"✅ User {telegram_id} not blocked, proceeding with button")
    
    # Check if bot is in maintenance mode SECOND
    if await check_maintenance_mode(update):
        from utils.ui_utils import MessageTemplates
        await query.message.reply_text(
            MessageTemplates.maintenance_mode(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
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
        logger.info("🔵 Calling my_balance_command from button_callback")
        from handlers.payment_handlers import my_balance_command
        await my_balance_command(update, context)
        logger.info("✅ my_balance_command finished")
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
    elif query.data == 'continue_order':
        # Return to order confirmation after balance top-up
        asyncio.create_task(mark_message_as_selected(update, context))
        telegram_id = query.from_user.id
        
        # Check if user has pending order
        pending_order = await db.pending_orders.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        if pending_order and pending_order.get('selected_rate'):
            # Show order confirmation with rates
            from handlers.order_flow.confirmation import show_data_confirmation
            await show_data_confirmation(update, context)
        else:
            # No pending order, start new one
            await safe_telegram_call(query.message.reply_text(
                "У вас нет активного заказа. Начните новый заказ из главного меню!",
                parse_mode='Markdown'
            ))
            await start_command(update, context)
    elif query.data == 'new_order':
        # ✅ FIX: Don't handle here - ConversationHandler will handle it (group=0 priority)
        # This prevents duplicate message sending
        pass
    elif query.data == 'cancel_order':
        # Import from order_flow.cancellation module
        from handlers.order_flow.cancellation import cancel_order
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



# ==================== ORPHANED BUTTON HANDLERS ====================

async def handle_orphaned_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses that are not caught by any active handler (orphaned buttons)"""
    query = update.callback_query
    
    # Ignore menu buttons (start, help, etc)
    if query.data in ['start', 'help', 'contact_admin', 'my_templates']:
        return
    
    logger.info(f"Orphaned button detected: {query.data} from user {update.effective_user.id}")
    
    await safe_telegram_call(query.answer("⚠️ Этот заказ уже завершён"))
    await safe_telegram_call(query.message.reply_text(
        "⚠️ *Этот заказ уже завершён или отменён.*\n\n"
        "Для создания нового заказа используйте меню в нижней части экрана.",
        parse_mode='Markdown'
    ))


async def check_stale_interaction(query, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if button press is from an old/completed interaction"""
    
    logger.debug(f"🔍 check_stale_interaction START: query.data={query.data if query else 'None'}")
    
    logger.info(f"check_stale_interaction called - user_data keys: {list(context.user_data.keys())}")
    
    # Check for rapid multiple clicks (debouncing)
    from utils.telegram_utils import is_button_click_allowed
    
    user_id = query.from_user.id
    button_data = query.data
    
    if not is_button_click_allowed(user_id, button_data):
        await safe_telegram_call(query.answer("⚠️ Пожалуйста, подождите..."))
        return True  # Block this interaction
    
    # If user_data is completely empty, it's likely a stale button from a completed order
    if not context.user_data or len(context.user_data) == 0:
        logger.info("Stale interaction detected - empty user_data, silently ignoring")
        # Silently ignore stale button clicks - just answer the callback
        await safe_telegram_call(query.answer())
        return True
    
    # If user_data exists but has no order-related data, it's also stale
    order_data_keys = ['from_name', 'to_name', 'parcel_weight', 'selected_rate']
    has_order_data = any(key in context.user_data for key in order_data_keys)
    
    logger.debug(f"🔍 check_stale_interaction: user_data keys={list(context.user_data.keys())[:10]}, has_order_data={has_order_data}")
    logger.info(f"Order data check: keys in user_data={list(context.user_data.keys())}, has_order_data={has_order_data}")
    
    if not has_order_data:
        logger.warning("⚠️ Blocking stale interaction - no order data")
        logger.info("Stale interaction detected - no order data in user_data, silently ignoring")
        await safe_telegram_call(query.answer())
        return True
    
    logger.debug("✅ Stale check passed, proceeding with action")
    return False
    
    # Check if order was already completed (has order_completed flag)
    if context.user_data.get('order_completed'):
        logger.info("Stale interaction detected - order_completed flag set, silently ignoring")
        # Silently ignore stale button clicks - just answer the callback
        await safe_telegram_call(query.answer())
        return True
    
    logger.info("Interaction is valid - proceeding")
    return False



# ==================== NAVIGATION HELPERS ====================

async def check_data_from_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to data confirmation screen from cancel dialog"""
    from handlers.order_flow.confirmation import show_data_confirmation
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Go back to data confirmation screen
    return await show_data_confirmation(update, context)


async def return_to_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order after cancel button - restore exact screen"""
    from utils.ui_utils import OrderStepMessages, get_cancel_keyboard
    from server import FROM_NAME, STATE_NAMES
    import asyncio
    
    logger.info(f"return_to_order called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Get the state we were in when cancel was pressed
    last_state = context.user_data.get('last_state')
    
    logger.info(f"return_to_order: last_state = {last_state}, type = {type(last_state)}")
    logger.info(f"return_to_order: user_data keys = {list(context.user_data.keys())}")
    
    # If no last_state - just continue
    if last_state is None:
        logger.warning("return_to_order: No last_state found!")
        await safe_telegram_call(query.message.reply_text("Продолжаем оформление заказа..."))
        return FROM_NAME
    
    # If last_state is a number (state constant), we need the string name
    # Check if it's a string (state name) or int (state constant)
    if isinstance(last_state, int):
        # It's a state constant - return it directly
        keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(str(last_state))
        logger.warning(f"return_to_order: last_state is int ({last_state}), should be string!")
        
        # Show next step
        reply_markup = get_cancel_keyboard()
        
        # 🚀 PERFORMANCE: Send message in background
        async def send_continue():
            bot_msg = await safe_telegram_call(query.message.reply_text(
                message_text if message_text else "Продолжаем оформление заказа...",
                reply_markup=reply_markup
            ))
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
                context.user_data['last_bot_message_text'] = message_text if message_text else "Продолжаем..."
        
        asyncio.create_task(send_continue())
        
        return last_state
    
    # last_state is a string (state name like "FROM_CITY")
    keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(last_state)
    
    # 🚀 PERFORMANCE: Send message in background
    async def send_return():
        if keyboard:
            bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=keyboard))
        else:
            reply_markup = get_cancel_keyboard()
            bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        
        # Save context
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
    
    asyncio.create_task(send_return())
    
    # Get state constant from state name
    state_constant = STATE_NAMES.get(last_state, FROM_NAME)
    logger.info(f"return_to_order: Returning state {state_constant} for state name '{last_state}'")
    
    return state_constant
