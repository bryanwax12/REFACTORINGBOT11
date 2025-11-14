"""
Pytest configuration and shared fixtures
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone
from typing import Dict, Any


# ============================================================
# MOCK DATABASE FIXTURES
# ============================================================

@pytest.fixture
def mock_db():
    """Mock MongoDB database"""
    db = Mock()
    
    # Mock collections
    db.users = AsyncMock()
    db.orders = AsyncMock()
    db.templates = AsyncMock()
    db.payments = AsyncMock()
    db.pending_orders = AsyncMock()
    
    return db


@pytest.fixture
def mock_user():
    """Mock user data"""
    return {
        'id': 'user_123',
        'telegram_id': 123456789,
        'balance': 50.00,
        'created_at': datetime.now(timezone.utc)
    }


# ============================================================
# ORDER DATA FIXTURES
# ============================================================

@pytest.fixture
def sample_order_data():
    """Sample order data for testing"""
    return {
        'from_name': 'John Doe',
        'from_street': '123 Main St',
        'from_street2': 'Apt 4',
        'from_city': 'New York',
        'from_state': 'NY',
        'from_zip': '10001',
        'from_phone': '+15551234567',
        'to_name': 'Jane Smith',
        'to_street': '456 Oak Ave',
        'to_street2': '',
        'to_city': 'Los Angeles',
        'to_state': 'CA',
        'to_zip': '90001',
        'to_phone': '+15559876543',
        'weight': 5.0,
        'length': 12,
        'width': 8,
        'height': 6
    }


@pytest.fixture
def incomplete_order_data():
    """Incomplete order data for validation testing"""
    return {
        'from_name': 'John Doe',
        'from_street': '123 Main St',
        'from_city': 'New York',
        # Missing: from_state, from_zip, to fields, weight
    }


@pytest.fixture
def sample_shipstation_rate():
    """Sample ShipStation rate response"""
    return {
        'rate_id': 'rate_12345',
        'carrier_code': 'ups',
        'carrier_friendly_name': 'UPS',
        'service_code': 'ups_ground',
        'service_type': 'Ground',
        'shipping_amount': {
            'amount': 15.50,
            'currency': 'USD'
        },
        'delivery_days': 3,
        'carrier_delivery_days': '3-5',
        'guaranteed_service': False
    }


@pytest.fixture
def sample_rates_list(sample_shipstation_rate):
    """List of sample rates"""
    rates = []
    
    # UPS rates
    for i, service in enumerate(['ups_ground', 'ups_3_day_select', 'ups_next_day_air']):
        rate = sample_shipstation_rate.copy()
        rate['service_code'] = service
        rate['service_type'] = service.replace('_', ' ').title()
        rate['shipping_amount']['amount'] = 15.50 + (i * 10)
        rate['delivery_days'] = 3 - i
        rates.append(rate)
    
    # FedEx rates
    for i, service in enumerate(['fedex_ground', 'fedex_2day']):
        rate = sample_shipstation_rate.copy()
        rate['carrier_code'] = 'fedex_walleted'
        rate['carrier_friendly_name'] = 'FedEx'
        rate['service_code'] = service
        rate['service_type'] = service.replace('_', ' ').title()
        rate['shipping_amount']['amount'] = 16.50 + (i * 8)
        rate['delivery_days'] = 2 - i
        rates.append(rate)
    
    return rates


# ============================================================
# TEMPLATE FIXTURES
# ============================================================

@pytest.fixture
def sample_template():
    """Sample template data"""
    return {
        'id': 'template_123',
        'telegram_id': 123456789,
        'name': 'Home to Work',
        'from_name': 'John Doe',
        'from_street1': '123 Main St',
        'from_street2': 'Apt 4',
        'from_city': 'New York',
        'from_state': 'NY',
        'from_zip': '10001',
        'from_phone': '+15551234567',
        'to_name': 'Jane Smith',
        'to_street1': '456 Oak Ave',
        'to_street2': '',
        'to_city': 'Los Angeles',
        'to_state': 'CA',
        'to_zip': '90001',
        'to_phone': '+15559876543',
        'weight': '5',
        'length': '12',
        'width': '8',
        'height': '6',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }


# ============================================================
# MOCK FUNCTIONS FIXTURES
# ============================================================

@pytest.fixture
def mock_find_user_func(mock_user):
    """Mock find_user_by_telegram_id function"""
    async def find_user(telegram_id: int):
        if telegram_id == mock_user['telegram_id']:
            return mock_user
        return None
    return find_user


@pytest.fixture
def mock_find_template_func(sample_template):
    """Mock find_template function"""
    async def find_template(template_id: str, projection=None):
        if template_id == sample_template['id']:
            return sample_template
        return None
    return find_template


@pytest.fixture
def mock_insert_func():
    """Mock insert function"""
    async def insert(data: Dict[str, Any]):
        return Mock(inserted_id='new_id_123')
    return insert


@pytest.fixture
def mock_update_func():
    """Mock update function"""
    async def update(id: str, data: Dict[str, Any]):
        return Mock(modified_count=1)
    return update


@pytest.fixture
def mock_delete_func():
    """Mock delete function"""
    async def delete(id: str):
        return Mock(deleted_count=1)
    return delete


# ============================================================
# TELEGRAM MOCK FIXTURES
# ============================================================

@pytest.fixture
def mock_telegram_context():
    """Mock Telegram context"""
    context = Mock()
    context.user_data = {}
    return context


@pytest.fixture
def mock_telegram_update():
    """Mock Telegram update"""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 123456789
    update.message = Mock()
    update.callback_query = Mock()
    return update


# ============================================================
# UTILITY FIXTURES
# ============================================================

@pytest.fixture
def mock_safe_telegram_call():
    """Mock safe_telegram_call function"""
    async def safe_call(coro):
        return await coro if hasattr(coro, '__await__') else coro
    return safe_call


@pytest.fixture
def sample_carrier_ids():
    """Sample carrier IDs for ShipStation"""
    return [
        'se-123456',  # UPS
        'se-234567',  # FedEx
        'se-345678'   # USPS
    ]
