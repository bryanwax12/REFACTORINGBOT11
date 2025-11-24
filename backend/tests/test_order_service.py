"""
Tests for OrderService
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.order_service import OrderService


@pytest.fixture
def mock_repositories():
    """Create mock repositories"""
    order_repo = MagicMock()
    order_repo.find_by_id = AsyncMock()
    order_repo.update_by_id = AsyncMock()
    order_repo.find_with_filter = AsyncMock()
    order_repo.collection = MagicMock()
    order_repo.collection.insert_one = AsyncMock()
    
    user_repo = MagicMock()
    user_repo.find_by_telegram_id = AsyncMock()
    user_repo.get_balance = AsyncMock()
    user_repo.update_balance = AsyncMock()
    
    payment_repo = MagicMock()
    
    return {
        'order': order_repo,
        'user': user_repo,
        'payment': payment_repo
    }


@pytest.fixture
def order_service(mock_repositories):
    """Create OrderService with mock repositories"""
    return OrderService(
        order_repo=mock_repositories['order'],
        user_repo=mock_repositories['user'],
        payment_repo=mock_repositories['payment']
    )


@pytest.mark.asyncio
async def test_get_order_success(order_service, mock_repositories):
    """Test getting order by ID"""
    # Arrange
    order_id = "test-order-123"
    expected_order = {'id': order_id, 'status': 'pending'}
    mock_repositories['order'].find_by_id.return_value = expected_order
    
    # Act
    result = await order_service.get_order(order_id)
    
    # Assert
    assert result == expected_order
    mock_repositories['order'].find_by_id.assert_called_once_with(order_id)


@pytest.mark.asyncio
async def test_update_order_status(order_service, mock_repositories):
    """Test updating order status"""
    # Arrange
    order_id = "test-order-123"
    mock_repositories['order'].update_by_id.return_value = True
    
    # Act
    result = await order_service.update_order_status(
        order_id,
        status='paid',
        payment_status='paid'
    )
    
    # Assert
    assert result is True
    mock_repositories['order'].update_by_id.assert_called_once()


@pytest.mark.asyncio
async def test_process_payment_success(order_service, mock_repositories):
    """Test successful payment processing"""
    # Arrange
    order_id = "test-order-123"
    telegram_id = 12345
    order = {
        'id': order_id,
        'telegram_id': telegram_id,
        'amount': 50.0,
        'status': 'pending'
    }
    
    mock_repositories['order'].find_by_id.return_value = order
    mock_repositories['user'].get_balance.return_value = 100.0
    mock_repositories['user'].update_balance.return_value = True
    mock_repositories['order'].update_by_id.return_value = True
    
    # Act
    result = await order_service.process_payment(order_id, telegram_id, 'balance')
    
    # Assert
    assert result['success'] is True
    assert result['payment_method'] == 'balance'
    assert result['amount'] == 50.0


@pytest.mark.asyncio
async def test_process_payment_insufficient_balance(order_service, mock_repositories):
    """Test payment processing with insufficient balance"""
    # Arrange
    order_id = "test-order-123"
    telegram_id = 12345
    order = {
        'id': order_id,
        'telegram_id': telegram_id,
        'amount': 100.0,
        'status': 'pending'
    }
    
    mock_repositories['order'].find_by_id.return_value = order
    mock_repositories['user'].get_balance.return_value = 50.0
    
    # Act
    result = await order_service.process_payment(order_id, telegram_id, 'balance')
    
    # Assert
    assert result['success'] is False
    assert result['error'] == 'Insufficient balance'
    assert result['required'] == 100.0
    assert result['available'] == 50.0


@pytest.mark.asyncio
async def test_cancel_order_with_refund(order_service, mock_repositories):
    """Test order cancellation with refund"""
    # Arrange
    order_id = "test-order-123"
    telegram_id = 12345
    order = {
        'id': order_id,
        'telegram_id': telegram_id,
        'amount': 50.0,
        'payment_status': 'paid'
    }
    
    mock_repositories['order'].find_by_id.return_value = order
    mock_repositories['user'].update_balance.return_value = True
    mock_repositories['order'].update_by_id.return_value = True
    
    # Act
    result = await order_service.cancel_order(order_id, telegram_id)
    
    # Assert
    assert result['success'] is True
    assert result['refunded'] is True
    assert result['refund_amount'] == 50.0


@pytest.mark.asyncio
async def test_get_user_orders(order_service, mock_repositories):
    """Test getting user orders"""
    # Arrange
    telegram_id = 12345
    expected_orders = [
        {'id': 'order-1', 'status': 'paid'},
        {'id': 'order-2', 'status': 'pending'}
    ]
    mock_repositories['order'].find_with_filter.return_value = expected_orders
    
    # Act
    result = await order_service.get_user_orders(telegram_id, limit=10)
    
    # Assert
    assert result == expected_orders
    mock_repositories['order'].find_with_filter.assert_called_once()


@pytest.mark.asyncio
async def test_add_tracking_info(order_service, mock_repositories):
    """Test adding tracking information"""
    # Arrange
    order_id = "test-order-123"
    tracking_number = "1Z999AA1"
    carrier = "UPS"
    mock_repositories['order'].update_by_id.return_value = True
    
    # Act
    result = await order_service.add_tracking_info(
        order_id,
        tracking_number,
        carrier
    )
    
    # Assert
    assert result is True
    mock_repositories['order'].update_by_id.assert_called_once()
