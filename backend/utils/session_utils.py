"""
Session Utilities
Вспомогательные функции для работы с сессиями пользователей
"""
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def save_to_session(user_id: int, next_step: str, data: dict, context: ContextTypes.DEFAULT_TYPE):
    """
    Save data to both context.user_data and session manager (V2 - atomic)
    Сохраняет данные в контекст и session manager атомарно
    
    Args:
        user_id: Telegram user ID
        next_step: Next conversation step
        data: Data to save
        context: Telegram context
    """
    from session_manager import session_manager
    
    context.user_data.update(data)
    await session_manager.update_session_atomic(user_id, step=next_step, data=data)


async def handle_critical_api_error(
    user_id: int,
    error_message: str,
    current_step: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Handle critical API errors with option to revert to previous step
    Обрабатывает критические ошибки API с возможностью вернуться к предыдущему шагу
    
    Shows user a message with options to retry, edit data, or cancel
    
    Args:
        user_id: Telegram user ID
        error_message: Error message to display
        current_step: Current conversation step
        update: Telegram update
        context: Telegram context
    
    Returns:
        int: Current step (for retry)
    """
    from session_manager import session_manager
    from handlers.common_handlers import safe_telegram_call
    
    # Log to session
    await session_manager.update_session_atomic(user_id, data={
        'last_error': error_message,
        'error_step': current_step,
        'error_timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    keyboard = [
        [InlineKeyboardButton("🔄 Попробовать снова", callback_data='continue_order')],
        [InlineKeyboardButton("✏️ Редактировать данные", callback_data='edit_data')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Show error message with options
    query = update.callback_query
    if query:
        await safe_telegram_call(query.message.reply_text(
            f"❌ Произошла ошибка:\n{error_message}\n\nВыберите действие:",
            reply_markup=reply_markup
        ))
    
    return current_step  # Stay on same step for retry


async def handle_step_error(
    user_id: int,
    error: Exception,
    current_step: str,
    context: ContextTypes.DEFAULT_TYPE,
    allow_revert: bool = False
):
    """
    Handle errors during step processing
    Обрабатывает ошибки во время обработки шагов диалога
    
    Args:
        user_id: User ID
        error: Exception that occurred
        current_step: Current conversation step
        context: Telegram context
        allow_revert: If True, revert to previous step; if False, retry from same step
    
    Returns:
        int: State to return to (current or previous)
    """
    from session_manager import session_manager
    # Import conversation states (будут доступны после импорта в server.py)
    from server import (
        FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, FROM_STATE,
        FROM_ZIP, FROM_PHONE, TO_NAME, TO_ADDRESS, TO_ADDRESS2, TO_CITY,
        TO_STATE, TO_ZIP, TO_PHONE, PARCEL_WEIGHT, PARCEL_LENGTH,
        PARCEL_WIDTH, PARCEL_HEIGHT, CONFIRM_DATA, SELECT_CARRIER
    )
    
    logger.error(f"❌ Error at step {current_step} for user {user_id}: {error}")
    
    # Save error info to session for debugging
    error_data = {
        'last_error': str(error),
        'error_step': current_step,
        'error_timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if allow_revert:
        # Revert to previous step
        previous_step = await session_manager.revert_to_previous_step(user_id, current_step, str(error))
        if previous_step:
            logger.info(f"🔙 Reverted user {user_id} from {current_step} to {previous_step}")
            # Map step names to ConversationHandler states
            step_to_state = {
                "START": FROM_NAME,
                "FROM_NAME": FROM_NAME,
                "FROM_ADDRESS": FROM_NAME,
                "FROM_ADDRESS2": FROM_ADDRESS,
                "FROM_CITY": FROM_ADDRESS2,
                "FROM_STATE": FROM_CITY,
                "FROM_ZIP": FROM_STATE,
                "FROM_PHONE": FROM_ZIP,
                "TO_NAME": FROM_PHONE,
                "TO_ADDRESS": TO_NAME,
                "TO_ADDRESS2": TO_ADDRESS,
                "TO_CITY": TO_ADDRESS2,
                "TO_STATE": TO_CITY,
                "TO_ZIP": TO_STATE,
                "TO_PHONE": TO_ZIP,
                "PARCEL_WEIGHT": TO_PHONE,
                "PARCEL_LENGTH": PARCEL_WEIGHT,
                "PARCEL_WIDTH": PARCEL_LENGTH,
                "PARCEL_HEIGHT": PARCEL_WIDTH,
                "CONFIRM_DATA": PARCEL_HEIGHT,
                "CARRIER_SELECTION": CONFIRM_DATA,
                "PAYMENT_METHOD": SELECT_CARRIER
            }
            return step_to_state.get(previous_step, current_step)
    else:
        # Save error but stay on same step (retry)
        await session_manager.update_session_atomic(user_id, data=error_data)
    
    # Don't change step - let user retry from same step
    return current_step
