"""
Simplified Integration Tests
Tests that verify integration between components without complex mocking
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
class TestDatabaseIntegration:
    """Test database operations with real DB"""
    
    async def test_user_lookup_with_index(self, test_db):
        """Test user lookup uses telegram_id index"""
        telegram_id = 999999999
        
        # Insert test user
        test_user = {
            "id": "test_user_123",
            "telegram_id": telegram_id,
            "balance": 50.0,
            "created_at": "2025-01-01T00:00:00Z"
        }
        await test_db.users.insert_one(test_user)
        
        # Query using index
        user = await test_db.users.find_one(
            {"telegram_id": telegram_id},
            {"_id": 0}
        )
        
        # Verify
        assert user is not None
        assert user["telegram_id"] == telegram_id
        assert user["balance"] == 50.0
        
        # Cleanup
        await test_db.users.delete_one({"telegram_id": telegram_id})
    
    
    async def test_order_pagination(self, test_db):
        """Test order pagination with compound index"""
        from utils.optimized_queries import get_user_orders
        
        telegram_id = 888888888
        
        # Insert test orders
        import time
        unique_timestamp = int(time.time() * 1000)
        for i in range(5):
            await test_db.orders.insert_one({
                "id": f"order_{unique_timestamp}_{i}",
                "order_id": f"test_order_{unique_timestamp}_{i}",  # Add unique order_id
                "telegram_id": telegram_id,
                "order_number": f"ORD-{unique_timestamp}-{i}",
                "created_at": f"2025-01-0{i+1}T00:00:00Z",
                "payment_status": "paid",
                "amount": 10.0 + i
            })
        
        # Query with pagination
        orders = await get_user_orders(test_db, telegram_id, limit=3)
        
        # Verify
        assert len(orders) <= 3
        # Should be sorted by created_at DESC
        
        # Cleanup
        await test_db.orders.delete_many({"telegram_id": telegram_id})
    
    
    async def test_template_count_fast(self, test_db):
        """Test fast template counting"""
        from utils.optimized_queries import count_templates_fast
        
        telegram_id = 777777777
        
        # Insert test templates
        for i in range(3):
            await test_db.templates.insert_one({
                "id": f"template_{i}",
                "telegram_id": telegram_id,
                "name": f"Template {i}",
                "created_at": "2025-01-01T00:00:00Z"
            })
        
        # Count
        count = await count_templates_fast(test_db, telegram_id)
        
        # Verify
        assert count == 3
        
        # Cleanup
        await test_db.templates.delete_many({"telegram_id": telegram_id})
    
    
    async def test_payment_lookup_by_invoice(self, test_db):
        """Test payment lookup by invoice ID (uses index)"""
        from utils.optimized_queries import find_payment_by_invoice
        
        invoice_id = "test_invoice_123"
        
        # Insert test payment
        await test_db.payments.insert_one({
            "invoice_id": invoice_id,
            "telegram_id": 666666666,
            "amount": 25.0,
            "status": "pending",
            "created_at": "2025-01-01T00:00:00Z"
        })
        
        # Lookup by invoice
        payment = await find_payment_by_invoice(test_db, invoice_id)
        
        # Verify
        assert payment is not None
        assert payment["invoice_id"] == invoice_id
        assert payment["amount"] == 25.0
        
        # Cleanup
        await test_db.payments.delete_one({"invoice_id": invoice_id})


@pytest.mark.asyncio
class TestServiceIntegration:
    """Test service layer integration"""
    
    async def test_payment_service_validation(self):
        """Test payment amount validation"""
        from services.payment_service import validate_payment_amount, validate_topup_amount
        
        # Valid payment
        valid, error = validate_payment_amount(10.0, 100.0)
        assert valid is True
        assert error is None
        
        # Insufficient balance
        valid, error = validate_payment_amount(150.0, 100.0)
        assert valid is False
        assert error is not None
        
        # Valid topup
        valid, error = validate_topup_amount(50.0)
        assert valid is True
        
        # Topup too small
        valid, error = validate_topup_amount(5.0)
        assert valid is False
        
        # Topup too large
        valid, error = validate_topup_amount(15000.0)
        assert valid is False
    
    
    async def test_template_service_validation(self):
        """Test template data validation"""
        from services.template_service import validate_template_data
        
        # Valid template - needs all required fields (including weight)
        valid_data = {
            "from_name": "John",
            "from_street": "123 Main",
            "from_city": "NY",
            "from_state": "NY",
            "from_zip": "10001",
            "to_name": "Jane",
            "to_street": "456 Oak",
            "to_city": "LA",
            "to_state": "CA",
            "to_zip": "90001",
            "weight": 5.0
        }
        valid, error = validate_template_data(valid_data)
        assert valid is True
        
        # Missing fields
        invalid_data = {
            "from_name": "John"
        }
        valid, error = validate_template_data(invalid_data)
        assert valid is False
    
    
    async def test_shipping_service_validation(self):
        """Test shipping address and parcel validation"""
        from services.shipping_service import validate_parcel_data
        
        # Valid parcel
        valid_parcel = {
            "weight": 5.0  # Function expects 'weight' key
        }
        valid, error = validate_parcel_data(valid_parcel)
        assert valid is True
        assert error is None
        
        # Negative weight
        invalid_parcel = {
            "weight": -1.0
        }
        valid, error = validate_parcel_data(invalid_parcel)
        assert valid is False
        assert error is not None
        
        # Weight too high
        heavy_parcel = {
            "weight": 200.0
        }
        valid, error = validate_parcel_data(heavy_parcel)
        assert valid is False
        assert error is not None


@pytest.mark.asyncio
class TestAPIIntegration:
    """Test external API integration (with mocks)"""
    
    async def test_shipstation_request_building(self, sample_order_data):
        """Test ShipStation API request construction"""
        from services.shipping_service import build_shipstation_rates_request
        
        # Add required weight field
        sample_order_data['parcel_weight'] = 5.5
        
        # Mock carrier IDs
        carrier_ids = ["se-123456", "se-789012"]
        
        request = build_shipstation_rates_request(sample_order_data, carrier_ids)
        
        # Verify structure (ShipEngine V2 format)
        assert "shipment" in request
        assert "rate_options" in request
        assert "ship_from" in request["shipment"]
        assert "ship_to" in request["shipment"]
    
    
    async def test_shipstation_api_call_mocked(
        self,
        sample_order_data,
        mock_shipstation_response
    ):
        """Test ShipStation API call with mocked response"""
        from services.shipping_service import fetch_rates_from_shipstation, build_shipstation_rates_request
        
        # Add required fields
        sample_order_data['parcel_weight'] = 5.5
        carrier_ids = ["se-123456"]
        
        request = build_shipstation_rates_request(sample_order_data, carrier_ids)
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_shipstation_response)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            success, rates, error = await fetch_rates_from_shipstation(
                request,
                "test_key",
                "test_secret"
            )
            
            assert success is True
            assert len(rates) > 0
            assert error is None


@pytest.mark.asyncio
class TestConversationFlow:
    """Test conversation handler state transitions"""
    
    async def test_state_constants_defined(self):
        """Verify all conversation states are defined"""
        from server import (
            FROM_NAME, FROM_ADDRESS, TO_NAME, TO_ADDRESS,
            PARCEL_WEIGHT, SELECT_CARRIER, PAYMENT_METHOD,
            CONFIRM_DATA, TEMPLATE_NAME
        )
        
        # All states should be unique integers
        states = [
            FROM_NAME, FROM_ADDRESS, TO_NAME, TO_ADDRESS,
            PARCEL_WEIGHT, SELECT_CARRIER, PAYMENT_METHOD,
            CONFIRM_DATA, TEMPLATE_NAME
        ]
        
        assert len(states) == len(set(states))  # All unique
        assert all(isinstance(s, int) for s in states)  # All integers
    
    
    async def test_state_names_mapping(self):
        """Verify STATE_NAMES mapping exists"""
        from server import STATE_NAMES, FROM_NAME, TO_NAME
        
        assert isinstance(STATE_NAMES, dict)
        assert FROM_NAME in STATE_NAMES
        assert TO_NAME in STATE_NAMES
        assert isinstance(STATE_NAMES[FROM_NAME], str)


@pytest.mark.asyncio
class TestSessionManager:
    """Test session management integration"""
    
    async def test_session_creation_and_retrieval(self, test_db):
        """Test session CRUD operations"""
        from session_manager import SessionManager
        
        sm = SessionManager(test_db)
        user_id = 555555555
        
        # Create session
        session = await sm.get_or_create_session(user_id, {"test": "data"})
        assert session is not None
        assert session["user_id"] == user_id
        
        # Retrieve existing session
        existing = await sm.get_or_create_session(user_id)
        assert existing["user_id"] == user_id
        
        # Clear session
        await sm.clear_session(user_id)
        
        # Verify cleared
        cleared = await sm.get_session(user_id)
        assert cleared is None
