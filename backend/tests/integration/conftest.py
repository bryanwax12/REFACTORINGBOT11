"""
Shared fixtures for integration tests
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Chat, Message, CallbackQuery
from telegram.ext import ContextTypes
from motor.motor_asyncio import AsyncIOMotorClient
import os


@pytest_asyncio.fixture
async def test_db():
    """Provide a test database connection"""
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db_name = os.environ.get('MONGODB_DB_NAME', 'telegram_shipping_bot')
    db = client[db_name]
    
    yield db
    
    # Cleanup: don't drop collections in production, just clean test data
    # await db.test_orders.delete_many({"test": True})
    client.close()


@pytest.fixture
def mock_telegram_user():
    """Create a mock Telegram user"""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.first_name = "Test"
    user.last_name = "User"
    user.username = "testuser"
    user.is_bot = False
    return user


@pytest.fixture
def mock_telegram_chat():
    """Create a mock Telegram chat"""
    chat = MagicMock(spec=Chat)
    chat.id = 123456789
    chat.type = "private"
    return chat


@pytest.fixture
def mock_telegram_message(mock_telegram_user, mock_telegram_chat):
    """Create a mock Telegram message"""
    message = AsyncMock(spec=Message)
    message.message_id = 1
    message.from_user = mock_telegram_user
    message.chat = mock_telegram_chat
    message.text = "Test message"
    message.reply_text = AsyncMock(return_value=message)
    message.edit_text = AsyncMock()
    message.delete = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_telegram_user, mock_telegram_message):
    """Create a mock CallbackQuery"""
    query = AsyncMock(spec=CallbackQuery)
    query.id = "test_query_id"
    query.from_user = mock_telegram_user
    query.message = mock_telegram_message
    query.data = "test_callback"
    query.answer = AsyncMock()
    return query


@pytest.fixture
def mock_update_message(mock_telegram_message, mock_telegram_user):
    """Create a mock Update with message"""
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.message = mock_telegram_message
    update.effective_user = mock_telegram_user
    update.effective_chat = mock_telegram_message.chat
    update.callback_query = None
    return update


@pytest.fixture
def mock_update_callback(mock_callback_query, mock_telegram_user):
    """Create a mock Update with callback query"""
    update = MagicMock(spec=Update)
    update.update_id = 2
    update.callback_query = mock_callback_query
    update.effective_user = mock_telegram_user
    update.effective_chat = mock_callback_query.message.chat
    update.message = None
    return update


@pytest.fixture
def mock_context():
    """Create a mock Context"""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest_asyncio.fixture
async def integration_context():
    """
    Create a context for integration tests with real-like setup
    """
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    
    # Mock bot with realistic methods
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    context.bot.answer_callback_query = AsyncMock()
    
    return context


@pytest.fixture
def sample_order_data():
    """Sample order data for testing"""
    return {
        "from_name": "John Doe",
        "from_street": "123 Main St",
        "from_street2": "Apt 4",
        "from_city": "New York",
        "from_state": "NY",
        "from_zip": "10001",
        "from_phone": "1234567890",
        "to_name": "Jane Smith",
        "to_street": "456 Oak Ave",
        "to_street2": "",
        "to_city": "Los Angeles",
        "to_state": "CA",
        "to_zip": "90001",
        "to_phone": "9876543210",
        "parcel_weight": "5.5",
        "parcel_length": "12",
        "parcel_width": "8",
        "parcel_height": "6"
    }


@pytest.fixture
def sample_shipping_rate():
    """Sample shipping rate for testing"""
    return {
        "carrier": "USPS",
        "carrier_name": "USPS",
        "service": "Priority Mail",
        "service_type": "Priority Mail",
        "service_code": "usps_priority_mail",
        "amount": 15.50,
        "totalAmount": 15.50,
        "delivery_days": "2-3",
        "rate_id": "rate_123"
    }


@pytest.fixture
def mock_shipstation_response():
    """Mock ShipStation API response"""
    return [
        {
            "serviceName": "USPS Priority Mail",
            "serviceCode": "usps_priority_mail",
            "shipmentCost": 15.50,
            "otherCost": 0.00,
            "carrierName": "USPS",
            "carrierCode": "stamps_com"
        },
        {
            "serviceName": "UPS Ground",
            "serviceCode": "ups_ground",
            "shipmentCost": 18.75,
            "otherCost": 0.00,
            "carrierName": "UPS",
            "carrierCode": "ups_walleted"
        }
    ]


@pytest.fixture
def mock_oxapay_response():
    """Mock Oxapay payment response"""
    return {
        "result": 100,
        "message": "Success",
        "trackId": "test_track_id_123",
        "payLink": "https://payment.oxapay.com/test"
    }
