"""
Unit tests for Payment Service
Tests all 8 functions in services/payment_service.py
"""
import pytest
from unittest.mock import AsyncMock
from services.payment_service import (
    get_user_balance,
    add_balance,
    deduct_balance,
    validate_topup_amount,
    validate_payment_amount,
    process_balance_payment,
    create_payment_invoice
)


# ============================================================
# BALANCE OPERATIONS TESTS
# ============================================================

@pytest.mark.asyncio
async def test_get_user_balance_exists(mock_user, mock_find_user_func):
    """Test getting balance for existing user"""
    balance = await get_user_balance(
        telegram_id=mock_user['telegram_id'],
        find_user_func=mock_find_user_func
    )
    
    assert balance == mock_user['balance']


@pytest.mark.asyncio
async def test_get_user_balance_not_exists():
    """Test getting balance for non-existent user"""
    async def find_none(telegram_id):
        return None
    
    balance = await get_user_balance(
        telegram_id=999999,
        find_user_func=find_none
    )
    
    assert balance == 0.0


@pytest.mark.asyncio
async def test_add_balance_success(mock_db, mock_user, mock_find_user_func):
    """Test successful balance addition"""
    mock_db.users.update_one = AsyncMock()
    
    success, new_balance, error = await add_balance(
        telegram_id=mock_user['telegram_id'],
        amount=25.00,
        db=mock_db,
        find_user_func=mock_find_user_func
    )
    
    assert success is True
    assert new_balance == 75.00  # 50 + 25
    assert error is None
    mock_db.users.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_add_balance_user_not_found(mock_db):
    """Test adding balance to non-existent user"""
    async def find_none(telegram_id):
        return None
    
    success, new_balance, error = await add_balance(
        telegram_id=999999,
        amount=25.00,
        db=mock_db,
        find_user_func=find_none
    )
    
    assert success is False
    assert new_balance == 0.0
    assert error == "User not found"


@pytest.mark.asyncio
async def test_deduct_balance_success(mock_db, mock_user, mock_find_user_func):
    """Test successful balance deduction"""
    mock_db.users.update_one = AsyncMock()
    
    success, new_balance, error = await deduct_balance(
        telegram_id=mock_user['telegram_id'],
        amount=20.00,
        db=mock_db,
        find_user_func=mock_find_user_func
    )
    
    assert success is True
    assert new_balance == 30.00  # 50 - 20
    assert error is None


@pytest.mark.asyncio
async def test_deduct_balance_insufficient(mock_db, mock_user, mock_find_user_func):
    """Test deducting more than available balance"""
    success, new_balance, error = await deduct_balance(
        telegram_id=mock_user['telegram_id'],
        amount=100.00,  # More than 50.00 balance
        db=mock_db,
        find_user_func=mock_find_user_func
    )
    
    assert success is False
    assert new_balance == mock_user['balance']  # Unchanged
    assert error == "Insufficient balance"


@pytest.mark.asyncio
async def test_deduct_balance_user_not_found(mock_db):
    """Test deducting from non-existent user"""
    async def find_none(telegram_id):
        return None
    
    success, new_balance, error = await deduct_balance(
        telegram_id=999999,
        amount=10.00,
        db=mock_db,
        find_user_func=find_none
    )
    
    assert success is False
    assert error == "User not found"


# ============================================================
# VALIDATION TESTS
# ============================================================

def test_validate_topup_amount_valid():
    """Test validating valid topup amount"""
    is_valid, error = validate_topup_amount(25.00)
    
    assert is_valid is True
    assert error is None


def test_validate_topup_amount_too_small():
    """Test validating topup amount below minimum"""
    is_valid, error = validate_topup_amount(5.00)
    
    assert is_valid is False
    assert error is not None
    assert '10' in error


def test_validate_topup_amount_too_large():
    """Test validating topup amount above maximum"""
    is_valid, error = validate_topup_amount(15000.00)
    
    assert is_valid is False
    assert error is not None
    assert '10,000' in error or '10000' in error


def test_validate_topup_amount_edge_cases():
    """Test edge cases for topup validation"""
    # Exactly minimum
    is_valid, _ = validate_topup_amount(10.00)
    assert is_valid is True
    
    # Exactly maximum
    is_valid, _ = validate_topup_amount(10000.00)
    assert is_valid is True
    
    # Just below minimum
    is_valid, _ = validate_topup_amount(9.99)
    assert is_valid is False
    
    # Just above maximum
    is_valid, _ = validate_topup_amount(10000.01)
    assert is_valid is False


def test_validate_payment_amount_valid():
    """Test validating valid payment amount"""
    is_valid, error = validate_payment_amount(
        amount=25.00,
        user_balance=50.00
    )
    
    assert is_valid is True
    assert error is None


def test_validate_payment_amount_insufficient_balance():
    """Test payment validation with insufficient balance"""
    is_valid, error = validate_payment_amount(
        amount=75.00,
        user_balance=50.00
    )
    
    assert is_valid is False
    assert error is not None


def test_validate_payment_amount_invalid():
    """Test payment validation with invalid amount"""
    is_valid, error = validate_payment_amount(
        amount=0,
        user_balance=50.00
    )
    
    assert is_valid is False
    assert error == "Invalid payment amount"
    
    is_valid, error = validate_payment_amount(
        amount=-10,
        user_balance=50.00
    )
    
    assert is_valid is False


# ============================================================
# PAYMENT PROCESSING TESTS
# ============================================================

@pytest.mark.asyncio
async def test_process_balance_payment_success(mock_db, mock_user, mock_find_user_func):
    """Test successful payment processing"""
    mock_db.users.update_one = AsyncMock()
    
    async def mock_update_order(order_id, data):
        pass
    
    success, new_balance, error = await process_balance_payment(
        telegram_id=mock_user['telegram_id'],
        amount=20.00,
        order_id='order_123',
        db=mock_db,
        find_user_func=mock_find_user_func,
        update_order_func=mock_update_order
    )
    
    assert success is True
    assert new_balance == 30.00  # 50 - 20
    assert error is None


@pytest.mark.asyncio
async def test_process_balance_payment_insufficient_balance(mock_db, mock_user, mock_find_user_func):
    """Test payment with insufficient balance"""
    async def mock_update_order(order_id, data):
        pass
    
    success, new_balance, error = await process_balance_payment(
        telegram_id=mock_user['telegram_id'],
        amount=100.00,
        order_id='order_123',
        db=mock_db,
        find_user_func=mock_find_user_func,
        update_order_func=mock_update_order
    )
    
    assert success is False
    assert error is not None


@pytest.mark.asyncio
async def test_process_balance_payment_user_not_found(mock_db):
    """Test payment for non-existent user"""
    async def find_none(telegram_id):
        return None
    
    async def mock_update_order(order_id, data):
        pass
    
    success, new_balance, error = await process_balance_payment(
        telegram_id=999999,
        amount=20.00,
        order_id='order_123',
        db=mock_db,
        find_user_func=find_none,
        update_order_func=mock_update_order
    )
    
    assert success is False
    assert error == "User not found"


# ============================================================
# INVOICE CREATION TESTS
# ============================================================

@pytest.mark.asyncio
async def test_create_payment_invoice_success():
    """Test successful invoice creation"""
    async def mock_create_invoice(amount, order_id, description):
        return {
            'success': True,
            'trackId': 'track_123',
            'payLink': 'https://pay.example.com/invoice_123'
        }
    
    async def mock_insert_payment(data):
        pass
    
    success, invoice_data, error = await create_payment_invoice(
        telegram_id=123456,
        amount=50.00,
        order_id='order_123',
        description='Test topup',
        create_oxapay_invoice_func=mock_create_invoice,
        insert_payment_func=mock_insert_payment
    )
    
    assert success is True
    assert invoice_data is not None
    assert invoice_data['track_id'] == 'track_123'
    assert invoice_data['pay_link'] == 'https://pay.example.com/invoice_123'
    assert error is None


@pytest.mark.asyncio
async def test_create_payment_invoice_amount_too_small():
    """Test invoice creation with amount below minimum"""
    async def mock_create_invoice(amount, order_id, description):
        return {'success': True}
    
    async def mock_insert_payment(data):
        pass
    
    success, invoice_data, error = await create_payment_invoice(
        telegram_id=123456,
        amount=5.00,  # Below $10 minimum
        order_id='order_123',
        description='Test topup',
        create_oxapay_invoice_func=mock_create_invoice,
        insert_payment_func=mock_insert_payment
    )
    
    assert success is False
    assert error is not None


@pytest.mark.asyncio
async def test_create_payment_invoice_api_error():
    """Test invoice creation when API returns error"""
    async def mock_create_invoice_error(amount, order_id, description):
        return {
            'success': False,
            'error': 'API error message'
        }
    
    async def mock_insert_payment(data):
        pass
    
    success, invoice_data, error = await create_payment_invoice(
        telegram_id=123456,
        amount=50.00,
        order_id='order_123',
        description='Test topup',
        create_oxapay_invoice_func=mock_create_invoice_error,
        insert_payment_func=mock_insert_payment
    )
    
    assert success is False
    assert error == 'API error message'


# ============================================================
# INTEGRATION TESTS
# ============================================================

@pytest.mark.asyncio
async def test_full_payment_flow(mock_db, mock_user, mock_find_user_func):
    """Test complete payment flow from validation to processing"""
    mock_db.users.update_one = AsyncMock()
    
    # 1. Validate amount
    is_valid, error = validate_payment_amount(30.00, mock_user['balance'])
    assert is_valid
    
    # 2. Process payment
    async def mock_update_order(order_id, data):
        assert data['payment_status'] == 'paid'
    
    success, new_balance, error = await process_balance_payment(
        telegram_id=mock_user['telegram_id'],
        amount=30.00,
        order_id='order_123',
        db=mock_db,
        find_user_func=mock_find_user_func,
        update_order_func=mock_update_order
    )
    
    assert success is True
    assert new_balance == 20.00


@pytest.mark.asyncio
async def test_full_topup_flow():
    """Test complete topup flow from validation to invoice"""
    # 1. Validate amount
    is_valid, error = validate_topup_amount(50.00)
    assert is_valid
    
    # 2. Create invoice
    async def mock_create_invoice(amount, order_id, description):
        return {
            'success': True,
            'trackId': 'track_xyz',
            'payLink': 'https://pay.test/xyz'
        }
    
    async def mock_insert_payment(data):
        assert data['amount'] == 50.00
        assert data['type'] == 'topup'
    
    success, invoice_data, error = await create_payment_invoice(
        telegram_id=123456,
        amount=50.00,
        order_id='topup_123456',
        description='Balance topup',
        create_oxapay_invoice_func=mock_create_invoice,
        insert_payment_func=mock_insert_payment
    )
    
    assert success is True
    assert invoice_data['amount'] == 50.00


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
