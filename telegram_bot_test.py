#!/usr/bin/env python3
"""
Focused Telegram Bot Testing for Regression Testing
Tests critical bot functionality after refactoring
"""

import requests
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tgbot-revamp.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def test_telegram_bot_status():
    """Test Telegram bot status endpoint - CRITICAL TEST"""
    print("🔍 Testing Telegram Bot Status...")
    print("🎯 CRITICAL: Verifying bot is running after refactoring")
    
    try:
        response = requests.get(f"{API_BASE}/telegram/status", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Bot Status Response: {json.dumps(data, indent=2)}")
            
            # Critical checks from review request
            application_running = data.get('application_running', False)
            bot_instance = data.get('bot_instance', False)
            telegram_token_set = data.get('telegram_token_set', False)
            bot_mode = data.get('bot_mode', 'Unknown')
            
            print(f"\n📊 CRITICAL BOT STATUS CHECKS:")
            print(f"   Application running: {'✅' if application_running else '❌'}")
            print(f"   Bot instance created: {'✅' if bot_instance else '❌'}")
            print(f"   Telegram token set: {'✅' if telegram_token_set else '❌'}")
            print(f"   Bot mode: {bot_mode} {'✅' if bot_mode == 'WEBHOOK' else '⚠️'}")
            
            # Check conversation handlers
            conv_handlers = data.get('conversation_handlers', [])
            print(f"   Conversation handlers: {len(conv_handlers)} {'✅' if len(conv_handlers) >= 2 else '❌'}")
            
            if application_running and bot_instance and telegram_token_set:
                print(f"   ✅ TELEGRAM BOT INFRASTRUCTURE: All critical components working")
                return True
            else:
                print(f"   ❌ TELEGRAM BOT INFRASTRUCTURE: Missing critical components")
                return False
        else:
            print(f"❌ Bot status check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Bot status test error: {e}")
        return False

def test_telegram_webhook_endpoint():
    """Test Telegram webhook endpoint - CRITICAL TEST"""
    print("\n🔍 Testing Telegram Webhook Endpoint...")
    print("🎯 CRITICAL: Testing /api/telegram/webhook after handlers refactoring")
    
    try:
        # Test 1: GET request (should return method not allowed or basic info)
        print("   Test 1: GET /api/telegram/webhook")
        response = requests.get(f"{API_BASE}/telegram/webhook", timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code in [405, 200]:
            print(f"   ✅ Webhook endpoint accessible")
        else:
            print(f"   ❌ Webhook endpoint issue: {response.status_code}")
            return False
        
        # Test 2: POST with invalid data (should handle gracefully)
        print("   Test 2: POST with invalid data")
        invalid_payload = {"invalid": "data"}
        
        response = requests.post(
            f"{API_BASE}/telegram/webhook",
            json=invalid_payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code in [200, 400]:
            print(f"   ✅ Webhook handles invalid data gracefully")
        else:
            print(f"   ❌ Webhook error handling issue: {response.status_code}")
            return False
        
        # Test 3: POST with valid Telegram Update structure
        print("   Test 3: POST with valid /start command")
        
        valid_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 999999999,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "language_code": "ru"
                },
                "chat": {
                    "id": 999999999,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "/start"
            }
        }
        
        response = requests.post(
            f"{API_BASE}/telegram/webhook",
            json=valid_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ Webhook processes /start command successfully")
            
            try:
                response_data = response.json()
                if response_data.get('ok') == True:
                    print(f"   ✅ Webhook returns correct response format")
                else:
                    print(f"   ⚠️ Webhook response: {response_data}")
            except:
                print(f"   ⚠️ Webhook response not JSON (may be expected)")
        else:
            print(f"   ❌ Webhook failed to process /start: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Webhook endpoint test error: {e}")
        return False

def test_telegram_help_command():
    """Test /help command via webhook - CRITICAL TEST"""
    print("\n🔍 Testing /help Command via Webhook...")
    print("🎯 CRITICAL: Testing help command after handlers refactoring")
    
    try:
        help_update = {
            "update_id": 123456790,
            "message": {
                "message_id": 2,
                "from": {
                    "id": 999999998,
                    "is_bot": False,
                    "first_name": "TestUser2",
                    "username": "testuser2",
                    "language_code": "ru"
                },
                "chat": {
                    "id": 999999998,
                    "first_name": "TestUser2",
                    "username": "testuser2",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "/help"
            }
        }
        
        response = requests.post(
            f"{API_BASE}/telegram/webhook",
            json=help_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ /help command processed successfully")
            
            try:
                response_data = response.json()
                if response_data.get('ok') == True:
                    print(f"   ✅ Help command returns correct response")
                else:
                    print(f"   ⚠️ Help response: {response_data}")
            except:
                print(f"   ⚠️ Help response not JSON (may be expected)")
            
            return True
        else:
            print(f"   ❌ /help command failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Help command test error: {e}")
        return False

def test_telegram_callback_buttons():
    """Test callback button handling - CRITICAL TEST"""
    print("\n🔍 Testing Callback Button Handling...")
    print("🎯 CRITICAL: Testing inline keyboard buttons after refactoring")
    
    try:
        # Test callback query for main menu button
        callback_update = {
            "update_id": 123456791,
            "callback_query": {
                "id": "test_callback_123",
                "from": {
                    "id": 999999997,
                    "is_bot": False,
                    "first_name": "TestUser3",
                    "username": "testuser3",
                    "language_code": "ru"
                },
                "message": {
                    "message_id": 3,
                    "from": {
                        "id": 8492458522,
                        "is_bot": True,
                        "first_name": "White Label Shipping Bot",
                        "username": "whitelabel_shipping_bot"
                    },
                    "chat": {
                        "id": 999999997,
                        "first_name": "TestUser3",
                        "username": "testuser3",
                        "type": "private"
                    },
                    "date": int(time.time()),
                    "text": "Test message with buttons"
                },
                "data": "start"
            }
        }
        
        response = requests.post(
            f"{API_BASE}/telegram/webhook",
            json=callback_update,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ Callback button 'start' processed successfully")
            
            try:
                response_data = response.json()
                if response_data.get('ok') == True:
                    print(f"   ✅ Callback returns correct response")
                else:
                    print(f"   ⚠️ Callback response: {response_data}")
            except:
                print(f"   ⚠️ Callback response not JSON (may be expected)")
            
            return True
        else:
            print(f"   ❌ Callback button failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Callback button test error: {e}")
        return False

def test_handlers_import():
    """Test that handlers are properly imported - CRITICAL TEST"""
    print("\n🔍 Testing Handlers Import After Refactoring...")
    print("🎯 CRITICAL: Verifying handlers moved to separate modules")
    
    try:
        # Check if handlers modules exist
        import sys
        sys.path.append('/app/backend')
        
        # Test importing common handlers
        try:
            from handlers.common_handlers import start_command, help_command, faq_command, button_callback
            print("   ✅ Common handlers imported successfully")
            common_handlers_ok = True
        except ImportError as e:
            print(f"   ❌ Common handlers import failed: {e}")
            common_handlers_ok = False
        
        # Test importing admin handlers
        try:
            from handlers.admin_handlers import verify_admin_key, notify_admin_error
            print("   ✅ Admin handlers imported successfully")
            admin_handlers_ok = True
        except ImportError as e:
            print(f"   ❌ Admin handlers import failed: {e}")
            admin_handlers_ok = False
        
        # Test importing webhook handlers
        try:
            from handlers.webhook_handlers import handle_oxapay_webhook, handle_telegram_webhook
            print("   ✅ Webhook handlers imported successfully")
            webhook_handlers_ok = True
        except ImportError as e:
            print(f"   ❌ Webhook handlers import failed: {e}")
            webhook_handlers_ok = False
        
        # Test importing order flow handlers
        try:
            from handlers.order_flow.from_address import order_from_name, order_from_address
            from handlers.order_flow.to_address import order_to_name, order_to_address
            from handlers.order_flow.parcel import order_parcel_weight
            print("   ✅ Order flow handlers imported successfully")
            order_handlers_ok = True
        except ImportError as e:
            print(f"   ❌ Order flow handlers import failed: {e}")
            order_handlers_ok = False
        
        all_imports_ok = (common_handlers_ok and admin_handlers_ok and 
                         webhook_handlers_ok and order_handlers_ok)
        
        print(f"\n📊 HANDLERS REFACTORING VERIFICATION:")
        print(f"   Common handlers: {'✅' if common_handlers_ok else '❌'}")
        print(f"   Admin handlers: {'✅' if admin_handlers_ok else '❌'}")
        print(f"   Webhook handlers: {'✅' if webhook_handlers_ok else '❌'}")
        print(f"   Order flow handlers: {'✅' if order_handlers_ok else '❌'}")
        
        if all_imports_ok:
            print(f"   ✅ HANDLERS REFACTORING: All modules imported successfully")
        else:
            print(f"   ❌ HANDLERS REFACTORING: Some modules failed to import")
        
        return all_imports_ok
        
    except Exception as e:
        print(f"❌ Handlers import test error: {e}")
        return False

def check_backend_logs_for_errors():
    """Check backend logs for critical errors"""
    print("\n🔍 Checking Backend Logs for Critical Errors...")
    
    try:
        # Check error logs
        result = os.popen("tail -n 100 /var/log/supervisor/backend.err.log").read()
        
        # Look for critical errors (excluding Telegram polling conflicts)
        critical_errors = []
        for line in result.split('\n'):
            line_lower = line.lower()
            # Skip Telegram polling conflicts as they're expected in webhook mode
            if any(skip in line_lower for skip in ['conflict', 'getupdates', 'polling']):
                continue
            # Look for actual critical errors
            if any(error in line_lower for error in ['error', 'failed', 'exception', 'traceback']):
                if any(critical in line_lower for critical in ['import', 'module', 'handler', 'webhook']):
                    critical_errors.append(line.strip())
        
        if critical_errors:
            print("   ❌ Critical errors found in logs:")
            for error in critical_errors[-5:]:  # Show last 5 critical errors
                if error:
                    print(f"      {error}")
            return False
        else:
            print("   ✅ No critical errors found in backend logs")
            return True
            
    except Exception as e:
        print(f"❌ Error checking logs: {e}")
        return False

def main():
    """Run focused Telegram bot regression tests"""
    print("🚀 TELEGRAM BOT REGRESSION TESTING AFTER REFACTORING")
    print("🎯 Focus: Critical bot functionality after handlers refactoring")
    print("=" * 80)
    
    tests = [
        ("Bot Status", test_telegram_bot_status),
        ("Webhook Endpoint", test_telegram_webhook_endpoint),
        ("Help Command", test_telegram_help_command),
        ("Callback Buttons", test_telegram_callback_buttons),
        ("Handlers Import", test_handlers_import),
        ("Backend Logs", check_backend_logs_for_errors)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔄 Running {test_name} Test...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TELEGRAM BOT REGRESSION TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 REGRESSION TEST RESULTS:")
    print(f"   Tests Passed: {passed}/{total}")
    print(f"   Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print(f"   ✅ ALL TESTS PASSED: Telegram bot working correctly after refactoring")
    elif passed >= total * 0.8:
        print(f"   ⚠️ MOSTLY WORKING: {total-passed} minor issues found")
    else:
        print(f"   ❌ CRITICAL ISSUES: {total-passed} major problems found")
    
    print("\n🔄 REFACTORING VERIFICATION:")
    if results.get("Handlers Import", False) and results.get("Bot Status", False):
        print("   ✅ HANDLERS REFACTORING: Successfully moved to modular architecture")
    else:
        print("   ❌ HANDLERS REFACTORING: Issues with modular architecture")
    
    if results.get("Webhook Endpoint", False) and results.get("Callback Buttons", False):
        print("   ✅ BOT FUNCTIONALITY: Core commands and buttons working")
    else:
        print("   ❌ BOT FUNCTIONALITY: Issues with commands or buttons")

if __name__ == "__main__":
    main()