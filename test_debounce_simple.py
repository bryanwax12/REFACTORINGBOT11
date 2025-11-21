#!/usr/bin/env python3
"""
Simple test to check if debounce decorator is working
"""
import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment
load_dotenv('/app/backend/.env')

WEBHOOK_URL = "https://telegram-admin-fix-2.emergent.host/api/telegram/webhook"
TEST_USER_ID = 999999999

def create_message_update(text, update_id):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {
                "id": TEST_USER_ID,
                "is_bot": False,
                "first_name": "TestUser",
                "username": "testuser"
            },
            "chat": {
                "id": TEST_USER_ID,
                "first_name": "TestUser",
                "type": "private"
            },
            "date": int(time.time()),
            "text": text
        }
    }

def create_callback_update(data, update_id):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"callback_{update_id}",
            "from": {
                "id": TEST_USER_ID,
                "is_bot": False,
                "first_name": "TestUser",
                "username": "testuser"
            },
            "message": {
                "message_id": update_id - 1,
                "from": {
                    "id": 123456789,
                    "is_bot": True,
                    "first_name": "Bot"
                },
                "chat": {
                    "id": TEST_USER_ID,
                    "first_name": "TestUser",
                    "type": "private"
                },
                "date": int(time.time()) - 1,
                "text": "Menu"
            },
            "chat_instance": f"chat_{update_id}",
            "data": data
        }
    }

def send_update(update):
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=update,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        return response.status_code, response.text
    except Exception as e:
        return 0, str(e)

def main():
    print("🔍 Testing Telegram Bot Debounce Functionality")
    print("=" * 60)
    
    # Step 1: Start conversation
    print("Step 1: Starting conversation with /start")
    start_update = create_message_update("/start", 1001)
    status, response = send_update(start_update)
    print(f"   /start: HTTP {status} - {response[:100]}")
    time.sleep(0.5)
    
    # Step 2: Click new order
    print("Step 2: Clicking 'new_order' button")
    new_order_update = create_callback_update("new_order", 1002)
    status, response = send_update(new_order_update)
    print(f"   new_order: HTTP {status} - {response[:100]}")
    time.sleep(1.0)  # Wait for conversation to start
    
    # Step 3: Send rapid messages to trigger debounce
    print("Step 3: Sending rapid messages (should trigger debounce)")
    messages = ["John Smith", "Jane Doe", "Bob Johnson", "Alice Brown"]
    
    start_time = time.time()
    for i, message in enumerate(messages):
        update = create_message_update(message, 1010 + i)
        status, response = send_update(update)
        elapsed = time.time() - start_time
        print(f"   Message {i+1} '{message}': HTTP {status} at {elapsed:.3f}s - {response[:50]}")
        
        # Very short delay to trigger debounce
        if i < len(messages) - 1:
            time.sleep(0.1)  # 100ms delay
    
    print(f"\nTotal time for {len(messages)} messages: {time.time() - start_time:.3f}s")
    
    # Step 4: Wait and check logs
    print("\nStep 4: Checking backend logs for debounce activity...")
    time.sleep(2)
    
    # Check logs
    try:
        log_cmd = "tail -n 100 /var/log/supervisor/backend.out.log | grep -i 'debounce\\|blocked\\|🚫'"
        log_result = os.popen(log_cmd).read()
        
        if log_result.strip():
            print("✅ Debounce activity found in logs:")
            for line in log_result.strip().split('\n')[:5]:  # Show first 5 lines
                print(f"   {line}")
        else:
            print("❌ No debounce activity found in logs")
            
            # Check for any recent activity
            print("\nChecking recent backend activity:")
            recent_cmd = "tail -n 20 /var/log/supervisor/backend.out.log"
            recent_result = os.popen(recent_cmd).read()
            print(recent_result)
            
    except Exception as e:
        print(f"❌ Error checking logs: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed. Check logs above for debounce behavior.")

if __name__ == "__main__":
    main()