#!/usr/bin/env python3
"""
Test script to simulate Telegram webhook updates and debug message handling
"""
import asyncio
import aiohttp
import os
import json
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001')

async def send_webhook_update(update_data):
    """Send a simulated webhook update to backend"""
    url = f"{BACKEND_URL}/api/telegram/webhook"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=update_data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                status = response.status
                text = await response.text()
                print(f"✅ Response: {status}")
                print(f"Body: {text}")
                return status, text
        except Exception as e:
            print(f"❌ Error: {e}")
            return None, str(e)

async def simulate_text_message_twice():
    """Simulate sending the same text message twice to test if first is ignored"""
    
    # Test user ID (use a test user, not admin)
    test_user_id = 123456789
    test_chat_id = 123456789
    test_username = "test_user"
    
    # First message
    update_1 = {
        "update_id": 1001,
        "message": {
            "message_id": 5001,
            "from": {
                "id": test_user_id,
                "is_bot": False,
                "first_name": "Test",
                "username": test_username
            },
            "chat": {
                "id": test_chat_id,
                "first_name": "Test",
                "username": test_username,
                "type": "private"
            },
            "date": int(datetime.now().timestamp()),
            "text": "123 Main Street"
        }
    }
    
    print("\n" + "="*50)
    print("📨 ПЕРВОЕ СООБЩЕНИЕ: '123 Main Street'")
    print("="*50)
    status1, response1 = await send_webhook_update(update_1)
    
    # Wait a bit
    await asyncio.sleep(3)
    
    # Second message (same text)
    update_2 = {
        "update_id": 1002,
        "message": {
            "message_id": 5002,
            "from": {
                "id": test_user_id,
                "is_bot": False,
                "first_name": "Test",
                "username": test_username
            },
            "chat": {
                "id": test_chat_id,
                "first_name": "Test",
                "username": test_username,
                "type": "private"
            },
            "date": int(datetime.now().timestamp()),
            "text": "123 Main Street"
        }
    }
    
    print("\n" + "="*50)
    print("📨 ВТОРОЕ СООБЩЕНИЕ (ПОВТОР): '123 Main Street'")
    print("="*50)
    status2, response2 = await send_webhook_update(update_2)
    
    print("\n" + "="*50)
    print("📊 РЕЗУЛЬТАТ ТЕСТА")
    print("="*50)
    print(f"Первое сообщение: {'✅ OK' if status1 == 200 else '❌ FAILED'}")
    print(f"Второе сообщение: {'✅ OK' if status2 == 200 else '❌ FAILED'}")
    print("\nПРОВЕРЬТЕ ЛОГИ БЭКЕНДА для деталей обработки")

if __name__ == "__main__":
    print("🧪 ТЕСТ: Проверка обработки текстовых сообщений")
    print("⚠️ ВНИМАНИЕ: Этот тест отправляет симулированные обновления")
    print("   Убедитесь, что пользователь находится в состоянии ввода адреса\n")
    
    asyncio.run(simulate_text_message_twice())
