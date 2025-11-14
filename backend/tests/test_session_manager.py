"""
Tests for SessionManager (MongoDB session management)
"""
import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import module to test
import sys
sys.path.insert(0, '/app/backend')
from session_manager import SessionManager


@pytest_asyncio.fixture
async def session_manager():
    """Fixture: Create SessionManager instance"""
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client['test_telegram_bot']  # Use test database
    
    sm = SessionManager(db)
    
    # Wait for indexes to be created
    await asyncio.sleep(0.5)
    
    yield sm
    
    # Cleanup: drop test database
    await client.drop_database('test_telegram_bot')
    client.close()


@pytest.mark.asyncio
async def test_get_or_create_session_new(session_manager):
    """Test creating a new session"""
    user_id = 12345
    
    # Create new session
    session = await session_manager.get_or_create_session(user_id, initial_data={'test': 'data'})
    
    assert session is not None
    assert session['user_id'] == user_id
    assert session['current_step'] == 'START'
    assert session['temp_data']['test'] == 'data'
    assert 'timestamp' in session


@pytest.mark.asyncio
async def test_get_or_create_session_existing(session_manager):
    """Test getting existing session"""
    user_id = 12345
    
    # Create session
    await session_manager.get_or_create_session(user_id, initial_data={'first': 'call'})
    
    # Get existing (should not reset data)
    session = await session_manager.get_or_create_session(user_id, initial_data={'second': 'call'})
    
    assert session['temp_data'].get('first') == 'call'
    # Initial data should NOT override on existing session
    assert session['temp_data'].get('second') is None


@pytest.mark.asyncio
async def test_update_session_atomic(session_manager):
    """Test atomic session update"""
    user_id = 12345
    
    # Create session
    await session_manager.get_or_create_session(user_id)
    
    # Update step and data
    session = await session_manager.update_session_atomic(
        user_id,
        step='FROM_NAME',
        data={'from_name': 'John Doe'}
    )
    
    assert session is not None
    assert session['current_step'] == 'FROM_NAME'
    assert session['temp_data']['from_name'] == 'John Doe'


@pytest.mark.asyncio
async def test_update_session_atomic_multiple_fields(session_manager):
    """Test updating multiple fields atomically"""
    user_id = 12345
    
    await session_manager.get_or_create_session(user_id)
    
    # First update
    await session_manager.update_session_atomic(user_id, data={'field1': 'value1'})
    
    # Second update (should preserve field1)
    session = await session_manager.update_session_atomic(user_id, data={'field2': 'value2'})
    
    assert session['temp_data']['field1'] == 'value1'
    assert session['temp_data']['field2'] == 'value2'


@pytest.mark.asyncio
async def test_clear_session(session_manager):
    """Test session deletion"""
    user_id = 12345
    
    # Create session
    await session_manager.get_or_create_session(user_id)
    
    # Clear session
    result = await session_manager.clear_session(user_id)
    assert result is True
    
    # Verify deleted
    session = await session_manager.get_session(user_id)
    assert session is None


@pytest.mark.asyncio
async def test_save_completed_label_fallback(session_manager):
    """Test save_completed_label with fallback (no replica set)"""
    user_id = 12345
    
    # Create session
    await session_manager.get_or_create_session(user_id, initial_data={'order_id': 'test123'})
    
    # Save label (should use fallback in standalone mode)
    label_data = {
        'order_id': 'test123',
        'tracking': 'TRACK123',
        'amount': 5.99
    }
    
    result = await session_manager.save_completed_label(user_id, label_data)
    assert result is True
    
    # Verify session deleted
    session = await session_manager.get_session(user_id)
    assert session is None
    
    # Verify label saved
    labels = await session_manager.get_user_labels(user_id, limit=1)
    assert len(labels) == 1
    assert labels[0]['label_data']['order_id'] == 'test123'


@pytest.mark.asyncio
async def test_revert_to_previous_step(session_manager):
    """Test reverting to previous step"""
    user_id = 12345
    
    # Create session at FROM_ZIP step
    await session_manager.get_or_create_session(user_id)
    await session_manager.update_session_atomic(user_id, step='FROM_ZIP', data={'from_zip': '12345'})
    
    # Revert to previous step
    previous_step = await session_manager.revert_to_previous_step(
        user_id,
        current_step='FROM_ZIP',
        error_message='Test error'
    )
    
    assert previous_step == 'FROM_STATE'
    
    # Verify session updated
    session = await session_manager.get_session(user_id)
    assert session['current_step'] == 'FROM_STATE'
    assert 'last_error' in session['temp_data']


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
