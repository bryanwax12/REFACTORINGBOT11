"""
Unit Tests for Order Utilities
Tests order ID generation and validation
"""
import pytest
from utils.order_utils import (
    generate_order_id,
    generate_pure_uuid_order_id,
    format_order_id_for_display,
    validate_order_id
)


class TestOrderIDGeneration:
    """Test order ID generation functions"""
    
    def test_generate_order_id_format(self):
        """Test order ID format"""
        order_id = generate_order_id()
        
        # Should be in format: ORD-{timestamp}-{uuid_short}
        parts = order_id.split('-')
        assert len(parts) >= 3
        assert parts[0] == "ORD"
        assert len(parts[1]) == 14  # YYYYMMDDHHMMSS
        assert len(parts[2]) == 8   # First 8 chars of UUID
    
    def test_generate_order_id_with_telegram_id(self):
        """Test order ID generation with telegram_id"""
        telegram_id = 123456789
        order_id = generate_order_id(telegram_id=telegram_id)
        
        assert order_id.startswith("ORD-")
        assert len(order_id) > 15
    
    def test_generate_order_id_uniqueness(self):
        """Test that generated order IDs are unique"""
        ids = set()
        for _ in range(100):
            order_id = generate_order_id()
            ids.add(order_id)
        
        # All 100 IDs should be unique
        assert len(ids) == 100
    
    def test_generate_order_id_custom_prefix(self):
        """Test order ID with custom prefix"""
        order_id = generate_order_id(prefix="TEST")
        assert order_id.startswith("TEST-")
    
    def test_generate_pure_uuid_order_id(self):
        """Test pure UUID generation"""
        order_id = generate_pure_uuid_order_id()
        
        # Should be UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert len(order_id) == 36
        assert order_id.count('-') == 4
    
    def test_pure_uuid_uniqueness(self):
        """Test UUID uniqueness"""
        ids = set()
        for _ in range(100):
            order_id = generate_pure_uuid_order_id()
            ids.add(order_id)
        
        assert len(ids) == 100


class TestOrderIDValidation:
    """Test order ID validation"""
    
    def test_validate_order_id_with_prefix(self):
        """Test validation of ORD-formatted ID"""
        order_id = generate_order_id()
        assert validate_order_id(order_id) is True
    
    def test_validate_pure_uuid(self):
        """Test validation of pure UUID"""
        order_id = generate_pure_uuid_order_id()
        assert validate_order_id(order_id) is True
    
    def test_validate_invalid_order_id(self):
        """Test validation of invalid IDs"""
        assert validate_order_id("") is False
        assert validate_order_id(None) is False
        assert validate_order_id("invalid") is False
        assert validate_order_id(123) is False
    
    def test_validate_malformed_order_id(self):
        """Test validation of malformed IDs"""
        assert validate_order_id("ORD") is False
        assert validate_order_id("ORD-123") is False


class TestOrderIDDisplay:
    """Test order ID display formatting"""
    
    def test_format_order_id_with_prefix(self):
        """Test formatting ORD-formatted ID for display"""
        order_id = "ORD-20251114123456-a3f8d2b4"
        display = format_order_id_for_display(order_id)
        
        # Should show ORD-{first 6 of uuid}
        assert "ORD-" in display
        assert len(display) <= 12
    
    def test_format_pure_uuid_for_display(self):
        """Test formatting UUID for display"""
        order_id = "123e4567-e89b-12d3-a456-426614174000"
        display = format_order_id_for_display(order_id)
        
        # Should show first 8 chars
        assert display == "123E4567"
    
    def test_format_empty_order_id(self):
        """Test formatting empty/None ID"""
        assert format_order_id_for_display("") == "N/A"
        assert format_order_id_for_display(None) == "N/A"
    
    def test_format_short_order_id(self):
        """Test formatting short ID"""
        order_id = "SHORT123"
        display = format_order_id_for_display(order_id)
        
        # Should return uppercase version, max 12 chars
        assert len(display) <= 12
        assert display == "SHORT123"


class TestOrderIDIntegration:
    """Integration tests for order ID usage"""
    
    def test_order_id_can_be_stored_in_dict(self):
        """Test that order ID can be stored in dictionary"""
        order_id = generate_order_id()
        order_data = {
            "order_id": order_id,
            "amount": 25.50
        }
        
        assert order_data["order_id"] == order_id
        assert validate_order_id(order_data["order_id"])
    
    def test_order_id_round_trip(self):
        """Test generate -> validate -> format cycle"""
        # Generate
        order_id = generate_order_id(telegram_id=123456789)
        
        # Validate
        assert validate_order_id(order_id)
        
        # Format for display
        display = format_order_id_for_display(order_id)
        assert display is not None
        assert len(display) > 0
