"""
End-to-End Order Flow Integration Tests
Tests the complete order creation flow through ConversationHandler
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from telegram.ext import ConversationHandler


@pytest.mark.asyncio
class TestOrderFlowE2E:
    """Test complete order creation flow"""
    
    async def test_new_order_flow_basic(
        self,
        mock_update_callback,
        mock_context,
        test_db
    ):
        """
        Test basic order flow: new_order -> addresses -> parcel -> rates
        """
        from handlers.order_flow.entry_points import new_order_start
        from handlers.order_flow.from_address import order_from_name
        from server import FROM_NAME, FROM_ADDRESS
        
        # Setup: User starts new order
        mock_update_callback.callback_query.data = "new_order"
        
        # Mock database operations
        with patch('server.find_user_by_telegram_id') as mock_find_user, \
             patch('server.count_user_templates', return_value=0), \
             patch('server.check_maintenance_mode', return_value=False), \
             patch('server.check_user_blocked', return_value=False), \
             patch('server.session_manager') as mock_session:
            
            mock_find_user.return_value = {
                "id": "user123",
                "telegram_id": 123456789,
                "balance": 100.0
            }
            
            mock_session.get_or_create_session = AsyncMock(return_value={
                "user_id": 123456789,
                "current_step": "START",
                "temp_data": {}
            })
            
            # Step 1: Start new order
            result = await new_order_start(mock_update_callback, mock_context)
            
            # Verify: Should transition to FROM_NAME state
            assert result == FROM_NAME
            assert mock_update_callback.callback_query.answer.called
            
        # Step 2: Enter from_name
        mock_update_message = MagicMock()
        mock_update_message.message = MagicMock()
        mock_update_message.message.text = "John Doe"
        mock_reply_msg = MagicMock()
        mock_reply_msg.message_id = 456
        mock_update_message.message.reply_text = AsyncMock(return_value=mock_reply_msg)
        mock_update_message.effective_user = mock_update_callback.effective_user
        
        with patch('server.safe_telegram_call') as mock_safe_call, \
             patch('server.session_manager') as mock_session:
            
            mock_safe_call.side_effect = lambda x: x
            mock_session.update_session_atomic = AsyncMock()
            
            result = await order_from_name(mock_update_message, mock_context)
            
            # Verify: Should save name and ask for address
            assert result == FROM_ADDRESS
            assert "from_name" in mock_context.user_data
            assert mock_context.user_data["from_name"] == "John Doe"
    
    
    async def test_template_order_flow(
        self,
        mock_update_callback,
        mock_context,
        sample_order_data
    ):
        """
        Test order creation from template
        """
        from handlers.order_flow.entry_points import start_order_with_template
        from server import PARCEL_WEIGHT
        
        # Setup: Load template data into context
        mock_context.user_data.update(sample_order_data)
        mock_context.user_data['template_name'] = "Test Template"
        
        with patch('server.safe_telegram_call') as mock_safe_call:
            mock_reply_msg = MagicMock()
            mock_reply_msg.message_id = 789
            mock_safe_call.return_value = mock_reply_msg
            
            # Start order with template
            result = await start_order_with_template(mock_update_callback, mock_context)
            
            # Verify: Should skip to PARCEL_WEIGHT (addresses pre-filled)
            assert result == PARCEL_WEIGHT
            assert mock_update_callback.callback_query.answer.called
    
    
    async def test_cancel_order_flow(
        self,
        mock_update_callback,
        mock_context,
        test_db
    ):
        """
        Test order cancellation
        """
        from handlers.order_flow.cancellation import cancel_order, confirm_cancel_order
        from server import SELECT_CARRIER, STATE_NAMES
        
        # Setup: Create user and session in DB
        await test_db.users.insert_one({
            "id": "user123",
            "telegram_id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "balance": 50.0,
            "created_at": "2024-01-01T00:00:00Z"
        })
        
        from repositories.session_repository import SessionRepository
        session_repo = SessionRepository(test_db)
        await session_repo.get_or_create_session(
            user_id=123456789,
            session_type="conversation"
        )
        
        # Setup: User is on rates selection screen
        mock_context.user_data['last_state'] = STATE_NAMES[SELECT_CARRIER]
        
        with patch('server.safe_telegram_call') as mock_safe_call:
            mock_reply_msg = MagicMock()
            mock_reply_msg.message_id = 999
            mock_safe_call.return_value = mock_reply_msg
            
            # Step 1: User clicks cancel
            result = await cancel_order(mock_update_callback, mock_context)
            
            # Verify: Should show confirmation with "Check Data" button
            assert result == STATE_NAMES[SELECT_CARRIER]
            assert mock_update_callback.callback_query.answer.called
        
        # Step 2: User confirms cancellation
        with patch('server.safe_telegram_call') as mock_safe_call:
            mock_safe_call.side_effect = lambda x: x
            
            result = await confirm_cancel_order(mock_update_callback, mock_context)
            
            # Verify: Should end conversation and clear data
            assert result == ConversationHandler.END
    
    
    async def test_data_confirmation_flow(
        self,
        mock_update_callback,
        mock_context,
        sample_order_data,
        test_db
    ):
        """
        Test data confirmation screen
        """
        from handlers.order_flow.confirmation import show_data_confirmation
        from server import CONFIRM_DATA
        
        # Setup: Create user and session in DB
        await test_db.users.insert_one({
            "id": "user123",
            "telegram_id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "balance": 50.0,
            "created_at": "2024-01-01T00:00:00Z"
        })
        
        from repositories.session_repository import SessionRepository
        session_repo = SessionRepository(test_db)
        await session_repo.get_or_create_session(
            user_id=123456789,
            session_type="conversation"
        )
        
        # Setup: User has entered all data
        mock_context.user_data.update(sample_order_data)
        
        # Add update.message mock
        mock_update_callback.message = MagicMock()
        mock_reply_msg = MagicMock()
        mock_reply_msg.message_id = 111
        mock_update_callback.message.reply_text = AsyncMock(return_value=mock_reply_msg)
        
        with patch('server.safe_telegram_call') as mock_safe_call:
            mock_safe_call.return_value = mock_reply_msg
            
            result = await show_data_confirmation(mock_update_callback, mock_context)
            
            # Verify: Should display confirmation screen
            assert result == CONFIRM_DATA
    
    
    async def test_payment_flow_sufficient_balance(
        self,
        mock_update_callback,
        mock_context,
        sample_shipping_rate,
        test_db
    ):
        """
        Test payment flow when user has sufficient balance
        """
        from handlers.order_flow.payment import show_payment_methods
        from server import PAYMENT_METHOD
        
        # Setup: Create user in DB with sufficient balance
        await test_db.users.insert_one({
            "id": "user123",
            "telegram_id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "balance": 100.0,  # Sufficient balance
            "created_at": "2024-01-01T00:00:00Z"
        })
        
        # Setup: Create session for user using SessionRepository
        from repositories.session_repository import SessionRepository
        session_repo = SessionRepository(test_db)
        await session_repo.get_or_create_session(
            user_id=123456789,
            session_type="conversation"
        )
        
        # Setup: User selected a rate
        mock_context.user_data['selected_rate'] = sample_shipping_rate
        mock_context.user_data['final_amount'] = 15.50
        
        with patch('server.safe_telegram_call') as mock_safe_call:
            mock_reply_msg = MagicMock()
            mock_reply_msg.message_id = 222
            mock_safe_call.return_value = mock_reply_msg
            
            result = await show_payment_methods(mock_update_callback, mock_context)
            
            # Verify: Should show balance payment option
            assert result == PAYMENT_METHOD


@pytest.mark.asyncio  
class TestOrderFlowEdgeCases:
    """Test edge cases and error handling in order flow"""
    
    async def test_missing_user_in_database(
        self,
        mock_update_callback,
        mock_context
    ):
        """Test handling when user not found in database"""
        from handlers.order_flow.entry_points import new_order_start
        
        with patch('server.find_user_by_telegram_id', return_value=None), \
             patch('server.count_user_templates', return_value=0), \
             patch('server.check_maintenance_mode', return_value=False), \
             patch('server.check_user_blocked', return_value=False), \
             patch('server.session_manager') as mock_session:
            
            mock_session.get_or_create_session = AsyncMock(return_value={
                "user_id": 123456789,
                "current_step": "START",
                "temp_data": {}
            })
            
            # Should handle gracefully
            result = await new_order_start(mock_update_callback, mock_context)
            
            # Verify: Should still proceed (user might be created on first message)
            assert result is not None
    
    
    async def test_maintenance_mode_active(
        self,
        mock_update_callback,
        mock_context
    ):
        """Test order flow when maintenance mode is active"""
        from handlers.order_flow.entry_points import new_order_start
        
        with patch('server.check_maintenance_mode', return_value=True), \
             patch('server.safe_telegram_call') as mock_safe_call, \
             patch('server.session_manager') as mock_session:
            
            mock_safe_call.side_effect = lambda x: x
            mock_session.get_or_create_session = AsyncMock(return_value={})
            
            result = await new_order_start(mock_update_callback, mock_context)
            
            # Verify: Should end conversation
            assert result == ConversationHandler.END
    
    
    async def test_blocked_user_attempt(
        self,
        mock_update_callback,
        mock_context
    ):
        """Test when blocked user tries to create order"""
        from handlers.order_flow.entry_points import new_order_start
        
        # Mock user repository to return blocked user
        with patch('repositories.get_user_repo') as mock_user_repo_factory:
            mock_user_repo = AsyncMock()
            mock_user_repo.get_or_create_user = AsyncMock(return_value={
                "id": "user123",
                "telegram_id": 123456789,
                "blocked": True  # User is blocked
            })
            mock_user_repo_factory.return_value = mock_user_repo
            
            result = await new_order_start(mock_update_callback, mock_context)
            
            # Verify: Should end conversation due to blocked user
            assert result == ConversationHandler.END
