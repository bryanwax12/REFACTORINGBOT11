"""
Unit Tests for Admin Services
Tests user, stats, and system admin services
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
class TestUserAdminService:
    """Test User Admin Service"""
    
    async def test_get_all_users(self):
        """Test getting all users"""
        from services.admin.user_admin_service import user_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[
            {"telegram_id": 123, "balance": 50},
            {"telegram_id": 456, "balance": 100}
        ])
        mock_db.users.find = MagicMock(return_value=mock_cursor)
        
        # Test
        users = await user_admin_service.get_all_users(mock_db, limit=10)
        
        # Verify
        assert len(users) == 2
        assert users[0]["telegram_id"] == 123
    
    
    async def test_block_user_success(self):
        """Test successful user blocking"""
        from services.admin.user_admin_service import user_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        
        # Mock bot
        mock_bot = AsyncMock()
        
        # Test
        success, message = await user_admin_service.block_user(
            mock_db,
            123456,
            mock_bot,
            send_notification=False
        )
        
        # Verify
        assert success is True
        assert "blocked successfully" in message.lower()
    
    
    async def test_unblock_user_success(self):
        """Test successful user unblocking"""
        from services.admin.user_admin_service import user_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        
        # Mock bot
        mock_bot = AsyncMock()
        
        # Test
        success, message = await user_admin_service.unblock_user(
            mock_db,
            123456,
            mock_bot,
            send_notification=False
        )
        
        # Verify
        assert success is True
        assert "unblocked successfully" in message.lower()
    
    
    async def test_update_user_balance_add(self):
        """Test adding to user balance"""
        from services.admin.user_admin_service import user_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        mock_db.users.find_one = AsyncMock(return_value={"balance": 150.0})
        
        # Test
        success, new_balance, error = await user_admin_service.update_user_balance(
            mock_db,
            123456,
            50.0,
            "add"
        )
        
        # Verify
        assert success is True
        assert new_balance == 150.0
        assert error is None
    
    
    async def test_update_user_discount(self):
        """Test updating user discount"""
        from services.admin.user_admin_service import user_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.users.update_one = AsyncMock(return_value=mock_result)
        
        # Test valid discount
        success, message = await user_admin_service.update_user_discount(
            mock_db,
            123456,
            15.0
        )
        
        # Verify
        assert success is True
        
        # Test invalid discount
        success, message = await user_admin_service.update_user_discount(
            mock_db,
            123456,
            150.0
        )
        
        # Verify
        assert success is False
        assert "between 0 and 100" in message


@pytest.mark.asyncio
class TestStatsAdminService:
    """Test Stats Admin Service"""
    
    async def test_get_dashboard_stats(self):
        """Test getting dashboard statistics"""
        from services.admin.stats_admin_service import stats_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_db.users.count_documents = AsyncMock(side_effect=[100, 5, 50, 10])  # total, blocked, with_balance, new_24h
        mock_db.orders.count_documents = AsyncMock(side_effect=[200, 180, 20, 15])  # total, paid, pending, new_24h
        
        # Mock revenue aggregation
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"total": 5000.0}])
        mock_db.orders.aggregate = MagicMock(return_value=mock_cursor)
        
        # Test
        stats = await stats_admin_service.get_dashboard_stats(mock_db)
        
        # Verify
        assert stats["users"]["total"] == 100
        assert stats["orders"]["total"] == 200
        assert stats["revenue"]["total"] == 5000.0
    
    
    async def test_get_expense_stats(self):
        """Test getting expense statistics"""
        from services.admin.stats_admin_service import stats_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[
            {"amount": 10.0, "carrier": "USPS"},
            {"amount": 15.0, "carrier": "USPS"},
            {"amount": 20.0, "carrier": "UPS"}
        ])
        mock_db.orders.find = MagicMock(return_value=mock_cursor)
        
        # Test
        stats = await stats_admin_service.get_expense_stats(mock_db, days=7)
        
        # Verify
        assert stats["total_expenses"] == 45.0
        assert stats["total_orders"] == 3
        assert "USPS" in stats["by_carrier"]
        assert "UPS" in stats["by_carrier"]
    
    
    async def test_get_performance_stats(self):
        """Test getting performance statistics"""
        from services.admin.stats_admin_service import stats_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_db.user_sessions.count_documents = AsyncMock(return_value=15)
        mock_db.pending_orders.count_documents = AsyncMock(return_value=5)
        mock_db.payments.count_documents = AsyncMock(side_effect=[100, 95])  # total, successful
        
        # Test
        stats = await stats_admin_service.get_performance_stats(mock_db)
        
        # Verify
        assert stats["active_sessions"] == 15
        assert stats["pending_orders"] == 5
        assert stats["payment_stats_24h"]["success_rate"] == 95.0


@pytest.mark.asyncio
class TestSystemAdminService:
    """Test System Admin Service"""
    
    async def test_enable_maintenance(self):
        """Test enabling maintenance mode"""
        from services.admin.system_admin_service import system_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_db.config.update_one = AsyncMock()
        
        # Test
        success, message = await system_admin_service.enable_maintenance(
            mock_db,
            "Test message"
        )
        
        # Verify
        assert success is True
        assert "enabled" in message.lower()
    
    
    async def test_disable_maintenance(self):
        """Test disabling maintenance mode"""
        from services.admin.system_admin_service import system_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_db.config.update_one = AsyncMock()
        
        # Test
        success, message = await system_admin_service.disable_maintenance(mock_db)
        
        # Verify
        assert success is True
        assert "disabled" in message.lower()
    
    
    async def test_clear_all_sessions(self):
        """Test clearing all sessions"""
        from services.admin.system_admin_service import system_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.deleted_count = 25
        mock_db.user_sessions.delete_many = AsyncMock(return_value=mock_result)
        
        # Test
        success, count, message = await system_admin_service.clear_all_sessions(
            mock_db,
            None
        )
        
        # Verify
        assert success is True
        assert count == 25
        assert "25" in message
    
    
    async def test_set_api_mode(self):
        """Test setting API-only mode"""
        from services.admin.system_admin_service import system_admin_service
        
        # Mock database
        mock_db = MagicMock()
        mock_db.config.update_one = AsyncMock()
        
        # Test enable
        success, message = await system_admin_service.set_api_mode(mock_db, True)
        assert success is True
        assert "enabled" in message.lower()
        
        # Test disable
        success, message = await system_admin_service.set_api_mode(mock_db, False)
        assert success is True
        assert "disabled" in message.lower()


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
