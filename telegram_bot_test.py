#!/usr/bin/env python3
"""
Telegram Bot Basic Flow Test - Review Request
Tests the Telegram bot basic flow as requested in the review
"""

import requests
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

# Use localhost for testing since bot is running in polling mode
BACKEND_URL = "http://localhost:8001"

def test_telegram_bot_basic_flow():
    """Test Telegram bot basic flow as requested in review"""
    print("🚀 TELEGRAM BOT BASIC FLOW TEST")
    print("🎯 REVIEW REQUEST: Test /start command, 'Новый заказ' flow, sender name/address entry")
    print(f"Backend URL: {BACKEND_URL}")
    print("=" * 80)
    
    results = {}
    
    # Test 1: Check backend health
    print("\n🔍 Test 1: Backend Health Check")
    try:
        response = requests.get(f"{BACKEND_URL}/monitoring/health", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✅ Backend is healthy: {health_data['status']}")
            print(f"   MongoDB: {health_data['components']['mongodb']['status']}")
            results['backend_health'] = True
        else:
            print(f"   ❌ Backend health check failed")
            results['backend_health'] = False
    except Exception as e:
        print(f"   ❌ Backend health check error: {e}")
        results['backend_health'] = False
    
    # Test 2: Check Telegram webhook endpoint availability
    print("\n🔍 Test 2: Telegram Webhook Endpoint")
    try:
        # Test GET (should return 405 Method Not Allowed)
        response = requests.get(f"{BACKEND_URL}/telegram/webhook", timeout=10)
        print(f"   GET /telegram/webhook: {response.status_code}")
        
        if response.status_code == 405:
            print(f"   ✅ Webhook endpoint exists (405 Method Not Allowed expected for GET)")
            results['webhook_endpoint'] = True
        else:
            print(f"   ⚠️ Unexpected response: {response.status_code}")
            results['webhook_endpoint'] = False
    except Exception as e:
        print(f"   ❌ Webhook endpoint test error: {e}")
        results['webhook_endpoint'] = False
    
    # Test 3: Simulate /start command
    print("\n🔍 Test 3: Simulate /start Command")
    try:
        test_user_id = 999999999
        start_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": test_user_id,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": test_user_id,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "/start",
                "entities": [{"offset": 0, "length": 6, "type": "bot_command"}]
            }
        }
        
        response = requests.post(
            f"{BACKEND_URL}/telegram/webhook",
            json=start_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"   ✅ /start command processed successfully")
                print(f"   Response: {result}")
                results['start_command'] = True
            except:
                print(f"   ✅ /start command processed (no JSON response)")
                results['start_command'] = True
        else:
            print(f"   ❌ /start command failed: {response.status_code}")
            try:
                error = response.json()
                print(f"   Error: {error}")
            except:
                print(f"   Error: {response.text}")
            results['start_command'] = False
            
    except Exception as e:
        print(f"   ❌ /start command test error: {e}")
        results['start_command'] = False
    
    # Test 4: Simulate "Новый заказ" button click
    print("\n🔍 Test 4: Simulate 'Новый заказ' Button Click")
    try:
        new_order_update = {
            "update_id": 123456790,
            "callback_query": {
                "id": "test_callback_123",
                "from": {
                    "id": test_user_id,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "language_code": "en"
                },
                "message": {
                    "message_id": 2,
                    "from": {
                        "id": 123456789,
                        "is_bot": True,
                        "first_name": "TestBot",
                        "username": "testbot"
                    },
                    "chat": {
                        "id": test_user_id,
                        "first_name": "TestUser",
                        "username": "testuser",
                        "type": "private"
                    },
                    "date": int(time.time()),
                    "text": "Welcome message"
                },
                "chat_instance": "test_chat_instance",
                "data": "new_order"
            }
        }
        
        response = requests.post(
            f"{BACKEND_URL}/telegram/webhook",
            json=new_order_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ 'Новый заказ' button processed successfully")
            results['new_order_button'] = True
        else:
            print(f"   ❌ 'Новый заказ' button failed: {response.status_code}")
            results['new_order_button'] = False
            
    except Exception as e:
        print(f"   ❌ 'Новый заказ' button test error: {e}")
        results['new_order_button'] = False
    
    # Test 5: Simulate sender name input
    print("\n🔍 Test 5: Simulate Sender Name Input")
    try:
        name_input_update = {
            "update_id": 123456791,
            "message": {
                "message_id": 3,
                "from": {
                    "id": test_user_id,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": test_user_id,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "John Smith"
            }
        }
        
        response = requests.post(
            f"{BACKEND_URL}/telegram/webhook",
            json=name_input_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Sender name input processed successfully")
            results['sender_name'] = True
        else:
            print(f"   ❌ Sender name input failed: {response.status_code}")
            results['sender_name'] = False
            
    except Exception as e:
        print(f"   ❌ Sender name input test error: {e}")
        results['sender_name'] = False
    
    # Test 6: Simulate sender address input
    print("\n🔍 Test 6: Simulate Sender Address Input")
    try:
        address_input_update = {
            "update_id": 123456792,
            "message": {
                "message_id": 4,
                "from": {
                    "id": test_user_id,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": test_user_id,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "123 Main Street"
            }
        }
        
        response = requests.post(
            f"{BACKEND_URL}/telegram/webhook",
            json=address_input_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Sender address input processed successfully")
            results['sender_address'] = True
        else:
            print(f"   ❌ Sender address input failed: {response.status_code}")
            results['sender_address'] = False
            
    except Exception as e:
        print(f"   ❌ Sender address input test error: {e}")
        results['sender_address'] = False
    
    # Test 7: Check bot token validation
    print("\n🔍 Test 7: Bot Token Validation")
    try:
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if bot_token and bot_token != "your_telegram_bot_token_here":
            # Test token by calling Telegram API
            response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    bot_data = bot_info.get('result', {})
                    print(f"   ✅ Bot token valid")
                    print(f"   Bot name: {bot_data.get('first_name', 'Unknown')}")
                    print(f"   Bot username: @{bot_data.get('username', 'Unknown')}")
                    results['bot_token'] = True
                else:
                    print(f"   ❌ Invalid bot token")
                    results['bot_token'] = False
            else:
                print(f"   ❌ Bot token validation failed")
                results['bot_token'] = False
        else:
            print(f"   ❌ Bot token not configured")
            results['bot_token'] = False
    except Exception as e:
        print(f"   ❌ Bot token validation error: {e}")
        results['bot_token'] = False
    
    # Test 8: Check bot responds without errors
    print("\n🔍 Test 8: Error Handling Test")
    try:
        # Send invalid update to test error handling
        invalid_update = {
            "update_id": 123456793,
            "invalid_field": "test"
        }
        
        response = requests.post(
            f"{BACKEND_URL}/telegram/webhook",
            json=invalid_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status: {response.status_code}")
        # Bot should handle invalid updates gracefully (200 or 400 are both acceptable)
        if response.status_code in [200, 400]:
            print(f"   ✅ Bot handles invalid updates gracefully")
            results['error_handling'] = True
        else:
            print(f"   ❌ Bot error handling issues")
            results['error_handling'] = False
            
    except Exception as e:
        print(f"   ❌ Error handling test error: {e}")
        results['error_handling'] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TELEGRAM BOT BASIC FLOW TEST RESULTS")
    print("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print(f"SUCCESS RATE: {success_rate:.1f}% ({passed}/{total} tests passed)")
    print()
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print()
    
    # Review request assessment
    core_tests = ['webhook_endpoint', 'start_command', 'new_order_button', 'sender_name', 'sender_address']
    core_passed = sum(1 for test in core_tests if results.get(test, False))
    core_success_rate = (core_passed / len(core_tests)) * 100
    
    print("🎯 REVIEW REQUEST ASSESSMENT:")
    print(f"   Core Bot Flow: {core_success_rate:.1f}% ({core_passed}/{len(core_tests)} tests passed)")
    
    if core_success_rate >= 80:
        print("   ✅ TELEGRAM BOT BASIC FLOW IS WORKING")
    elif core_success_rate >= 60:
        print("   ⚠️ TELEGRAM BOT BASIC FLOW HAS MINOR ISSUES")
    else:
        print("   ❌ TELEGRAM BOT BASIC FLOW HAS MAJOR ISSUES")
    
    # Overall assessment
    if success_rate >= 80:
        print("\n🎉 OVERALL: TELEGRAM BOT BACKEND IS HEALTHY")
    elif success_rate >= 60:
        print("\n⚠️ OVERALL: TELEGRAM BOT BACKEND HAS ISSUES")
    else:
        print("\n🚨 OVERALL: TELEGRAM BOT BACKEND NEEDS ATTENTION")
    
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    test_telegram_bot_basic_flow()