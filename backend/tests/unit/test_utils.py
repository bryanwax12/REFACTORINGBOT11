"""
Unit tests for utility functions
"""
import pytest
from utils.db_operations import (
    find_user_by_telegram_id,
    count_user_templates
)


class TestDBOperations:
    """Test suite for database operations utilities"""
    
    @pytest.mark.asyncio
    async def test_find_user_by_telegram_id_exists(self, test_db):
        """Test finding existing user"""
        # Setup: Create test user
        telegram_id = 123456789
        await test_db.users.insert_one({
            "telegram_id": telegram_id,
            "username": "testuser",
            "balance": 100.0
        })
        
        # Execute
        user = await find_user_by_telegram_id(telegram_id)
        
        # Assert
        assert user is not None
        assert user["telegram_id"] == telegram_id
        assert user["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_find_user_by_telegram_id_not_exists(self, test_db):
        """Test finding non-existent user"""
        # Execute
        user = await find_user_by_telegram_id(999999999)
        
        # Assert
        assert user is None
    
    @pytest.mark.asyncio
    async def test_count_user_templates_zero(self, test_db):
        """Test counting templates when user has none"""
        # Execute
        count = await count_user_templates(123456789)
        
        # Assert
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_count_user_templates_multiple(self, test_db):
        """Test counting templates when user has multiple"""
        # Setup: Create test templates
        from uuid import uuid4
        telegram_id = 123456789
        for i in range(3):
            await test_db.templates.insert_one({
                "id": str(uuid4()),
                "telegram_id": telegram_id,
                "name": f"Template {i}",
                "data": {}
            })
        
        # Execute
        count = await count_user_templates(telegram_id)
        
        # Assert
        assert count == 3


class TestErrorHandling:
    """Test suite for error handling utilities"""
    
    def test_error_response_format(self):
        """Test ErrorResponse formatting"""
        from middleware.error_handler_middleware import ErrorResponse
        
        # Execute
        error = ErrorResponse.format_error(
            status_code=400,
            error_type="ValidationError",
            message="Test error",
            details={"field": "test"},
            request_id="123"
        )
        
        # Assert
        assert error["error"]["status_code"] == 400
        assert error["error"]["type"] == "ValidationError"
        assert error["error"]["message"] == "Test error"
        assert error["error"]["details"]["field"] == "test"
        assert error["error"]["request_id"] == "123"
    
    def test_error_response_minimal(self):
        """Test ErrorResponse with minimal fields"""
        from middleware.error_handler_middleware import ErrorResponse
        
        # Execute
        error = ErrorResponse.format_error(
            status_code=500,
            error_type="InternalError",
            message="Internal error"
        )
        
        # Assert
        assert "details" not in error["error"]
        assert "request_id" not in error["error"]


class TestHelperFunctions:
    """Test suite for helper functions"""
    
    def test_is_rate_limit_error(self):
        """Test rate limit error detection"""
        from middleware.error_handler_middleware import is_rate_limit_error
        
        # Test positive cases
        assert is_rate_limit_error(Exception("Rate limit exceeded"))
        assert is_rate_limit_error(Exception("Too many requests"))
        
        # Test negative cases
        assert not is_rate_limit_error(Exception("Connection error"))
    
    def test_is_timeout_error(self):
        """Test timeout error detection"""
        from middleware.error_handler_middleware import is_timeout_error
        
        # Test positive cases
        assert is_timeout_error(Exception("Request timeout"))
        assert is_timeout_error(Exception("Operation timed out"))
        
        # Test negative cases
        assert not is_timeout_error(Exception("Connection error"))
    
    def test_get_user_friendly_message(self):
        """Test user-friendly message generation"""
        from middleware.error_handler_middleware import get_user_friendly_message
        
        # Test rate limit
        msg = get_user_friendly_message(Exception("Rate limit exceeded"))
        assert "много запросов" in msg.lower()
        
        # Test timeout
        msg = get_user_friendly_message(Exception("Request timeout"))
        assert "слишком много времени" in msg.lower()
        
        # Test ValueError
        msg = get_user_friendly_message(ValueError("Invalid input"))
        assert msg == "Invalid input"
        
        # Test generic error
        msg = get_user_friendly_message(Exception("Unknown error"))
        assert "Произошла ошибка" in msg
