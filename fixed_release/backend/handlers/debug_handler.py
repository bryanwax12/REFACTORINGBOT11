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
    logger.error(f"   User data (filtered): {[k for k in context.user_data.keys() if not k.startswith('_')]}")
    logger.error(f"   Chat data keys: {list(context.chat_data.keys())}")
    
    # Check conversation state
    try:
        # Try to get conversation state from PTB internal storage
        if hasattr(update, 'effective_chat') and update.effective_chat:
            logger.error(f"   Chat ID: {update.effective_chat.id}")
            logger.error(f"   User ID: {user_id}")
    except Exception as e:
        logger.error(f"   Error checking conversation state: {e}")
    
    # Check if user is in middle of conversation
    has_order_data = any(key.startswith('from_') or key.startswith('to_') or key.startswith('parcel_') 
                         for key in context.user_data.keys())
    
    if has_order_data:
        logger.error(f"   ⚠️ USER HAS ORDER DATA but ConversationHandler didn't match!")
        logger.error(f"   This means conversation state is lost or incorrect!")
        
        # Send specific message
        if update.message:
            await update.message.reply_text(
                "⚠️ Извините, состояние диалога потеряно.\n\n"
                "Пожалуйста, используйте /start чтобы начать заново."
            )
    else:
        # Send helpful message to user
        if update.message:
            await update.message.reply_text(
                "⚠️ Сообщение не обработано.\n\n"
                "Пожалуйста, используйте /start для начала работы с ботом."
            )
