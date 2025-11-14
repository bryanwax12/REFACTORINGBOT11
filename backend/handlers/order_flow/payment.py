"""
Order Flow: Payment Handlers
Handles payment method selection and processing
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)


async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show payment method selection screen
    
    This function is typically called after carrier selection.
    Shows options: Pay from balance, Pay with crypto, Top-up balance
    """
    from server import (
        safe_telegram_call,
        find_user_by_telegram_id,
        PAYMENT_METHOD,
        mark_message_as_selected
    )
    from utils.ui_utils import PaymentFlowUI
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    user = await find_user_by_telegram_id(telegram_id)
    
    # Get order amount
    selected_rate = context.user_data.get('selected_rate', {})
    amount = context.user_data.get('final_amount', selected_rate.get('amount', 0))
    balance = user.get('balance', 0.0) if user else 0.0
    
    # Build message
    message = PaymentFlowUI.payment_method_selection(amount, balance)
    
    # Build keyboard
    keyboard = []
    
    if balance >= amount:
        keyboard.append([InlineKeyboardButton(
            f"💳 Оплатить с баланса (${balance:.2f})",
            callback_data='pay_from_balance'
        )])
    
    keyboard.append([InlineKeyboardButton(
        "💰 Оплатить криптовалютой",
        callback_data='pay_crypto'
    )])
    
    if balance < amount:
        deficit = amount - balance
        keyboard.append([InlineKeyboardButton(
            f"➕ Пополнить баланс (не хватает ${deficit:.2f})",
            callback_data='topup_for_order'
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к тарифам", callback_data='back_to_rates')])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
        message,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
    
    return PAYMENT_METHOD


async def handle_pay_from_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment from user balance"""
    from server import process_payment
    return await process_payment(update, context)


async def handle_pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle crypto payment selection"""
    from server import (
        safe_telegram_call,
        mark_message_as_selected,
        PAYMENT_METHOD
    )
    from utils.ui_utils import PaymentFlowUI
    import asyncio
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Get order amount
    selected_rate = context.user_data.get('selected_rate', {})
    amount = context.user_data.get('final_amount', selected_rate.get('amount', 0))
    
    # Show crypto selection
    message = PaymentFlowUI.topup_crypto_selection(amount)
    reply_markup = PaymentFlowUI.build_crypto_selection_keyboard()
    
    await safe_telegram_call(query.message.reply_text(
        message,
        reply_markup=reply_markup
    ))
    
    return PAYMENT_METHOD


async def handle_topup_for_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle top-up balance before payment"""
    from server import my_balance_command
    
    # Save that we're in order flow for return
    context.user_data['return_to_order_after_topup'] = True
    
    return await my_balance_command(update, context)


async def handle_back_to_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to rates button"""
    from server import fetch_shipping_rates, mark_message_as_selected
    import asyncio
    
    # Mark previous message as selected (remove buttons)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Return to rate selection
    return await fetch_shipping_rates(update, context)


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    'show_payment_methods',
    'handle_pay_from_balance',
    'handle_pay_crypto',
    'handle_topup_for_order',
    'handle_back_to_rates'
]
