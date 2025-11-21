"""
User feedback utilities to show processing status
Provides visual feedback when user inputs are being processed
"""
import asyncio
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ReactionEmoji

logger = logging.getLogger(__name__)


def with_processing_feedback(show_checkmark: bool = True, reminder_on_fast_input: bool = True):
    """
    Decorator to provide visual feedback during message processing
    
    Features:
    1. Shows checkmark ✅ on user's message when accepted
    2. Shows reminder if user sends messages too quickly
    
    Args:
        show_checkmark: Add ✅ reaction to accepted message
        reminder_on_fast_input: Show reminder if user types too fast
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_message = update.message
            
            # Check if this is a debounced (ignored) message
            # by checking if handler was called too quickly
            if reminder_on_fast_input and context.user_data.get('_fast_input_count', 0) > 2:
                # User has sent 3+ fast messages, show reminder
                try:
                    await user_message.reply_text(
                        "⏱ Пожалуйста, подождите секунду между вводами.\n"
                        "Ваше сообщение обрабатывается...",
                        quote=False
                    )
                    # Reset counter
                    context.user_data['_fast_input_count'] = 0
                except Exception as e:
                    logger.warning(f"Failed to send fast input reminder: {e}")
            
            # Process the message
            result = await func(update, context, *args, **kwargs)
            
            # Add checkmark to show message was accepted
            if show_checkmark and user_message:
                try:
                    await user_message.set_reaction(ReactionEmoji.THUMBS_UP)
                except Exception as e:
                    # Reactions might not be supported in all chats
                    logger.debug(f"Could not set reaction: {e}")
            
            return result
        
        return wrapper
    return decorator


async def mark_message_accepted(update: Update, emoji: str = "👍"):
    """
    Add emoji reaction to user's message to show it was accepted
    
    Args:
        update: Telegram update object
        emoji: Emoji to use as reaction (default: 👍)
    """
    try:
        if update.message:
            await update.message.set_reaction(emoji)
    except Exception as e:
        logger.debug(f"Could not set reaction: {e}")


async def show_processing_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Show temporary "processing..." message and return message_id
    Use this for long-running operations
    
    Returns:
        message_id of the processing message (to delete later)
    """
    try:
        msg = await update.message.reply_text(
            "⏳ Обрабатываю ваш запрос...",
            quote=False
        )
        return msg.message_id
    except Exception as e:
        logger.warning(f"Failed to send processing message: {e}")
        return None


async def delete_processing_message(update: Update, message_id: int):
    """
    Delete the temporary processing message
    
    Args:
        update: Telegram update object
        message_id: ID of message to delete
    """
    if message_id:
        try:
            await update.message.chat.delete_message(message_id)
        except Exception as e:
            logger.debug(f"Could not delete processing message: {e}")


class ProcessingIndicator:
    """
    Context manager for showing processing status
    
    Usage:
        async with ProcessingIndicator(update, context):
            # Long running operation
            await process_payment()
            # Processing message will be shown and auto-deleted
    """
    
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                 message: str = "⏳ Обрабатываю..."):
        self.update = update
        self.context = context
        self.message = message
        self.msg_id = None
    
    async def __aenter__(self):
        try:
            msg = await self.update.message.reply_text(self.message, quote=False)
            self.msg_id = msg.message_id
        except Exception as e:
            logger.warning(f"Failed to show processing indicator: {e}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.msg_id:
            try:
                await self.update.message.chat.delete_message(self.msg_id)
            except Exception as e:
                logger.debug(f"Could not delete processing message: {e}")


def track_fast_input(func):
    """
    Decorator to track how fast user is typing
    Increments counter if messages come too quickly
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # This will be used by debounce decorator
        import time
        current_time = time.time()
        last_time = context.user_data.get('_last_input_time', 0)
        
        if current_time - last_time < 0.5:  # Less than 500ms
            # User is typing fast
            context.user_data['_fast_input_count'] = context.user_data.get('_fast_input_count', 0) + 1
        else:
            # Reset counter if user paused
            context.user_data['_fast_input_count'] = 0
        
        context.user_data['_last_input_time'] = current_time
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper
