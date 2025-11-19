#!/usr/bin/env python3
"""
Test Admin Error Notification
Simulates a bot error to test admin notification system
"""

import asyncio
import sys
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

# Load environment
load_dotenv('/app/backend/.env')

MONGO_URL = os.getenv('MONGO_URL')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID')

async def test_error_notification():
    """Simulate an error and test admin notification"""
    
    print("=" * 60)
    print("🧪 TESTING ADMIN ERROR NOTIFICATION SYSTEM")
    print("=" * 60)
    
    # Connect to DB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client['telegram_shipping_bot']
    
    # Import bot instance and notification function
    from server import bot_instance, ADMIN_TELEGRAM_ID as admin_id
    from handlers.admin_handlers import notify_admin_error
    from repositories import get_user_repo
    
    if not bot_instance:
        print("❌ Bot instance not available!")
        return False
    
    if not admin_id:
        print("❌ Admin ID not configured!")
        return False
    
    print(f"✅ Bot instance available")
    print(f"✅ Admin ID configured: {admin_id}")
    
    try:
        # Get test user (CALL SERVICE)
        user_repo = get_user_repo()
        test_user = await user_repo.find_by_telegram_id(5594152712)
        
        if not test_user:
            print("❌ Test user not found!")
            return False
        
        print(f"✅ Test user found: {test_user.get('username')}")
        
        # Test 1: Simple notification
        print("\n📤 Test 1: Sending test error notification...")
        
        await notify_admin_error(
            user_info=test_user,
            error_type="Test Error - System Check",
            error_details="Это тестовая ошибка для проверки системы уведомлений. Все работает корректно! ✅"
        )
        
        print("✅ Test notification sent!")
        
        # Test 2: Simulate real error with more details
        print("\n📤 Test 2: Sending detailed error notification...")
        
        await notify_admin_error(
            user_info=test_user,
            error_type="TypeError - Order Processing",
            error_details="TypeError: 'NoneType' object has no attribute 'order_id'. User tried to process payment but order context was lost after balance top-up.",
            order_id="ORD-20251119-TEST123"
        )
        
        print("✅ Detailed notification sent!")
        
        # Test 3: Global error handler simulation
        print("\n📤 Test 3: Simulating global error handler...")
        
        # Create a mock context error
        class MockError(Exception):
            pass
        
        test_error = MockError("Симуляция критической ошибки в боте")
        error_details = f"{type(test_error).__name__}: {str(test_error)}"
        
        await notify_admin_error(
            user_info=test_user,
            error_type="Global Bot Error (Test)",
            error_details=error_details
        )
        
        print("✅ Global error simulation sent!")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\n📱 Проверьте Telegram бот админа (ID: {admin_id})")
        print(f"   Вы должны получить 3 уведомления об ошибках")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(test_error_notification())
    sys.exit(0 if success else 1)
