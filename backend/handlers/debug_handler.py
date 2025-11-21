"""
Debug handler to catch unhandled messages
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def debug_unhandled_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Catch all unhandled messages for debugging
    """
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    message_text = update.message.text if update.message else "N/A"
    
    logger.error(f"🚨 UNHANDLED MESSAGE from user {user_id}: '{message_text}'")
    logger.error(f"   User data keys: {list(context.user_data.keys())}")
    logger.error(f"   Chat data keys: {list(context.chat_data.keys())}")
    
    # Send helpful message to user
    if update.message:
        await update.message.reply_text(
            "⚠️ Сообщение не обработано.\n\n"
            "Пожалуйста, используйте /start для начала работы с ботом."
        )
