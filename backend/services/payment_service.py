"""
Payment Service
Сервис для управления платежами
"""
import logging
from typing import Optional, Dict, Any, Tuple
import pymongo.errors

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Сервис для управления платежами
    Инкапсулирует бизнес-логику работы с платежами
    """
    
    def __init__(self, payment_repo, user_repo):
        """
        Инициализация сервиса
        
        Args:
            payment_repo: PaymentRepository
            user_repo: UserRepository
        """
        self.payment_repo = payment_repo
        self.user_repo = user_repo
    
    async def check_balance_sufficient(
        self,
        telegram_id: int,
        amount: float
    ) -> Tuple[bool, float]:
        """
        Проверить достаточность баланса
        
        Args:
            telegram_id: Telegram ID пользователя
            amount: Требуемая сумма
            
        Returns:
            (sufficient, current_balance)
        """
        balance = await self.user_repo.get_balance(telegram_id)
        return balance >= amount, balance
    
    async def process_balance_payment(
        self,
        telegram_id: int,
        order_id: str,
        amount: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Обработать платеж с баланса
        
        Args:
            telegram_id: Telegram ID пользователя
            order_id: ID заказа
            amount: Сумма
            
        Returns:
            (success, error_message)
        """
        # Проверить достаточность баланса
        sufficient, balance = await self.check_balance_sufficient(telegram_id, amount)
        
        if not sufficient:
            return False, f"Insufficient balance. Required: ${amount:.2f}, Available: ${balance:.2f}"
        
        # Списать с баланса
        success = await self.user_repo.update_balance(
            telegram_id,
            amount,
            operation="subtract"
        )
        
        if not success:
            return False, "Failed to deduct balance"
        
        return True, None
    
    async def add_balance(
        self,
        telegram_id: int,
        amount: float,
        description: str = "Balance topup"
    ) -> bool:
        """
        Добавить средства на баланс
        
        Args:
            telegram_id: Telegram ID пользователя
            amount: Сумма
            description: Описание
            
        Returns:
            True если успешно
        """
        return await self.user_repo.update_balance(
            telegram_id,
            amount,
            description
        )
    
    @staticmethod
    def validate_topup_amount(amount: float) -> Tuple[bool, Optional[str]]:
        """
        Валидировать сумму пополнения
        
        Args:
            amount: Сумма
            
        Returns:
            (is_valid, error_message)
        """
        if amount < 10:
            return False, "❌ Минимальная сумма пополнения: $10"
        
        if amount > 10000:
            return False, "❌ Максимальная сумма пополнения: $10,000"
        
        return True, None


# ============================================================
# LEGACY FUNCTIONS (for backward compatibility)
# ============================================================


# ============================================================
# BALANCE OPERATIONS
# ============================================================

async def get_user_balance(telegram_id: int, find_user_func) -> float:
    """
    Get user's current balance
    
    Args:
        telegram_id: Telegram user ID
        find_user_func: Function to find user by telegram_id
    
    Returns:
        Current balance as float
    """
    user = await find_user_func(telegram_id)
    return user.get('balance', 0.0) if user else 0.0


async def add_balance(
    telegram_id: int,
    amount: float,
    db,
    find_user_func
) -> Tuple[bool, float, Optional[str]]:
    """
    Add funds to user balance
    
    Args:
        telegram_id: Telegram user ID
        amount: Amount to add
        db: Database connection
        find_user_func: Function to find user
    
    Returns:
        (success, new_balance, error_message)
    """
    try:
        user = await find_user_func(telegram_id)
        if not user:
            return False, 0.0, "User not found"
        
        new_balance = user.get('balance', 0.0) + amount
        
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"balance": new_balance}}
        )
        
        logger.info(f"💰 Balance added: user={telegram_id}, amount=${amount:.2f}, new_balance=${new_balance:.2f}")
        return True, new_balance, None
    
    except pymongo.errors.ConnectionFailure as e:
        logger.error(f"❌ MongoDB connection error adding balance: {e}", exc_info=True)
        return False, 0.0, "Database connection error"
    except pymongo.errors.PyMongoError as e:
        logger.error(f"❌ MongoDB error adding balance: {e}", exc_info=True)
        return False, 0.0, "Database error"
    except Exception as e:
        logger.error(f"❌ Unexpected error adding balance: {e}", exc_info=True)
        return False, 0.0, str(e)


async def deduct_balance(
    telegram_id: int,
    amount: float,
    db,
    find_user_func
) -> Tuple[bool, float, Optional[str]]:
    """
    Deduct funds from user balance
    
    Args:
        telegram_id: Telegram user ID
        amount: Amount to deduct
        db: Database connection
        find_user_func: Function to find user
    
    Returns:
        (success, new_balance, error_message)
    """
    try:
        user = await find_user_func(telegram_id)
        if not user:
            return False, 0.0, "User not found"
        
        current_balance = user.get('balance', 0.0)
        
        if current_balance < amount:
            return False, current_balance, "Insufficient balance"
        
        new_balance = current_balance - amount
        
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"balance": new_balance}}
        )
        
        logger.info(f"💳 Balance deducted: user={telegram_id}, amount=${amount:.2f}, new_balance=${new_balance:.2f}")
        return True, new_balance, None
    
    except pymongo.errors.ConnectionFailure as e:
        logger.error(f"❌ MongoDB connection error deducting balance: {e}", exc_info=True)
        return False, 0.0, "Database connection error"
    except pymongo.errors.PyMongoError as e:
        logger.error(f"❌ MongoDB error deducting balance: {e}", exc_info=True)
        return False, 0.0, "Database error"
    except Exception as e:
        logger.error(f"❌ Unexpected error deducting balance: {e}", exc_info=True)
        return False, 0.0, str(e)


# ============================================================
# PAYMENT VALIDATION
# ============================================================

def validate_topup_amount(amount: float) -> Tuple[bool, Optional[str]]:
    """
    Validate topup amount
    
    Args:
        amount: Amount to validate
    
    Returns:
        (is_valid, error_message)
    """
    if amount < 10:
        from utils.ui_utils import PaymentFlowUI
        return False, PaymentFlowUI.topup_amount_too_small()
    
    if amount > 10000:
        from utils.ui_utils import PaymentFlowUI
        return False, PaymentFlowUI.topup_amount_too_large()
    
    return True, None


def validate_payment_amount(amount: float, user_balance: float) -> Tuple[bool, Optional[str]]:
    """
    Validate if payment can be processed
    
    Args:
        amount: Payment amount
        user_balance: User's current balance
    
    Returns:
        (can_pay, error_message)
    """
    if amount <= 0:
        return False, "Invalid payment amount"
    
    if user_balance < amount:
        from utils.ui_utils import PaymentFlowUI
        return False, PaymentFlowUI.insufficient_balance_error()
    
    return True, None


# ============================================================
# PAYMENT PROCESSING
# ============================================================

async def process_balance_payment(
    telegram_id: int,
    amount: float,
    order_id: str,
    db,
    find_user_func,
    update_order_func
) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Process payment from user balance
    
    Args:
        telegram_id: Telegram user ID
        amount: Payment amount
        order_id: Order ID to update
        db: Database connection
        find_user_func: Function to find user
        update_order_func: Function to update order
    
    Returns:
        (success, new_balance, error_message)
    """
    try:
        # Get current balance
        user = await find_user_func(telegram_id)
        if not user:
            return False, None, "User not found"
        
        current_balance = user.get('balance', 0.0)
        
        # Validate
        is_valid, error_msg = validate_payment_amount(amount, current_balance)
        if not is_valid:
            return False, current_balance, error_msg
        
        # Deduct balance
        success, new_balance, error = await deduct_balance(
            telegram_id, amount, db, find_user_func
        )
        
        if not success:
            return False, current_balance, error
        
        # Update order status
        await update_order_func(order_id, {"payment_status": "paid"})
        
        logger.info(f"✅ Payment processed: order={order_id}, amount=${amount:.2f}, new_balance=${new_balance:.2f}")
        return True, new_balance, None
        
    except Exception as e:
        logger.error(f"❌ Error processing payment: {e}")
        return False, None, str(e)


# ============================================================
# INVOICE CREATION
# ============================================================

async def create_payment_invoice(
    telegram_id: int,
    amount: float,
    order_id: str,
    description: str,
    create_oxapay_invoice_func,
    insert_payment_func
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Create payment invoice for topup
    
    Args:
        telegram_id: Telegram user ID
        amount: Amount to topup
        order_id: Unique order ID
        description: Payment description
        create_oxapay_invoice_func: Function to create Oxapay invoice
        insert_payment_func: Function to insert payment record
    
    Returns:
        (success, invoice_data, error_message)
    """
    try:
        # Validate amount
        is_valid, error_msg = validate_topup_amount(amount)
        if not is_valid:
            return False, None, error_msg
        
        # Create invoice
        invoice_result = await create_oxapay_invoice_func(
            amount=amount,
            order_id=order_id,
            description=description
        )
        
        if not invoice_result.get('success'):
            error = invoice_result.get('error', 'Unknown error')
            return False, None, error
        
        # Save payment record
        track_id = invoice_result['trackId']
        pay_link = invoice_result['payLink']
        
        payment_dict = {
            'order_id': f"topup_{telegram_id}",
            'amount': amount,
            'invoice_id': track_id,
            'track_id': track_id,  # Store track_id for webhook lookup
            'pay_url': pay_link,
            'status': 'pending',
            'telegram_id': telegram_id,
            'type': 'topup'
        }
        
        await insert_payment_func(payment_dict)
        
        logger.info(f"💳 Invoice created: telegram_id={telegram_id}, amount=${amount:.2f}, track_id={track_id}")
        
        return True, {
            'track_id': track_id,
            'pay_link': pay_link,
            'amount': amount
        }, None
        
    except Exception as e:
        logger.error(f"❌ Error creating invoice: {e}")
        return False, None, str(e)


# ============================================================
# MODULE DOCUMENTATION
# ============================================================

"""
PAYMENT SERVICE ARCHITECTURE:

This module centralizes all payment-related operations:
1. Balance management (add, deduct, check)
2. Payment validation
3. Payment processing
4. Invoice creation
5. Transaction logging

BENEFITS:
- Single source of truth for payment logic
- Easy to test payment flows
- Centralized validation
- Transaction safety
- Clear error handling
"""
