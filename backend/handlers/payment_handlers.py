"""
Payment Handlers
Handles balance, topup, and payment flow for Telegram bot
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram.error
import pymongo.errors

logger = logging.getLogger(__name__)

# These will be imported from server.py
# TODO: Move these to utils when refactoring is complete
# from utils.telegram_helpers import safe_telegram_call, mark_message_as_selected
# from utils.security import check_user_blocked, send_blocked_message


from utils.handler_decorators import with_user_session, safe_handler, with_services

@safe_handler()
@with_user_session(create_user=True)
@with_services(user_service=True, payment_service=True)
async def my_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE, user_service, payment_service):
    """
    /balance command handler
    Shows user balance and allows topup
    
    Decorators handle:
    - User session management + blocking check
    - Error handling
    - UserService injection
    """
    from server import safe_telegram_call, mark_message_as_selected
    
    logger.info("🔍 my_balance_command CALLED")
    
    # Get telegram_id
    telegram_id = update.effective_user.id
    
    # ALWAYS get fresh user data from DB (don't trust context cache)
    from server import db
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    
    if not user:
        logger.error(f"❌ User {telegram_id} not found in database!")
        return
    
    balance = user.get('balance', 0)
    
    logger.info(f"💰 Fresh balance from DB for user {telegram_id}: ${balance:.2f}")
    
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        # TODO: Load message context from last pending payment
        # payment_record = await payment_service.get_pending_payment(telegram_id, "topup")
        # 
        # if payment_record and payment_record.get('payment_message_id'):
        #     logger.info(f"Payment message_id: {payment_record.get('payment_message_id')}")
        #     context.user_data['last_bot_message_id'] = payment_record['payment_message_id']
        #     context.user_data['last_bot_message_text'] = payment_record.get('payment_message_text', '')
        
        logger.info(f"Context before mark_message_as_selected: last_bot_message_id={context.user_data.get('last_bot_message_id')}")
        
        # Mark previous message as selected
        asyncio.create_task(mark_message_as_selected(update, context))
        
        send_method = query.message.reply_text
    else:
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    from utils.ui_utils import get_back_to_menu_keyboard
    
    message = f"""💰 *Пополнение баланса*
━━━━━━━━━━━━━━━━━━━━

💳 *Ваш баланс:* ${balance:.2f}

Вы можете использовать баланс для оплаты заказов.

━━━━━━━━━━━━━━━━━━━━

💵 *Введите сумму для пополнения*
(минимум $10):"""
    
    reply_markup = get_back_to_menu_keyboard()
    
    # Set state to wait for amount input
    context.user_data['awaiting_topup_amount'] = True
    
    logger.info(f"📤 Sending balance message to user {telegram_id}")
    
    # Send message and save context
    bot_message = await send_method(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    logger.info(f"✅ Balance message sent successfully, message_id={bot_message.message_id}")
    
    context.user_data['last_bot_message_id'] = bot_message.message_id
    context.user_data['last_bot_message_text'] = message


async def add_balance(telegram_id: int, amount: float, db):
    """
    Add balance to user account
    
    Args:
        telegram_id: User's Telegram ID
        amount: Amount to add
        db: Database connection (deprecated, kept for backward compatibility)
    
    Returns:
        bool: True if successful
    """
    try:
        from repositories import get_user_repo
        user_repo = get_user_repo()
        
        result = await user_repo.update_balance(telegram_id, amount, operation="add")
        
        if result:
            logger.info(f"💰 Added ${amount:.2f} to user {telegram_id}")
            return True
        else:
            logger.warning(f"⚠️ User {telegram_id} not found for balance add")
            return False
    
    except pymongo.errors.ConnectionFailure as e:
        logger.error(f"MongoDB connection failed while adding balance: {e}", exc_info=True)
        return False
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error while adding balance: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error adding balance: {e}", exc_info=True)
        return False


async def deduct_balance(telegram_id: int, amount: float, db):
    """
    Deduct balance from user account
    
    Args:
        telegram_id: User's Telegram ID
        amount: Amount to deduct
        db: Database connection (deprecated, kept for backward compatibility)
    
    Returns:
        bool: True if successful, False if insufficient balance
    """
    try:
        from repositories import get_user_repo
        user_repo = get_user_repo()
        
        # Check current balance first
        current_balance = await user_repo.get_balance(telegram_id)
        
        if current_balance == 0.0:
            # User might not exist
            user = await user_repo.find_by_telegram_id(telegram_id)
            if not user:
                logger.warning(f"⚠️ User {telegram_id} not found")
                return False
        
        if current_balance < amount:
            logger.warning(f"⚠️ Insufficient balance for user {telegram_id}: ${current_balance:.2f} < ${amount:.2f}")
            return False
        
        # Deduct balance
        result = await user_repo.update_balance(telegram_id, amount, operation="subtract")
        
        if result:
            logger.info(f"💸 Deducted ${amount:.2f} from user {telegram_id}")
            return True
        else:
            return False
    
    except pymongo.errors.ConnectionFailure as e:
        logger.error(f"MongoDB connection failed while deducting balance: {e}", exc_info=True)
        return False
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error while deducting balance: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error deducting balance: {e}", exc_info=True)
        return False



# ==================== TOP-UP HANDLERS ====================

async def handle_topup_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom topup amount input"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from services.api_services import create_oxapay_invoice
    from utils.db_operations import insert_payment
    from server import Payment
    import time
    import uuid
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    if not context.user_data.get('awaiting_topup_amount'):
        return
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    try:
        amount = float(update.message.text.strip())
        
        from utils.ui_utils import PaymentFlowUI
        if amount < 10:
            await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_amount_too_small(), parse_mode='Markdown'))
            return
        
        if amount > 10000:
            await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_amount_too_large(), parse_mode='Markdown'))
            return
        
        # Clear the waiting flag
        context.user_data['awaiting_topup_amount'] = False
        
        telegram_id = update.effective_user.id
        
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            await safe_telegram_call(update.message.reply_text("❌ Пользователь не найден"))
            return
        
        # Create Oxapay invoice (order_id must be <= 50 chars)
        order_id = f"top_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        invoice_result = await create_oxapay_invoice(
            amount=amount,
            order_id=order_id,
            description=f"Balance Top-up ${amount}"
        )
        
        if invoice_result.get('success'):
            track_id = invoice_result['trackId']
            pay_link = invoice_result['payLink']
            
            # Save top-up payment
            topup_input_message_id = context.user_data.get('last_bot_message_id')
            
            payment = Payment(
                order_id=f"topup_{user.get('id', user.get('_id', str(user['telegram_id'])))}",
                amount=amount,
                invoice_id=track_id,
                pay_url=pay_link,
                status="pending"
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            payment_dict['telegram_id'] = telegram_id
            payment_dict['track_id'] = track_id  # Store track_id for webhook lookup
            payment_dict['type'] = 'topup'
            payment_dict['topup_input_message_id'] = topup_input_message_id
            await insert_payment(payment_dict)
            
            keyboard = [
                [InlineKeyboardButton("💳 Оплатить", url=pay_link)],
                [InlineKeyboardButton("◀️ Назад", callback_data='my_balance')],
                [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""*✅ Счёт на пополнение создан!*

*💵 Сумма: ${amount}*
*🪙 Криптовалюта: Любая из доступных*

*Нажмите кнопку "Оплатить" для перехода на страницу оплаты.*
*На платежной странице вы сможете выбрать удобную криптовалюту.*

⚠️❗️❗️ *ВАЖНО: Оплатите точно ${amount}!* ❗️❗️⚠️
_Если вы оплатите другую сумму, деньги не поступят на баланс._

*После успешной оплаты баланс будет автоматически пополнен.*"""
            
            bot_msg = await safe_telegram_call(update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            ))
            
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
                context.user_data['last_bot_message_text'] = message_text
        else:
            from utils.ui_utils import PaymentFlowUI
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_invoice_error(error_msg), parse_mode='Markdown'))
            
    except ValueError:
        from utils.ui_utils import PaymentFlowUI
        await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_invalid_format(), parse_mode='Markdown'))


async def handle_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom top-up amount input and create Oxapay invoice directly"""
    from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
    from server import create_oxapay_invoice, insert_payment, Payment, TOPUP_AMOUNT
    import time
    import uuid
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ConversationHandler
    
    # Mark previous message as selected (remove "Отмена" button)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    try:
        amount_text = update.message.text.strip()
        
        # Validate amount
        try:
            topup_amount = float(amount_text)
        except ValueError:
            await safe_telegram_call(update.message.reply_text(
                "❌ Неверный формат суммы. Введите число, например: 50"
            ))
            return TOPUP_AMOUNT
        
        # Check limits
        if topup_amount < 10:
            await safe_telegram_call(update.message.reply_text(
                "❌ Минимальная сумма пополнения: $10"
            ))
            return TOPUP_AMOUNT
        
        if topup_amount > 10000:
            await safe_telegram_call(update.message.reply_text(
                "❌ Максимальная сумма пополнения: $10,000"
            ))
            return TOPUP_AMOUNT
        
        telegram_id = update.effective_user.id
        
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            await safe_telegram_call(update.message.reply_text("❌ Пользователь не найден"))
            return ConversationHandler.END
        
        # Create Oxapay invoice
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
            payment = Payment(
                order_id=f"topup_{user.get('id', user.get('_id', str(user['telegram_id'])))}",
                amount=topup_amount,
                invoice_id=track_id,
                pay_url=pay_link,
                status="pending"
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            payment_dict['telegram_id'] = telegram_id
            payment_dict['track_id'] = track_id  # Store track_id for webhook lookup
            payment_dict['type'] = 'topup'
            await insert_payment(payment_dict)
            
            keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""✅ *Счёт на пополнение создан!*

💵 *Сумма: ${topup_amount}*
🪙 *Криптовалюта: Любая из доступных*

*Нажмите кнопку "Оплатить" для перехода на страницу оплаты.*
*На платежной странице вы сможете выбрать удобную криптовалюту.*

⚠️❗️❗️ *ВАЖНО: Оплатите точно ${topup_amount}!* ❗️❗️⚠️
_Если вы оплатите другую сумму, деньги НЕ поступят на баланс!_

*После успешной оплаты баланс будет автоматически пополнен.*"""
            
            # 🚀 PERFORMANCE: Send message and save to DB in background
            async def send_payment_message():
                bot_msg = await safe_telegram_call(update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                ))
                
                if bot_msg:
                    # Save message_id in payment for later removal of button
                    from repositories import get_repositories
                    repos = get_repositories()
                    await repos.payments.update_payment(
                        {"invoice_id": track_id},
                        {
                            "payment_message_id": bot_msg.message_id,
                            "payment_message_text": message_text
                        }
                    )
                    
                    context.user_data['last_bot_message_id'] = bot_msg.message_id
                    context.user_data['last_bot_message_text'] = message_text
            
            asyncio.create_task(send_payment_message())
            
            return ConversationHandler.END
        else:
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(update.message.reply_text(f"❌ *Ошибка создания инвойса:* {error_msg}", parse_mode='Markdown'))
            return ConversationHandler.END
    
    except ValueError as e:
        logger.warning(f"Invalid topup amount: {e}")
        await safe_telegram_call(update.message.reply_text(f"❌ Неверная сумма пополнения"))
        return ConversationHandler.END
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error in topup: {e}", exc_info=True)
        await safe_telegram_call(update.message.reply_text(f"❌ Ошибка базы данных. Попробуйте позже."))
        return ConversationHandler.END
    except telegram.error.TelegramError as e:
        logger.error(f"Telegram error in topup: {e}", exc_info=True)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Unexpected error in topup handler: {e}", exc_info=True)
        await safe_telegram_call(update.message.reply_text(f"❌ Ошибка: {str(e)}"))
        return ConversationHandler.END


async def handle_topup_crypto_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cryptocurrency selection for top-up"""
    from handlers.common_handlers import safe_telegram_call
    from handlers.order_flow.cancellation import cancel_order, confirm_cancel_order, return_to_order
    from server import create_oxapay_invoice, insert_payment, Payment
    import time
    import uuid
    from telegram.ext import ConversationHandler
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    try:
        # Extract cryptocurrency from callback data
        crypto_asset = query.data.replace('topup_crypto_', '').upper()
        topup_amount = context.user_data.get('topup_amount')
        
        if not topup_amount:
            await safe_telegram_call(query.message.reply_text("❌ Ошибка: сумма не найдена. Начните заново."))
            return ConversationHandler.END
        
        telegram_id = query.from_user.id
        
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            await safe_telegram_call(query.message.reply_text("❌ Пользователь не найден"))
            return ConversationHandler.END
        
        # Create Oxapay invoice for top-up
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
            payment = Payment(
                order_id=f"topup_{user.get('id', user.get('_id', str(user['telegram_id'])))}",
                amount=topup_amount,
                invoice_id=track_id,
                pay_url=pay_link,
                currency=crypto_asset,
                status="pending"
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            payment_dict['telegram_id'] = telegram_id
            payment_dict['track_id'] = track_id  # Store track_id for webhook lookup
            payment_dict['type'] = 'topup'
            await insert_payment(payment_dict)
            
            keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await safe_telegram_call(query.message.reply_text(
                f"""✅ *Счёт на пополнение создан!*

💵 *Сумма: ${topup_amount}*
🪙 *Криптовалюта: Любая из доступных*

*Нажмите кнопку "Оплатить" для перехода на страницу оплаты.*
*На платежной странице вы сможете выбрать удобную криптовалюту.*

⚠️❗️❗️ *ВАЖНО: Оплатите точно ${topup_amount}!* ❗️❗️⚠️
_Если вы оплатите другую сумму, деньги НЕ поступят на баланс!_

*После успешной оплаты баланс будет автоматически пополнен.*""",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            ))
        else:
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(query.message.reply_text(f"❌ Ошибка создания инвойса: {error_msg}"))
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Crypto selection handling error: {e}")
        await safe_telegram_call(query.message.reply_text(f"❌ Ошибка: {str(e)}"))
        return ConversationHandler.END

