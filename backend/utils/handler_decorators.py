"""
Handler Decorators
Wrappers for Telegram handlers with error handling and recovery
"""
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)


def safe_handler(fallback_state=ConversationHandler.END, error_message="❌ Произошла ошибка. Попробуйте позже."):
    """
    Decorator for Telegram handlers with automatic error handling
    
    Features:
    - Catches all exceptions
    - Logs error with context
    - Sends user-friendly error message
    - Returns fallback conversation state
    - Prevents bot hangs
    
    Usage:
        @safe_handler(fallback_state=ConversationHandler.END)
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Your handler code
            return NEXT_STATE
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                # Call original handler
                return await func(update, context, *args, **kwargs)
                
            except Exception as e:
                # Extract context info
                user_id = update.effective_user.id if update.effective_user else "Unknown"
                chat_id = update.effective_chat.id if update.effective_chat else "Unknown"
                handler_name = func.__name__
                
                # Log with full context
                logger.error(
                    f"❌ Error in handler '{handler_name}' "
                    f"(user_id={user_id}, chat_id={chat_id}): {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                
                # Send error message to user
                try:
                    if update.message:
                        await update.message.reply_text(error_message)
                    elif update.callback_query:
                        await update.callback_query.answer(error_message, show_alert=True)
                        await update.callback_query.message.reply_text(error_message)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
                
                # Return fallback state to prevent hang
                return fallback_state
        
        return wrapper
    return decorator


def track_handler_performance(threshold_seconds=2.0):
    """
    Decorator to track handler execution time
    
    Logs warning if handler takes too long
    
    Usage:
        @track_handler_performance(threshold_seconds=2.0)
        async def slow_handler(update, context):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            import time
            
            handler_name = func.__name__
            start_time = time.perf_counter()
            
            try:
                result = await func(update, context, *args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start_time
                
                if elapsed > threshold_seconds:
                    user_id = update.effective_user.id if update.effective_user else "Unknown"
                    logger.warning(
                        f"⏱️ SLOW HANDLER: '{handler_name}' took {elapsed:.2f}s "
                        f"(user_id={user_id}, threshold={threshold_seconds}s)"
                    )
                else:
                    logger.debug(f"✅ Handler '{handler_name}' completed in {elapsed:.2f}s")
        
        return wrapper
    return decorator


def require_session(fallback_state=ConversationHandler.END):
    """
    Decorator to ensure session exists before handler execution
    
    If session missing, creates new one and notifies user
    
    Usage:
        @require_session(fallback_state=ConversationHandler.END)
        async def handler_needs_session(update, context):
            # Session guaranteed to exist
            session = context.user_data['session']
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from session_manager import session_manager
            
            user_id = update.effective_user.id
            
            # Check if session exists
            session = await session_manager.get_session(user_id)
            
            if not session:
                logger.warning(f"⚠️ Session missing for user {user_id} in handler '{func.__name__}', creating new one")
                
                # Create new session
                session = await session_manager.get_or_create_session(user_id)
                
                # Notify user
                message = "⚠️ Сессия истекла. Начнем заново."
                if update.message:
                    await update.message.reply_text(message)
                elif update.callback_query:
                    await update.callback_query.answer(message, show_alert=True)
                
                return fallback_state
            
            # Store in context for handler
            context.user_data['session'] = session
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def with_typing_action():
    """
    Decorator to show "typing..." action during handler execution
    
    Provides visual feedback to user that bot is working
    
    Usage:
        @with_typing_action()
        async def long_running_handler(update, context):
            # Bot shows "typing..." while this runs
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            from telegram.constants import ChatAction
            
            # Send typing action
            if update.effective_chat:
                try:
                    await context.bot.send_chat_action(
                        chat_id=update.effective_chat.id,
                        action=ChatAction.TYPING
                    )
                except Exception as e:
                    logger.debug(f"Failed to send typing action: {e}")
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================
# COMBINED DECORATORS
# ============================================================

def robust_handler(
    fallback_state=ConversationHandler.END,
    error_message="❌ Произошла ошибка. Попробуйте позже.",
    track_performance=True,
    show_typing=True
):
    """
    All-in-one decorator combining multiple protections
    
    Features:
    - Error handling
    - Performance tracking
    - Typing indicator
    - Session validation (optional)
    
    Usage:
        @robust_handler(fallback_state=CONFIRM_DATA)
        async def my_handler(update, context):
            ...
    """
    def decorator(func):
        # Apply decorators in reverse order (inside-out)
        wrapped = func
        
        if show_typing:
            wrapped = with_typing_action()(wrapped)
        
        if track_performance:
            wrapped = track_handler_performance(threshold_seconds=2.0)(wrapped)
        
        wrapped = safe_handler(fallback_state, error_message)(wrapped)
        
        return wrapped
    
    return decorator


# ============================================================
# USAGE EXAMPLES
# ============================================================

"""
Example 1: Basic error handling
--------------------------------
from utils.handler_decorators import safe_handler
from telegram.ext import ConversationHandler

@safe_handler(fallback_state=ConversationHandler.END)
async def order_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If error occurs, user gets message and conversation ends
    name = update.message.text
    # ... process name
    return NEXT_STATE


Example 2: Performance tracking
--------------------------------
from utils.handler_decorators import track_handler_performance

@track_handler_performance(threshold_seconds=1.5)
async def fetch_rates_handler(update, context):
    # Logs warning if takes > 1.5s
    rates = await fetch_rates(...)
    return SHOW_RATES


Example 3: Combined robust handler
-----------------------------------
from utils.handler_decorators import robust_handler

@robust_handler(
    fallback_state=CONFIRM_DATA,
    error_message="❌ Не удалось обработать данные",
    track_performance=True,
    show_typing=True
)
async def process_address(update, context):
    # Fully protected handler with all features
    ...


Example 4: Session requirement
-------------------------------
from utils.handler_decorators import require_session, safe_handler

@require_session(fallback_state=ConversationHandler.END)
@safe_handler(fallback_state=ConversationHandler.END)
async def continue_order(update, context):
    # Session guaranteed to exist in context.user_data['session']
    session = context.user_data['session']
    ...
"""
