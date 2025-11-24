"""
Decorators for Telegram Bot Handlers
Provides reusable decorators for common handler functionality
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def with_typing_indicator(func):
    """
    Show 'typing...' indicator immediately when user sends text
    
    Usage:
        @with_typing_indicator
        async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # handler code
            pass
    
    Args:
        func: Async handler function to wrap
    
    Returns:
        Wrapped function that shows typing indicator before execution
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # INSTANT visual feedback
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, 
                action="typing"
            )
        except Exception as e:
            logger.debug(f"Failed to send typing action: {e}")
        
        return await func(update, context)
    
    return wrapper
