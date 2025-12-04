"""
Order Flow: Template Save and Topup Handlers
Handles template saving and topup amount input
"""
import logging
import asyncio
import time
import uuid
from datetime import datetime, timezone
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup

# ⚡ Performance: Import preloaded keyboards
from utils.ui_utils import PRELOADED_CANCEL_KEYBOARD
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

from utils.handler_decorators import with_user_session, safe_handler


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def save_template_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save template with user-provided name"""
    from server import (
        TEMPLATE_NAME,
        db, safe_telegram_call
    )
    from utils.db_operations import insert_template, count_user_templates
    from services import template_service
    
    # Remove cancel button from previous message if it exists
    if 'last_prompt_message_id' in context.user_data:
        try:
            bot = context.bot
            chat_id = update.effective_chat.id
            message_id = context.user_data['last_prompt_message_id']
            
            logger.info(f"🔧 Attempting to remove cancel button: chat_id={chat_id}, message_id={message_id}")
            
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None
            )
            logger.info("✅ Removed cancel button from template prompt")
        except Exception as e:
            logger.warning(f"Could not remove cancel button: {e}")
    
    template_name = update.effective_message.text.strip()[:30]  # Limit to 30 chars
    
    if not template_name:
        await safe_telegram_call(update.effective_message.reply_text("❌ Название не может быть пустым. Попробуйте еще раз:"))
        return TEMPLATE_NAME
    
    telegram_id = update.effective_user.id
    
    # Check if template with this name already exists
    existing = await db.templates.find_one({
        "telegram_id": telegram_id,
        "name": template_name
    })
    
    if existing:
        # Ask to update or use new name
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить существующий", callback_data=f'template_update_{existing["id"]}')],
            [InlineKeyboardButton("📝 Ввести другое название", callback_data='template_new_name')],
            [InlineKeyboardButton("❌ Отмена", callback_data='start')]
        ]
        # 🚀 PERFORMANCE: Send message in background
        async def send_message():
            message_text = (
                f"⚠️ *Шаблон уже существует*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📁 *Название:* {template_name}\n\n"
                f"Шаблон с таким названием уже сохранён.\n\n"
                f"*Выберите действие:*\n"
                f"• Обновить — заменить адреса в существующем шаблоне\n"
                f"• Ввести другое название — сохранить как новый шаблон"
            )
            bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            ))
            # Don't clear last_bot_message here - we need it for mark_message_as_selected
            context.user_data['pending_template_name'] = template_name

        asyncio.create_task(send_message())

        return TEMPLATE_NAME
    
    # Create template using template service
    success, template_id, error = await template_service.create_template(
        telegram_id=telegram_id,
        template_name=template_name,
        order_data=context.user_data,
        insert_template_func=insert_template,
        count_user_templates_func=count_user_templates,
        max_templates=10
    )
    
    if not success:
        # Add navigation buttons for error case
        keyboard = [
            [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='return_to_confirm_from_error')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"❌ *Ошибка сохранения шаблона*\n\n{error}"
        await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        ))
        # Return to CONFIRM_DATA state instead of ending conversation
        from server import CONFIRM_DATA
        return CONFIRM_DATA
    
    # ⚡ Performance: Invalidate template cache
    if 'cached_templates' in context.user_data:
        del context.user_data['cached_templates']
        logger.info("⚡ Template cache invalidated after save")
    
    keyboard = [
        [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='continue_order')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"✅ *Шаблон сохранён!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 *Название:* {template_name}\n\n"
        f"💡 Теперь вы можете использовать этот шаблон для быстрого создания заказов с готовыми адресами.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Что дальше?*"
    )
    
    # ⚡ Performance: Invalidate template cache
    if 'cached_templates' in context.user_data:
        del context.user_data['cached_templates']
        logger.info("⚡ Template cache invalidated after save")
    
    # 🚀 PERFORMANCE: Send message in background
    async def send_success():
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
        # Save last bot message context for button protection
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
    
    asyncio.create_task(send_success())
    
    # Save template name for potential continuation
    context.user_data['saved_template_name'] = template_name
    
    # Clear prompt message ID after successful save
    context.user_data.pop('last_prompt_message_id', None)
    
    return TEMPLATE_NAME


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_template_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update existing template with current order data"""
    from server import (
        db, safe_telegram_call, mark_message_as_selected
    )
    from repositories import get_user_repo
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    template_id = query.data.replace('template_update_', '')
    telegram_id = query.from_user.id
    
    # Check if user exists using Repository Pattern
    user_repo = get_user_repo()
    user = await user_repo.find_by_telegram_id(telegram_id)
    if not user:
        await safe_telegram_call(update.effective_message.reply_text("❌ Ошибка: пользователь не найден"))
        return ConversationHandler.END
    
    # Update template
    update_data = {
        "from_name": context.user_data.get('from_name', ''),
        "from_street1": context.user_data.get('from_street', ''),
        "from_street2": context.user_data.get('from_street2', ''),
        "from_city": context.user_data.get('from_city', ''),
        "from_state": context.user_data.get('from_state', ''),
        "from_zip": context.user_data.get('from_zip', ''),
        "from_phone": context.user_data.get('from_phone', ''),
        "to_name": context.user_data.get('to_name', ''),
        "to_street1": context.user_data.get('to_street', ''),
        "to_street2": context.user_data.get('to_street2', ''),
        "to_city": context.user_data.get('to_city', ''),
        "to_state": context.user_data.get('to_state', ''),
        "to_zip": context.user_data.get('to_zip', ''),
        "to_phone": context.user_data.get('to_phone', ''),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Note: update_template only supports template_id filter, manual query needed for telegram_id check
    result = await db.templates.update_one(
        {"id": template_id, "telegram_id": telegram_id},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        template_name = context.user_data.get('pending_template_name', 'шаблон')
        keyboard = [
            [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='continue_order')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            f"✅ *Шаблон обновлён!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📁 *Название:* {template_name}\n"
            f"🔄 *Статус:* Адреса обновлены\n\n"
            f"💡 Шаблон теперь содержит актуальные адреса из текущего заказа.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Что дальше?*"
        )
        
        # 🚀 PERFORMANCE: Send message in background
        async def send_message():
            bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            ))
            
            # Save last bot message context for button protection
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
                context.user_data['last_bot_message_text'] = message_text
                context.user_data['saved_template_name'] = template_name
        
        asyncio.create_task(send_message())
        
        return ConversationHandler.END
    else:
        await safe_telegram_call(update.effective_message.reply_text("❌ Не удалось обновить шаблон"))
        return ConversationHandler.END


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_template_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user to enter a new template name"""
    from server import TEMPLATE_NAME, safe_telegram_call, mark_message_as_selected
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    from utils.ui_utils import get_cancel_keyboard
    reply_markup = PRELOADED_CANCEL_KEYBOARD  # ⚡ Performance
    
    message_text = (
        "📝 *Новое название шаблона*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Введите уникальное название для шаблона.\n\n"
        "*Примеры:*\n"
        "• _\"Дом → Офис 2\"_\n"
        "• _\"Склад NY\"_\n"
        "• _\"Родителям (зима)\"_\n\n"
        "💬 *Введите название:*"
    )
    
    await safe_telegram_call(update.effective_message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    ))
    # Clear last_bot_message to prevent interfering with text input
    context.user_data.pop('last_bot_message_id', None)
    context.user_data.pop('last_bot_message_text', None)
    return TEMPLATE_NAME


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def continue_order_after_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order confirmation after saving template"""
    from handlers.order_flow.confirmation import show_data_confirmation
    from server import mark_message_as_selected
    import asyncio
    
    # Mark previous message as selected (remove buttons)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    # Return to order confirmation screen
    return await show_data_confirmation(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def handle_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom top-up amount input and create Oxapay invoice directly"""
    from server import (
        TOPUP_AMOUNT,
        safe_telegram_call, mark_message_as_selected,
        db
    )
    from services.api_services import create_oxapay_invoice
    from utils.db_operations import insert_payment
    from models.payment import Payment
    from repositories import get_user_repo
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import asyncio
    
    # Mark previous message as selected (remove "Отмена" button)
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
    try:
        amount_text = update.effective_message.text.strip()
        
        # Validate amount
        try:
            topup_amount = float(amount_text)
        except ValueError:
            await safe_telegram_call(update.effective_message.reply_text(
                "❌ Неверный формат суммы. Введите число, например: 50"
            ))
            return TOPUP_AMOUNT
        
        # Check limits
        if topup_amount < 10:
            await safe_telegram_call(update.effective_message.reply_text(
                "❌ Минимальная сумма пополнения: $10"
            ))
            return TOPUP_AMOUNT
        
        if topup_amount > 10000:
            await safe_telegram_call(update.effective_message.reply_text(
                "❌ Максимальная сумма пополнения: $10,000"
            ))
            return TOPUP_AMOUNT
        
        telegram_id = update.effective_user.id
        
        # Get user using Repository Pattern
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            await safe_telegram_call(update.effective_message.reply_text("❌ Пользователь не найден"))
            return ConversationHandler.END
        
        # Create Oxapay invoice directly (order_id must be <= 50 chars)
        # Generate short order_id: "top_" (4) + timestamp (10) + "_" (1) + random (8) = 23 chars
        order_id = f"top_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        invoice_result = await create_oxapay_invoice(
            amount=topup_amount,
            order_id=order_id,
            description=f"Balance Top-up ${topup_amount}"
        )
        
        if invoice_result.get('success'):
            track_id = invoice_result['trackId']
            pay_link = invoice_result['payLink']
            
            # Save top-up payment
            from datetime import datetime, timezone
            payment = Payment(
                telegram_id=telegram_id,
                order_id=f"topup_{user.get('id', user.get('_id', str(user['telegram_id'])))}",
                amount=topup_amount,
                invoice_id=track_id,
                status="pending",
                created_at=datetime.now(timezone.utc).isoformat(),
                type="topup"
            )
            payment_dict = payment.model_dump()
            # Remove pay_url as it's not in Payment model
            payment_dict['pay_url'] = pay_link
            payment_dict['track_id'] = track_id  # Store track_id for webhook lookup
            await insert_payment(payment_dict)
            
            keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = (
                f"✅ *Счёт на пополнение создан!*\n\n"
                f"💵 *Сумма: ${topup_amount}*\n"
                f"🪙 *Криптовалюта: Любая из доступных*\n\n"
                f"*Нажмите кнопку \"Оплатить\" для перехода на страницу оплаты.*\n"
                f"*На платежной странице вы сможете выбрать удобную криптовалюту.*\n\n"
                f"⚠️❗️❗️ *ВАЖНО: Оплатите точно ${topup_amount}!* ❗️❗️⚠️\n"
                f"_Если вы оплатите другую сумму, деньги НЕ поступят на баланс!_\n\n"
                f"*После успешной оплаты баланс будет автоматически пополнен.*"
            )
            
            # 🚀 PERFORMANCE: Send message in background
            async def send_message():
                bot_msg = await safe_telegram_call(update.effective_message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                ))
                
                if bot_msg:
                    # Save message_id in payment for later removal of button
                    await db.payments.update_one(
                        {"invoice_id": track_id},
                        {"$set": {
                            "payment_message_id": bot_msg.message_id,
                            "payment_message_text": message_text
                        }}
                    )
                    
                    # Also save in context for immediate use
                    context.user_data['last_bot_message_id'] = bot_msg.message_id
                    context.user_data['last_bot_message_text'] = message_text
            
            asyncio.create_task(send_message())
            
            return ConversationHandler.END
        else:
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(update.effective_message.reply_text(f"❌ *Ошибка создания инвойса:* {error_msg}", parse_mode='Markdown'))
            return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Top-up amount handling error: {e}")
        await safe_telegram_call(update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуйте снова позже."
        ))
        return ConversationHandler.END


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def cancel_template_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel template saving and return to order confirmation (no dialog)"""
    from server import safe_telegram_call
    from handlers.order_flow.confirmation import show_data_confirmation
    
    logger.info("❌ Canceling template save, returning to order confirmation")
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Remove buttons from the message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.warning(f"Could not remove buttons: {e}")
    
    # Return to order confirmation screen directly
    return await show_data_confirmation(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def return_to_confirm_from_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order confirmation after template save error"""
    from server import safe_telegram_call
    from handlers.order_flow.confirmation import show_data_confirmation
    
    logger.info("↩️ Returning to order confirmation from template error")
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Remove buttons from the error message
    try:
        await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
    except Exception as e:
        logger.warning(f"Could not remove buttons: {e}")
    
    # Return to order confirmation screen
    return await show_data_confirmation(update, context)


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    'save_template_name',
    'handle_template_update',
    'handle_template_new_name',
    'continue_order_after_template',
    'cancel_template_save',
    'return_to_confirm_from_error',
    'handle_topup_amount'
]
