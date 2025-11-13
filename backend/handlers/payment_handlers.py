"""
Payment Handlers
Handles balance, topup, and payment flow for Telegram bot
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# These will be imported from server.py
# TODO: Move these to utils when refactoring is complete
# from utils.telegram_helpers import safe_telegram_call, mark_message_as_selected
# from utils.security import check_user_blocked, send_blocked_message


async def my_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db, find_user_by_telegram_id, safe_telegram_call, mark_message_as_selected, check_user_blocked, send_blocked_message):
    """
    Show user balance and topup options
    Handles both /balance command and callback
    """
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        telegram_id = query.from_user.id
        
        # Load message context from database if this is a callback from payment screen
        payment_record = await db.payments.find_one(
            {"telegram_id": telegram_id, "type": "topup", "status": "pending"},
            {"_id": 0},
            sort=[("created_at", -1)]  # Get latest pending payment
        )
        
        logger.info(f"Payment record found: {payment_record is not None}")
        if payment_record and payment_record.get('payment_message_id'):
            logger.info(f"Payment message_id: {payment_record.get('payment_message_id')}")
            context.user_data['last_bot_message_id'] = payment_record['payment_message_id']
            context.user_data['last_bot_message_text'] = payment_record.get('payment_message_text', '')
        
        logger.info(f"Context before mark_message_as_selected: last_bot_message_id={context.user_data.get('last_bot_message_id')}")
        
        # Mark previous message as selected
        asyncio.create_task(mark_message_as_selected(update, context))
        
        send_method = query.message.reply_text
    else:
        asyncio.create_task(mark_message_as_selected(update, context))
        telegram_id = update.effective_user.id
        send_method = update.message.reply_text
    
    # Check if user is blocked
    if await check_user_blocked(telegram_id):
        await send_blocked_message(update)
        return
    
    user = await find_user_by_telegram_id(telegram_id)
    balance = user.get('balance', 0.0) if user else 0.0
    
    message = f"""💳 Ваш баланс: ${balance:.2f}

Вы можете использовать баланс для оплаты заказов.

Введите сумму для пополнения (минимум $10):"""
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data='start')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Set state to wait for amount input
    context.user_data['awaiting_topup_amount'] = True
    
    # Send message and save context
    bot_message = await send_method(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    context.user_data['last_bot_message_id'] = bot_message.message_id
    context.user_data['last_bot_message_text'] = message


async def handle_topup_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE, db, create_oxapay_invoice, safe_telegram_call, mark_message_as_selected):
    """
    Handle custom topup amount input from user
    Creates payment invoice and shows payment link
    """
    if not context.user_data.get('awaiting_topup_amount'):
        return
    
    asyncio.create_task(mark_message_as_selected(update, context))
    
    try:
        amount = float(update.message.text.strip())
        
        if amount < 10:
            await update.message.reply_text(
                "❌ Минимальная сумма пополнения: $10\n\nПожалуйста, введите сумму не менее $10:"
            )
            return
        
        if amount > 10000:
            await update.message.reply_text(
                "❌ Максимальная сумма пополнения: $10,000\n\nПожалуйста, введите сумму не более $10,000:"
            )
            return
        
        # Clear awaiting state
        context.user_data['awaiting_topup_amount'] = False
        
        telegram_id = update.effective_user.id
        
        # Create payment via Oxapay
        from datetime import datetime, timezone
        from uuid import uuid4
        
        payment_id = str(uuid4())
        
        invoice_result = await create_oxapay_invoice(
            amount=amount,
            order_id=payment_id,
            description=f"Balance topup for ${amount:.2f}"
        )
        
        if not invoice_result.get('success'):
            await update.message.reply_text(
                "❌ Ошибка при создании платежа. Попробуйте позже или свяжитесь с администратором."
            )
            return
        
        # Save payment record
        payment_record = {
            "id": payment_id,
            "telegram_id": telegram_id,
            "type": "topup",
            "amount": amount,
            "status": "pending",
            "track_id": invoice_result.get('trackId'),
            "pay_link": invoice_result.get('payLink'),
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.payments.insert_one(payment_record)
        
        # Show payment link
        message = f"""✅ Счёт на пополнение создан!

💰 Сумма: ${amount:.2f}
🔗 Ссылка для оплаты:

{invoice_result.get('payLink')}

⏰ Счёт действителен 30 минут.
После оплаты баланс будет автоматически пополнен."""
        
        keyboard = [
            [InlineKeyboardButton("💳 Перейти к оплате", url=invoice_result.get('payLink'))],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        bot_message = await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        
        # Save message context
        await db.payments.update_one(
            {"id": payment_id},
            {"$set": {
                "payment_message_id": bot_message.message_id,
                "payment_message_text": message
            }}
        )
        
        context.user_data['last_bot_message_id'] = bot_message.message_id
        context.user_data['last_bot_message_text'] = message
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Пожалуйста, введите число (например: 50):"
        )


async def add_balance(telegram_id: int, amount: float, db):
    """
    Add balance to user account
    
    Args:
        telegram_id: User's Telegram ID
        amount: Amount to add
        db: Database connection
    
    Returns:
        bool: True if successful
    """
    try:
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$inc": {"balance": amount}}
        )
        
        if result.modified_count > 0:
            logger.info(f"💰 Added ${amount:.2f} to user {telegram_id}")
            return True
        else:
            logger.warning(f"⚠️ User {telegram_id} not found for balance add")
            return False
            
    except Exception as e:
        logger.error(f"Error adding balance: {e}")
        return False


async def deduct_balance(telegram_id: int, amount: float, db):
    """
    Deduct balance from user account
    
    Args:
        telegram_id: User's Telegram ID
        amount: Amount to deduct
        db: Database connection
    
    Returns:
        bool: True if successful, False if insufficient balance
    """
    try:
        # Check current balance first
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0, "balance": 1})
        
        if not user:
            logger.warning(f"⚠️ User {telegram_id} not found")
            return False
        
        current_balance = user.get('balance', 0.0)
        
        if current_balance < amount:
            logger.warning(f"⚠️ Insufficient balance for user {telegram_id}: ${current_balance:.2f} < ${amount:.2f}")
            return False
        
        # Deduct balance
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$inc": {"balance": -amount}}
        )
        
        if result.modified_count > 0:
            logger.info(f"💸 Deducted ${amount:.2f} from user {telegram_id}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error deducting balance: {e}")
        return False
