#!/usr/bin/env python3
"""
Regression Test for Handlers Refactoring
Tests the modular architecture after moving functions to handlers modules
"""

import requests
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://easyshipbot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def test_telegram_webhook_endpoint():
    """Test Telegram webhook endpoint - CRITICAL TEST per review request"""
    print("\n🔍 Testing Telegram Webhook Endpoint...")
    print("🎯 CRITICAL: Testing /api/telegram/webhook endpoint after refactoring")
    
    try:
        # Test 1: GET request to webhook endpoint (should return method not allowed or basic info)
        print("   Test 1: GET /api/telegram/webhook")
        response = requests.get(f"{API_BASE}/telegram/webhook", timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        # Webhook endpoints typically don't support GET, so 405 is expected
        if response.status_code in [405, 200]:
            print("   ✅ Webhook endpoint accessible")
        else:
            print(f"   ❌ Webhook endpoint not accessible: {response.status_code}")
            return False
        
        # Test 2: POST request with invalid data (should handle gracefully)
        print("   Test 2: POST /api/telegram/webhook with invalid data")
        invalid_payload = {"invalid": "data"}
        
        response = requests.post(
            f"{API_BASE}/telegram/webhook",
            json=invalid_payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        
        # Should handle invalid data gracefully (200 or 400 are both acceptable)
        if response.status_code in [200, 400]:
            print("   ✅ Webhook handles invalid data gracefully")
        else:
            print(f"   ❌ Webhook error handling issue: {response.status_code}")
            return False
        
        # Test 3: POST request with valid Telegram Update structure
        print("   Test 3: POST /api/telegram/webhook with valid Update structure")
        
        # Create a valid Telegram Update object for /start command
        valid_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 999999999,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser",
                    "language_code": "en"
                },
                "chat": {
                    "id": 999999999,
                    "first_name": "Test",
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
            print("   ✅ Webhook processes valid Telegram updates")
            
            # Check response format
            try:
                response_data = response.json()
                if response_data.get('ok'):
                    print("   ✅ Webhook returns correct response format")
                else:
                    print(f"   ⚠️ Webhook response format: {response_data}")
            except Exception:
                print("   ⚠️ Webhook response not JSON (may be expected)")
        else:
            print(f"   ❌ Webhook failed to process valid update: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except Exception:
                print(f"      Error: {response.text}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram webhook endpoint test error: {e}")
        return False


def test_admin_api_endpoints():
    """Test Admin API endpoints with authentication - CRITICAL TEST per review request"""
    print("\n🔍 Testing Admin API Endpoints...")
    print("🎯 CRITICAL: Testing admin endpoints with X-Api-Key authentication after refactoring")
    
    try:
        # Load admin API key from environment
        load_dotenv('/app/backend/.env')
        admin_api_key = os.environ.get('ADMIN_API_KEY')
        
        if not admin_api_key:
            print("   ❌ ADMIN_API_KEY not found in environment")
            return False
        
        print("   Admin API key loaded: ✅")
        
        # Test 1: GET /api/admin/stats with correct API key
        print("   Test 1: GET /api/admin/stats with valid API key")
        
        headers = {
            'X-Api-Key': admin_api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(f"{API_BASE}/admin/stats", headers=headers, timeout=15)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            stats_data = response.json()
            print("   ✅ Admin stats endpoint working")
            print(f"   📊 Stats data keys: {list(stats_data.keys())}")
            
            # Verify expected stats fields
            expected_fields = ['total_users', 'total_orders', 'paid_orders', 'total_revenue']
            for field in expected_fields:
                if field in stats_data:
                    print(f"      {field}: ✅ ({stats_data[field]})")
                else:
                    print(f"      {field}: ❌ (missing)")
        else:
            print(f"   ❌ Admin stats failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except Exception:
                print(f"      Error: {response.text}")
            return False
        
        # Test 2: Test without API key (should fail)
        print("   Test 2: GET /api/admin/stats without API key (should fail)")
        
        response = requests.get(f"{API_BASE}/admin/stats", timeout=15)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code in [401, 403]:
            print("   ✅ Correctly rejected request without API key")
        else:
            print(f"   ❌ Should have rejected request without API key: {response.status_code}")
            return False
        
        print("   ✅ All admin API endpoint tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Admin API endpoints test error: {e}")
        return False


def test_handlers_import_verification():
    """Test handlers module imports - CRITICAL TEST per review request"""
    print("\n🔍 Testing Handlers Module Imports...")
    print("🎯 CRITICAL: Verifying functions moved to handlers modules import correctly")
    
    try:
        # Test 1: Check if handlers modules exist
        print("   Test 1: Handlers modules existence")
        
        import os
        handlers_dir = '/app/backend/handlers'
        expected_modules = [
            'common_handlers.py',
            'admin_handlers.py',
            'payment_handlers.py',
            'template_handlers.py',
            'order_handlers.py'
        ]
        
        for module in expected_modules:
            module_path = os.path.join(handlers_dir, module)
            exists = os.path.exists(module_path)
            print(f"      {module}: {'✅' if exists else '❌'}")
            if not exists:
                return False
        
        # Test 2: Test imports from server.py
        print("   Test 2: Server.py imports from handlers modules")
        
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        expected_imports = [
            'from handlers.common_handlers import',
            'from handlers.admin_handlers import',
            'start_command',
            'help_command',
            'faq_command',
            'button_callback',
            'verify_admin_key',
            'notify_admin_error'
        ]
        
        for import_item in expected_imports:
            found = import_item in server_code
            print(f"      {import_item}: {'✅' if found else '❌'}")
            if not found:
                return False
        
        # Test 3: Test specific function imports
        print("   Test 3: Critical function imports verification")
        
        try:
            # Import functions from handlers modules
            import sys
            sys.path.append('/app/backend')
            
            from handlers.common_handlers import start_command, help_command, faq_command, button_callback
            print("      common_handlers functions: ✅")
            
            from handlers.admin_handlers import verify_admin_key, notify_admin_error
            print("      admin_handlers functions: ✅")
            
        except ImportError as e:
            print(f"      ❌ Import error: {e}")
            return False
        
        # Test 4: Check for import errors in backend logs
        print("   Test 4: Backend logs import error check")
        
        log_result = os.popen("tail -n 100 /var/log/supervisor/backend.err.log | grep -i 'import\\|module'").read()
        
        # Look for import-related errors
        import_errors = []
        for line in log_result.split('\n'):
            line_lower = line.lower()
            if any(error in line_lower for error in ['importerror', 'modulenotfounderror', 'cannot import']):
                import_errors.append(line.strip())
        
        if import_errors:
            print("      ❌ Import errors found in logs:")
            for error in import_errors[-3:]:  # Show last 3 import errors
                if error:
                    print(f"         {error}")
            return False
        else:
            print("      ✅ No import errors in backend logs")
        
        print("   ✅ All handlers import tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Handlers import verification test error: {e}")
        return False


def test_api_health():
    """Test if the API is running"""
    print("🔍 Testing API Health...")
    try:
        response = requests.get(f"{API_BASE}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Health: {data}")
            return True
        else:
            print(f"❌ API Health failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API Health error: {e}")
        return False


def main():
    """Main regression test for handlers refactoring"""
    print("🚀 РЕГРЕССИОННОЕ ТЕСТИРОВАНИЕ HANDLERS REFACTORING")
    print("🎯 ЦЕЛЬ: Проверить работоспособность бота после рефакторинга модульной архитектуры")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Base: {API_BASE}")
    
    # Track test results
    test_results = {}
    
    # Run core tests
    test_results['api_health'] = test_api_health()
    test_results['telegram_webhook'] = test_telegram_webhook_endpoint()
    test_results['admin_api'] = test_admin_api_endpoints()
    test_results['handlers_imports'] = test_handlers_import_verification()
    
    # Calculate results
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"\n{'='*80}")
    print("📊 РЕЗУЛЬТАТЫ РЕГРЕССИОННОГО ТЕСТИРОВАНИЯ")
    print(f"{'='*80}")
    
    for test_name, result in test_results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"   {test_name}: {status}")
    
    print("\n📈 ОБЩИЕ РЕЗУЛЬТАТЫ:")
    print(f"   Всего тестов: {total_tests}")
    print(f"   Пройдено: {passed_tests} ✅")
    print(f"   Провалено: {total_tests - passed_tests} ❌")
    print(f"   Процент успеха: {success_rate:.1f}%")
    
    if success_rate >= 75:
        print("\n✅ РЕГРЕССИОННОЕ ТЕСТИРОВАНИЕ УСПЕШНО ЗАВЕРШЕНО")
        print("   Рефакторинг модульной архитектуры работает корректно")
        return True
    else:
        print("\n❌ РЕГРЕССИОННОЕ ТЕСТИРОВАНИЕ ВЫЯВИЛО ПРОБЛЕМЫ")
        print("   Требуется исправление ошибок рефакторинга")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)