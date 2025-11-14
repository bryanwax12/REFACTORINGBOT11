"""
Tests for Repository Pattern
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from repositories.user_repository import UserRepository
from repositories.order_repository import OrderRepository


class TestUserRepository:
    """Тесты для UserRepository"""
    
    @pytest_asyncio.fixture
    async def mock_db(self):
        """Mock database"""
        db = MagicMock()
        db.users = AsyncMock()
        return db
    
    @pytest_asyncio.fixture
    async def user_repo(self, mock_db):
        """User repository fixture"""
        return UserRepository(mock_db)
    
    @pytest.mark.asyncio
    async def test_find_by_telegram_id(self, user_repo):
        """Тест поиска по telegram_id"""
        # Mock response
        user_repo.collection.find_one = AsyncMock(return_value={
            "telegram_id": 12345,
            "username": "testuser",
            "balance": 100.0
        })
        
        result = await user_repo.find_by_telegram_id(12345)
        
        assert result is not None
        assert result['telegram_id'] == 12345
        assert result['username'] == 'testuser'
    
    @pytest.mark.asyncio
    async def test_create_user(self, user_repo):
        """Тест создания пользователя"""
        user_repo.collection.insert_one = AsyncMock()
        
        user = await user_repo.create_user(
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            initial_balance=50.0
        )
        
        assert user['telegram_id'] == 12345
        assert user['username'] == 'testuser'
        assert user['balance'] == 50.0
        assert 'created_at' in user
    
    @pytest.mark.asyncio
    async def test_update_balance_add(self, user_repo):
        """Тест добавления к балансу"""
        user_repo.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        result = await user_repo.update_balance(12345, 50.0, operation="add")
        
        assert result == True
        
        # Проверить что вызван update_one с правильными параметрами
        call_args = user_repo.collection.update_one.call_args
        assert call_args[0][0] == {"telegram_id": 12345}
        assert call_args[0][1]['$inc']['balance'] == 50.0
    
    @pytest.mark.asyncio
    async def test_update_balance_subtract(self, user_repo):
        """Тест вычитания из баланса"""
        user_repo.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        result = await user_repo.update_balance(12345, 30.0, operation="subtract")
        
        assert result == True
        
        call_args = user_repo.collection.update_one.call_args
        assert call_args[0][1]['$inc']['balance'] == -30.0
    
    @pytest.mark.asyncio
    async def test_is_admin(self, user_repo):
        """Тест проверки admin статуса"""
        user_repo.collection.find_one = AsyncMock(return_value={
            "telegram_id": 12345,
            "is_admin": True
        })
        
        result = await user_repo.is_admin(12345)
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_block_user(self, user_repo):
        """Тест блокировки пользователя"""
        user_repo.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        result = await user_repo.block_user(12345)
        
        assert result == True


class TestOrderRepository:
    """Тесты для OrderRepository"""
    
    @pytest_asyncio.fixture
    async def mock_db(self):
        """Mock database"""
        db = MagicMock()
        db.orders = AsyncMock()
        return db
    
    @pytest_asyncio.fixture
    async def order_repo(self, mock_db):
        """Order repository fixture"""
        return OrderRepository(mock_db)
    
    @pytest.mark.asyncio
    async def test_create_order(self, order_repo):
        """Тест создания заказа"""
        order_repo.collection.insert_one = AsyncMock()
        
        order = await order_repo.create_order(
            user_id=12345,
            order_data={"total_cost": 50.0},
            auto_generate_id=True
        )
        
        assert order['user_id'] == 12345
        assert order['status'] == 'pending'
        assert order['payment_status'] == 'unpaid'
        assert 'order_id' in order
        assert 'created_at' in order
    
    @pytest.mark.asyncio
    async def test_find_by_order_id(self, order_repo):
        """Тест поиска по order_id"""
        order_repo.collection.find_one = AsyncMock(return_value={
            "order_id": "ORDER123",
            "user_id": 12345,
            "status": "pending"
        })
        
        result = await order_repo.find_by_order_id("ORDER123")
        
        assert result is not None
        assert result['order_id'] == "ORDER123"
    
    @pytest.mark.asyncio
    async def test_update_status(self, order_repo):
        """Тест обновления статуса"""
        order_repo.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        result = await order_repo.update_status("ORDER123", "completed", notes="Done")
        
        assert result == True
        
        call_args = order_repo.collection.update_one.call_args
        assert call_args[0][0] == {"order_id": "ORDER123"}
        assert call_args[0][1]['$set']['status'] == "completed"
        assert call_args[0][1]['$set']['status_notes'] == "Done"
    
    @pytest.mark.asyncio
    async def test_update_payment_status(self, order_repo):
        """Тест обновления статуса оплаты"""
        order_repo.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        result = await order_repo.update_payment_status(
            "ORDER123",
            "paid",
            payment_data={"invoice_id": "INV123"}
        )
        
        assert result == True
        
        call_args = order_repo.collection.update_one.call_args
        assert call_args[0][1]['$set']['payment_status'] == "paid"
        assert call_args[0][1]['$set']['payment_data'] == {"invoice_id": "INV123"}
    
    @pytest.mark.asyncio
    async def test_add_tracking_info(self, order_repo):
        """Тест добавления трекинга"""
        order_repo.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        
        result = await order_repo.add_tracking_info(
            "ORDER123",
            tracking_number="TRACK123",
            carrier="USPS"
        )
        
        assert result == True
