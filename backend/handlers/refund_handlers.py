"""
Refund Request Handlers for Telegram Bot
Handles user refund requests for labels
"""
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

# Conversation states
REFUND_INPUT = 0

# Backend API - use environment variable or localhost for development
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:8001')


async def refund_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show refund menu with information about manual processing
    """
    query = update.callback_query
    await query.answer()
    
    message = (
        "💰 *Возврат средств за лейблы*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *Условия для возврата:*\n"
        "• Лейбл должен быть старше *5 дней*\n"
        "• Лейбл не использовался для отправки\n\n"
        "⚠️ *Важная информация:*\n"
        "• Заявки на рефанд обрабатываются *вручную*\n"
        "• Время рассмотрения: 1-3 рабочих дня\n"
        "• Вы получите уведомление о статусе заявки\n\n"
        "📝 *Отправьте номер(а) лейбла для возврата:*\n"
        "_(можете указать несколько через запятую)_"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Связаться с агентом", url="https://t.me/White_Label_Shipping_Bot_Agent")],
        [InlineKeyboardButton("❌ Отмена", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return REFUND_INPUT


async def process_refund_labels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Process label IDs for refund
    """
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Parse label IDs (can be comma-separated or newline-separated)
    label_ids = []
    for line in text.replace(',', '\n').split('\n'):
        label_id = line.strip()
        if label_id:
            label_ids.append(label_id)
    
    if not label_ids:
        await update.message.reply_text(
            "❌ Пожалуйста, введите хотя бы один номер лейбла."
        )
        return REFUND_INPUT
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        f"⏳ Проверяю {len(label_ids)} лейбл(ов)..."
    )
    
    try:
        # Call backend API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/refunds/request?telegram_id={user_id}",
                json={"label_ids": label_ids}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Build response message
                message_parts = []
                
                # Valid labels
                if result.get("valid_labels"):
                    message_parts.append(
                        f"✅ *Заявка создана!*\n\n"
                        f"📋 Принято к рассмотрению: *{len(result['valid_labels'])}* лейбл(ов)\n"
                    )
                    
                    if len(result['valid_labels']) <= 5:
                        message_parts.append("Лейблы:\n")
                        for label_id in result['valid_labels']:
                            message_parts.append(f"• `{label_id}`\n")
                    
                    message_parts.append(
                        f"\n⏳ Заявка будет рассмотрена администратором.\n"
                        f"Вы получите уведомление о результате.\n\n"
                        f"ID заявки: `{result['request_id']}`"
                    )
                
                # Invalid labels
                if result.get("invalid_labels"):
                    if result.get("valid_labels"):
                        message_parts.append("\n\n")
                    
                    message_parts.append(
                        f"⚠️ *Не прошли проверку:* {len(result['invalid_labels'])} лейбл(ов)\n\n"
                    )
                    
                    for invalid in result['invalid_labels'][:10]:  # Show max 10
                        message_parts.append(
                            f"❌ `{invalid['label_id']}`\n"
                            f"   _{invalid['reason']}_\n\n"
                        )
                    
                    if len(result['invalid_labels']) > 10:
                        message_parts.append(f"_...и еще {len(result['invalid_labels']) - 10}_\n")
                
                # No valid labels at all
                if not result.get("valid_labels"):
                    message_parts = [
                        "❌ *Не удалось создать заявку*\n\n"
                        "Ни один из указанных лейблов не прошел проверку:\n\n"
                    ]
                    for invalid in result['invalid_labels'][:10]:
                        message_parts.append(
                            f"• `{invalid['label_id']}`\n"
                            f"  _{invalid['reason']}_\n\n"
                        )
                
                message = "".join(message_parts)
                
                keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="start")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await processing_msg.edit_text(
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await processing_msg.edit_text(
                    f"❌ Ошибка при создании заявки: {response.status_code}\n\n"
                    "Попробуйте позже или свяжитесь с поддержкой."
                )
    
    except Exception as e:
        logger.error(f"Error processing refund request: {e}")
        await processing_msg.edit_text(
            f"❌ Произошла ошибка при обработке заявки:\n{str(e)}\n\n"
            "Попробуйте позже или свяжитесь с поддержкой."
        )
    
    return ConversationHandler.END


async def my_refunds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show user's refund requests
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    try:
        # Get user's refund requests
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BACKEND_URL}/api/refunds/user/requests?telegram_id={user_id}"
            )
            
            if response.status_code == 200:
                data = response.json()
                requests = data.get("requests", [])
                
                if not requests:
                    message = (
                        "📋 *Мои заявки на возврат*\n\n"
                        "У вас пока нет заявок на возврат средств.\n\n"
                        "Чтобы создать заявку, нажмите \"💰 Refund Label\" в главном меню."
                    )
                else:
                    message_parts = [
                        f"📋 *Мои заявки на возврат*\n\n"
                        f"Всего заявок: *{len(requests)}*\n\n"
                    ]
                    
                    # Status emojis
                    status_emoji = {
                        "pending": "⏳",
                        "approved": "✅",
                        "rejected": "❌",
                        "processed": "💰"
                    }
                    
                    status_text = {
                        "pending": "На рассмотрении",
                        "approved": "Одобрено",
                        "rejected": "Отклонено",
                        "processed": "Выполнено"
                    }
                    
                    for idx, req in enumerate(requests[:10], 1):  # Show max 10
                        status = req.get("status", "pending")
                        label_count = len(req.get("label_ids", []))
                        created_at = req.get("created_at", "")
                        
                        if isinstance(created_at, str):
                            try:
                                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                created_at = dt.strftime("%d.%m.%Y %H:%M")
                            except:
                                pass
                        
                        message_parts.append(
                            f"{idx}. {status_emoji.get(status, '📝')} *{status_text.get(status, status)}*\n"
                            f"   Лейблов: {label_count}\n"
                            f"   Дата: {created_at}\n"
                        )
                        
                        if req.get("refund_amount"):
                            message_parts.append(f"   Сумма: ${req['refund_amount']:.2f}\n")
                        
                        message_parts.append("\n")
                    
                    if len(requests) > 10:
                        message_parts.append(f"_...и еще {len(requests) - 10} заявок_\n")
                    
                    message = "".join(message_parts)
                
                keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="start")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="start")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "❌ Ошибка при получении списка заявок. Попробуйте позже.",
                    reply_markup=reply_markup
                )
    
    except Exception as e:
        logger.error(f"Error getting user refunds: {e}")
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"❌ Произошла ошибка: {str(e)}",
            reply_markup=reply_markup
        )


async def cancel_refund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel refund request process
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    query = update.callback_query
    await query.answer()
    
    # Add button to return to main menu
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "❌ Создание заявки отменено.",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END
