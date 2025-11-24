"""
Unit test for ConversationHandler fix
Tests that /start command properly clears conversation state
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes, ConversationHandler


@pytest.mark.asyncio
async def test_start_command_clears_state_and_returns_end():
    """
    Test that start_command:
    1. Clears context.user_data
    2. Returns ConversationHandler.END to exit active conversations
    """
    from handlers.common_handlers import start_command
    
    # Mock Update object
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.first_name = "TestUser"
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 12345
    
    # Mock message
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock(return_value=MagicMock(message_id=999))
    update.callback_query = None
    
    # Mock Context with user_data that has old conversation state
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {
        'from_name': 'Old Name',
        'to_name': 'Old To Name',
        'last_state': 5,
        'order_data': {'some': 'old_data'}
    }
    
    # Mock db_user for decorator
    context.user_data['db_user'] = {
        'telegram_id': 12345,
        'first_name': 'TestUser',
        'balance': 10.0,
        'blocked': False
    }
    
    print("🧪 Testing start_command...")
    print(f"   Before: context.user_data has {len(context.user_data)} keys")
    
    # Mock maintenance check
    with patch('handlers.common_handlers.check_maintenance_mode', return_value=False):
        # Call start_command
        result = await start_command(update, context)
    
    print(f"   After: context.user_data has {len(context.user_data)} keys")
    print(f"   Return value: {result}")
    
    # Assertions
    assert result == ConversationHandler.END, "start_command должна возвращать ConversationHandler.END"
    
    # Check that old conversation data was cleared
    assert 'from_name' not in context.user_data, "Старые данные диалога должны быть очищены"
    assert 'to_name' not in context.user_data, "Старые данные диалога должны быть очищены"
    assert 'last_state' not in context.user_data, "Старые данные диалога должны быть очищены"
    
    print("✅ Тест пройден: start_command правильно очищает состояние и возвращает END")


@pytest.mark.asyncio
async def test_start_command_with_maintenance_mode():
    """
    Test that start_command returns END when in maintenance mode
    """
    from handlers.common_handlers import start_command
    
    # Mock Update
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 12345
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.id = 12345
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock(return_value=MagicMock(message_id=999))
    update.callback_query = None
    
    # Mock Context
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {'db_user': {'telegram_id': 12345, 'first_name': 'Test', 'balance': 0}}
    
    print("🧪 Testing start_command in maintenance mode...")
    
    # Mock maintenance mode ON
    with patch('handlers.common_handlers.check_maintenance_mode', return_value=True):
        result = await start_command(update, context)
    
    assert result == ConversationHandler.END, "Maintenance mode должен возвращать END"
    print("✅ Тест пройден: maintenance mode корректно обрабатывается")


if __name__ == '__main__':
    import asyncio
    
    print("=" * 60)
    print("🧪 Запуск тестов исправления ConversationHandler")
    print("=" * 60)
    
    # Run tests
    asyncio.run(test_start_command_clears_state_and_returns_end())
    asyncio.run(test_start_command_with_maintenance_mode())
    
    print("\n" + "=" * 60)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 60)
