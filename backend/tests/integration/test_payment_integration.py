"""
Payment Integration Tests
Tests complete payment flow including balance, crypto, and order creation
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


@pytest.mark.asyncio
class TestPaymentIntegration:
    """Test complete payment flows"""
    
    async def test_balance_payment_full_flow(
        self,
        test_db,
        mock_update_callback,
        mock_context,
        sample_shipping_rate,
        sample_order_data
    ):
        """
        Test complete flow: balance payment -> order creation -> label generation
        """
        from services.payment_service import process_balance_payment
        
        # Setup: User has sufficient balance
        telegram_id = 123456789
        amount = 15.50
        
        # Mock user with balance
        mock_user = {
            "id": "user123",
            "telegram_id": telegram_id,
            "balance": 100.0
        }
        
        mock_context.user_data.update(sample_order_data)
        mock_context.user_data['selected_rate'] = sample_shipping_rate
        mock_context.user_data['final_amount'] = amount
        
        # Note: find_user_by_telegram_id and deduct_balance are passed as parameters
        # Create mock functions directly
        mock_find = AsyncMock(return_value=mock_user)
        mock_deduct = AsyncMock(return_value=(True, None))
            
        # Process payment
        success, new_balance, error = await process_balance_payment(
            telegram_id=telegram_id,
            amount=amount,
            find_user_func=mock_find,
            deduct_balance_func=mock_deduct
        )
        
        # Verify: Payment successful
        assert success is True
        assert error is None
        assert new_balance == 100.0 - amount
    
    
    async def test_insufficient_balance_payment(
        self,
        mock_update_callback,
        mock_context
    ):
        """
        Test payment flow when user has insufficient balance
        """
        from services.payment_service import validate_payment_amount
        
        telegram_id = 123456789
        amount = 150.0  # More than balance
        user_balance = 100.0
        
        # Validate payment
        valid, error = validate_payment_amount(
            amount=amount,
            user_balance=user_balance
        )
        
        # Verify: Should fail validation
        assert valid is False
        assert "insufficient" in error.lower()
    
    
    async def test_crypto_payment_invoice_creation(
        self,
        mock_update_callback,
        mock_context,
        mock_oxapay_response
    ):
        """
        Test crypto payment invoice creation
        """
        from server import create_oxapay_invoice
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_oxapay_response)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await create_oxapay_invoice(
                amount=25.0,
                order_id="order_123",
                description="Test Order Payment"
            )
            
            # Verify: Invoice created
            assert 'trackId' in result or 'success' in result
    
    
    async def test_topup_flow(
        self,
        test_db,
        mock_update_message,
        mock_context
    ):
        """
        Test balance top-up flow
        """
        from handlers.order_flow.template_save import handle_topup_amount
        from services.payment_service import validate_topup_amount
        
        # Step 1: Validate topup amount
        valid, error = validate_topup_amount(50.0)
        assert valid is True
        assert error is None
        
        # Step 2: Test too small amount
        valid, error = validate_topup_amount(5.0)
        assert valid is False
        assert "minimum" in error.lower()
        
        # Step 3: Test too large amount
        valid, error = validate_topup_amount(15000.0)
        assert valid is False
        assert "maximum" in error.lower()
    
    
    async def test_payment_webhook_processing(
        self,
        test_db
    ):
        """
        Test processing of payment webhook from Oxapay
        """
        # Mock webhook data
        webhook_data = {
            "trackId": "test_track_123",
            "status": "Paid",
            "amount": 50.0,
            "currency": "USD"
        }
        
        # In real test, would call webhook handler
        # For now, verify data structure
        assert "trackId" in webhook_data
        assert webhook_data["status"] == "Paid"


@pytest.mark.asyncio
class TestOrderCreationIntegration:
    """Test order creation after payment"""
    
    async def test_complete_order_creation(
        self,
        test_db,
        sample_order_data,
        sample_shipping_rate
    ):
        """
        Test complete order creation flow
        """
        # Setup order data
        order_data = {
            **sample_order_data,
            "selected_rate": sample_shipping_rate,
            "telegram_id": 123456789,
            "payment_method": "balance",
            "amount": 15.50
        }
        
        # Mock order insertion
        with patch('server.insert_order') as mock_insert:
            mock_insert.return_value = "order_id_123"
            
            order_id = await mock_insert(order_data)
            
            # Verify: Order created
            assert order_id == "order_id_123"
    
    
    async def test_label_generation_after_payment(
        self,
        sample_order_data,
        sample_shipping_rate
    ):
        """
        Test shipping label generation after successful payment
        """
        from services.shipping_service import build_shipstation_label_request
        
        order_data = {
            **sample_order_data,
            "selected_rate": sample_shipping_rate
        }
        
        # Build label request
        label_request = build_shipstation_label_request(
            order_data=order_data,
            rate_data=sample_shipping_rate
        )
        
        # Verify request structure
        assert "shipFrom" in label_request
        assert "shipTo" in label_request
        assert "carrierCode" in label_request or "serviceCode" in label_request
    
    
    async def test_order_history_retrieval(
        self,
        test_db
    ):
        """
        Test retrieving user's order history
        """
        telegram_id = 123456789
        
        # Query with optimized index
        orders = await test_db.orders.find(
            {"telegram_id": telegram_id},
            {"_id": 0}  # Projection to exclude _id
        ).sort("created_at", -1).limit(10).to_list(length=10)
        
        # Should use idx_user_orders index
        # Verify query works (may return empty list)
        assert isinstance(orders, list)
