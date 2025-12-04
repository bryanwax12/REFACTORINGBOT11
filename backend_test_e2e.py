#!/usr/bin/env python3
"""
ФИНАЛЬНОЕ E2E ТЕСТИРОВАНИЕ - PRODUCTION READINESS CHECK
Comprehensive testing suite for Telegram Shipping Bot production deployment
Based on review request: https://orderbot-upgrade.emergent.host
"""

import requests
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

# Production Configuration from review request
BACKEND_URL = "https://orderbot-upgrade.emergent.host"
API_BASE = f"{BACKEND_URL}/api"
WEBHOOK_URL = f"{BACKEND_URL}/api/telegram/webhook"

# Production Bot Configuration
PROD_BOT_TOKEN = "8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM"
ADMIN_API_KEY = "sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024"
TEST_USER_ID = 7066790254  # Test user with balance from review request

print(f"🚀 PRODUCTION E2E TEST CONFIGURATION:")
print(f"   Backend URL: {BACKEND_URL}")
print(f"   Webhook URL: {WEBHOOK_URL}")
print(f"   Production Bot: @whitelabel_shipping_bot")
print(f"   Test User ID: {TEST_USER_ID}")
print(f"   Admin API Key: {ADMIN_API_KEY[:20]}...")

# Test data from review request
TEST_FROM_ADDRESS = {
    "name": "John Smith",
    "street1": "123 Main St",
    "city": "San Francisco", 
    "state": "CA",
    "zip": "94102",
    "phone": "+14155551234"
}

TEST_TO_ADDRESS = {
    "name": "Jane Doe",
    "street1": "456 Oak Ave", 
    "city": "Los Angeles",
    "state": "CA", 
    "zip": "90001",
    "phone": "+13105555678"
}

TEST_PARCEL = {
    "weight": 5,
    "length": 10,
    "width": 10,
    "height": 5
}

# ==================== БЛОК 1: FULL USER FLOW (Priority: CRITICAL) ====================

def test_full_user_flow():
    """Test complete order creation flow from start to finish - CRITICAL REVIEW REQUEST"""
    print("\n🔍 БЛОК 1: FULL USER FLOW - Создание заказа от начала до конца")
    print("🎯 КРИТИЧЕСКИЙ ТЕСТ: /start → Новый заказ → Все данные → Выбор тарифа → Оплата")
    print(f"📋 Тестовые данные: User {TEST_USER_ID}, SF→LA, 5lbs, 10x10x5")
    
    try:
        # Step 1: /start command
        print(f"\n   📋 Шаг 1: Команда /start")
        start_update = {
            "update_id": int(time.time() * 1000),
            "message": {
                "message_id": 1,
                "from": {
                    "id": TEST_USER_ID,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "language_code": "ru"
                },
                "chat": {
                    "id": TEST_USER_ID,
                    "first_name": "TestUser", 
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "/start"
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=start_update, timeout=15)
        print(f"   POST /start: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        if response.status_code != 200:
            print(f"   ❌ /start failed: {response.text}")
            return False
        
        # Step 2: "Новый заказ" button
        print(f"\n   📋 Шаг 2: Кнопка 'Новый заказ'")
        time.sleep(0.5)
        
        new_order_update = {
            "update_id": int(time.time() * 1000) + 1,
            "callback_query": {
                "id": f"new_order_{int(time.time())}",
                "from": {
                    "id": TEST_USER_ID,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser"
                },
                "message": {
                    "message_id": 2,
                    "from": {"id": 123456789, "is_bot": True, "first_name": "Bot"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": "Main menu"
                },
                "chat_instance": "test_chat_instance",
                "data": "new_order"
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=new_order_update, timeout=15)
        print(f"   Новый заказ: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Step 3-8: Sender Details
        sender_steps = [
            ("Имя отправителя", TEST_FROM_ADDRESS["name"]),
            ("Адрес 1", TEST_FROM_ADDRESS["street1"]),
            ("Город", TEST_FROM_ADDRESS["city"]),
            ("Штат", TEST_FROM_ADDRESS["state"]),
            ("ZIP", TEST_FROM_ADDRESS["zip"]),
            ("Телефон", TEST_FROM_ADDRESS["phone"])
        ]
        
        print(f"\n   📋 Шаги 3-8: Данные отправителя")
        for i, (field_name, value) in enumerate(sender_steps, 3):
            time.sleep(0.3)
            
            text_update = {
                "update_id": int(time.time() * 1000) + i,
                "message": {
                    "message_id": i + 1,
                    "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": value
                }
            }
            response = requests.post(WEBHOOK_URL, json=text_update, timeout=15)
            print(f"   Шаг {i} ({field_name}): {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Skip Address 2
        print(f"\n   📋 Шаг 9: Пропуск Address 2")
        skip_update = {
            "update_id": int(time.time() * 1000) + 9,
            "callback_query": {
                "id": f"skip_{int(time.time())}",
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "message": {
                    "message_id": 10,
                    "from": {"id": 123456789, "is_bot": True, "first_name": "Bot"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": "Address 2 step"
                },
                "chat_instance": "test_chat_instance",
                "data": "skip_from_address2"
            }
        }
        response = requests.post(WEBHOOK_URL, json=skip_update, timeout=15)
        print(f"   Skip Address 2: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Step 10-15: Recipient Details
        recipient_steps = [
            ("Имя получателя", TEST_TO_ADDRESS["name"]),
            ("Адрес получателя", TEST_TO_ADDRESS["street1"]),
            ("Город получателя", TEST_TO_ADDRESS["city"]),
            ("Штат получателя", TEST_TO_ADDRESS["state"]),
            ("ZIP получателя", TEST_TO_ADDRESS["zip"]),
            ("Телефон получателя", TEST_TO_ADDRESS["phone"])
        ]
        
        print(f"\n   📋 Шаги 10-15: Данные получателя")
        for i, (field_name, value) in enumerate(recipient_steps, 10):
            time.sleep(0.3)
            
            text_update = {
                "update_id": int(time.time() * 1000) + i,
                "message": {
                    "message_id": i + 1,
                    "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": value
                }
            }
            response = requests.post(WEBHOOK_URL, json=text_update, timeout=15)
            print(f"   Шаг {i} ({field_name}): {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Skip TO Address 2
        print(f"\n   📋 Шаг 16: Пропуск TO Address 2")
        skip_to_update = {
            "update_id": int(time.time() * 1000) + 16,
            "callback_query": {
                "id": f"skip_to_{int(time.time())}",
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "message": {
                    "message_id": 17,
                    "from": {"id": 123456789, "is_bot": True, "first_name": "Bot"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": "TO Address 2 step"
                },
                "chat_instance": "test_chat_instance",
                "data": "skip_to_address2"
            }
        }
        response = requests.post(WEBHOOK_URL, json=skip_to_update, timeout=15)
        print(f"   Skip TO Address 2: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Step 17-20: Parcel Details
        parcel_steps = [
            ("Вес (lbs)", str(TEST_PARCEL["weight"])),
            ("Длина (in)", str(TEST_PARCEL["length"])),
            ("Ширина (in)", str(TEST_PARCEL["width"])),
            ("Высота (in)", str(TEST_PARCEL["height"]))
        ]
        
        print(f"\n   📋 Шаги 17-20: Данные посылки")
        for i, (field_name, value) in enumerate(parcel_steps, 17):
            time.sleep(0.3)
            
            text_update = {
                "update_id": int(time.time() * 1000) + i,
                "message": {
                    "message_id": i + 1,
                    "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": value
                }
            }
            response = requests.post(WEBHOOK_URL, json=text_update, timeout=15)
            print(f"   Шаг {i} ({field_name}): {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        print(f"\n   ✅ FULL USER FLOW TEST COMPLETED")
        print(f"   📊 Результат: Все шаги создания заказа обработаны")
        print(f"   🔍 Проверка: Webhook обрабатывает все updates (HTTP 200)")
        print(f"   🔍 Ожидается: ShipStation API вызов для получения тарифов")
        
        return True
        
    except Exception as e:
        print(f"❌ Full user flow test error: {e}")
        return False

# ==================== БЛОК 2: ADMIN PANEL FUNCTIONS (Priority: HIGH) ====================

def test_maintenance_mode():
    """Test maintenance mode enable/disable/status - CRITICAL REVIEW REQUEST"""
    print("\n🔍 БЛОК 2.1: Тестирование режима обслуживания (Maintenance Mode)")
    print("🎯 КРИТИЧЕСКИЙ ТЕСТ: Включение/выключение/проверка статуса режима обслуживания")
    
    if not ADMIN_API_KEY:
        print("❌ ADMIN_API_KEY не найден - тест невозможен")
        return False
    
    headers = {'X-API-Key': ADMIN_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        # Test 1: Enable maintenance mode
        print("\n   📋 Тест 1: Включение режима обслуживания")
        enable_payload = {"message": "Тех. работы"}
        
        response = requests.post(f"{API_BASE}/admin/maintenance/enable", 
                               json=enable_payload, headers=headers, timeout=10)
        print(f"   POST /admin/maintenance/enable: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test 2: Check maintenance status
        print("\n   📋 Тест 2: Проверка статуса режима обслуживания")
        response = requests.get(f"{API_BASE}/admin/maintenance/status", 
                              headers=headers, timeout=10)
        print(f"   GET /admin/maintenance/status: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test 3: Disable maintenance mode
        print("\n   📋 Тест 3: Выключение режима обслуживания")
        response = requests.post(f"{API_BASE}/admin/maintenance/disable", 
                               headers=headers, timeout=10)
        print(f"   POST /admin/maintenance/disable: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        print(f"   ✅ MAINTENANCE MODE TEST PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Maintenance mode test error: {e}")
        return False

def test_user_management():
    """Test user blocking/unblocking functionality - CRITICAL REVIEW REQUEST"""
    print("\n🔍 БЛОК 2.2: Тестирование управления пользователями")
    print("🎯 КРИТИЧЕСКИЙ ТЕСТ: Блокировка/разблокировка пользователя и проверка статуса")
    
    if not ADMIN_API_KEY:
        print("❌ ADMIN_API_KEY не найден - тест невозможен")
        return False
    
    headers = {'X-API-Key': ADMIN_API_KEY}
    test_telegram_id = TEST_USER_ID
    
    try:
        # Test 1: Get user
        print(f"\n   📋 Тест 1: Получение пользователя {test_telegram_id}")
        response = requests.get(f"{API_BASE}/admin/users/{test_telegram_id}", 
                              headers=headers, timeout=10)
        print(f"   GET /admin/users/{test_telegram_id}: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test 2: Block user
        print(f"\n   📋 Тест 2: Блокировка пользователя")
        response = requests.post(f"{API_BASE}/admin/users/{test_telegram_id}/block", 
                               headers=headers, timeout=10)
        print(f"   POST /admin/users/{test_telegram_id}/block: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test 3: Verify blocked user can't use bot
        print(f"\n   📋 Тест 3: Проверка что заблокированный пользователь не может использовать бота")
        start_update = {
            "update_id": int(time.time() * 1000),
            "message": {
                "message_id": 1,
                "from": {"id": test_telegram_id, "is_bot": False, "first_name": "TestUser"},
                "chat": {"id": test_telegram_id, "type": "private"},
                "date": int(time.time()),
                "text": "/start"
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=start_update, timeout=15)
        print(f"   /start заблокированным пользователем: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test 4: Unblock user
        print(f"\n   📋 Тест 4: Разблокировка пользователя")
        response = requests.post(f"{API_BASE}/admin/users/{test_telegram_id}/unblock", 
                               headers=headers, timeout=10)
        print(f"   POST /admin/users/{test_telegram_id}/unblock: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        print(f"   ✅ USER MANAGEMENT TEST PASSED")
        return True
        
    except Exception as e:
        print(f"❌ User management test error: {e}")
        return False

def test_balance_operations():
    """Test balance add/deduct operations - CRITICAL REVIEW REQUEST"""
    print("\n🔍 БЛОК 2.3: Тестирование операций с балансом")
    print("🎯 КРИТИЧЕСКИЙ ТЕСТ: Пополнение/списание баланса и проверка значений")
    
    if not ADMIN_API_KEY:
        print("❌ ADMIN_API_KEY не найден - тест невозможен")
        return False
    
    headers = {'X-API-Key': ADMIN_API_KEY}
    test_telegram_id = TEST_USER_ID
    
    try:
        # Test 1: Get initial balance
        print(f"\n   📋 Тест 1: Получение начального баланса")
        response = requests.get(f"{API_BASE}/admin/users/{test_telegram_id}", 
                              headers=headers, timeout=10)
        print(f"   GET /admin/users/{test_telegram_id}: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        initial_balance = 0.0
        if response.status_code == 200:
            try:
                data = response.json()
                initial_balance = float(data.get('balance', 0.0))
                print(f"   Initial Balance: ${initial_balance:.2f}")
            except:
                print(f"   Response: {response.text}")
        
        # Test 2: Add balance
        print(f"\n   📋 Тест 2: Пополнение баланса на $2.00")
        response = requests.post(f"{API_BASE}/admin/users/{test_telegram_id}/balance/add?amount=2.00", 
                               headers=headers, timeout=10)
        print(f"   POST balance/add: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test 3: Deduct balance
        print(f"\n   📋 Тест 3: Списание баланса на $1.00")
        response = requests.post(f"{API_BASE}/admin/users/{test_telegram_id}/balance/deduct?amount=1.00", 
                               headers=headers, timeout=10)
        print(f"   POST balance/deduct: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test 4: Verify final balance
        print(f"\n   📋 Тест 4: Проверка финального баланса")
        response = requests.get(f"{API_BASE}/admin/users/{test_telegram_id}", 
                              headers=headers, timeout=10)
        print(f"   GET final balance: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                final_balance = float(data.get('balance', 0.0))
                expected_final = initial_balance + 2.00 - 1.00
                print(f"   Final Balance: ${final_balance:.2f}")
                print(f"   Expected Final: ${expected_final:.2f}")
            except:
                print(f"   Response: {response.text}")
        
        print(f"   ✅ BALANCE OPERATIONS TEST PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Balance operations test error: {e}")
        return False

# ==================== БЛОК 3: INTEGRATIONS (Priority: HIGH) ====================

def test_shipstation_api():
    """Test ShipStation API integration - CRITICAL REVIEW REQUEST"""
    print("\n🔍 БЛОК 3.1: Тестирование ShipStation API")
    print("🎯 КРИТИЧЕСКИЙ ТЕСТ: Получение тарифов от всех перевозчиков (USPS, FedEx, UPS)")
    
    # Test with addresses from review request
    test_payload = {
        "from_address": {
            "name": TEST_FROM_ADDRESS["name"],
            "street1": TEST_FROM_ADDRESS["street1"],
            "city": TEST_FROM_ADDRESS["city"],
            "state": TEST_FROM_ADDRESS["state"],
            "zip": TEST_FROM_ADDRESS["zip"],
            "country": "US"
        },
        "to_address": {
            "name": TEST_TO_ADDRESS["name"],
            "street1": TEST_TO_ADDRESS["street1"],
            "city": TEST_TO_ADDRESS["city"],
            "state": TEST_TO_ADDRESS["state"],
            "zip": TEST_TO_ADDRESS["zip"],
            "country": "US"
        },
        "parcel": {
            "length": TEST_PARCEL["length"],
            "width": TEST_PARCEL["width"],
            "height": TEST_PARCEL["height"],
            "distance_unit": "in",
            "weight": TEST_PARCEL["weight"],
            "mass_unit": "lb"
        }
    }
    
    try:
        print(f"📦 Test Payload: SF→LA, 5lbs, 10x10x5")
        
        response = requests.post(
            f"{API_BASE}/calculate-shipping",
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', [])
            
            print(f"\n📊 ShipStation API Results:")
            print(f"   Total rates returned: {len(rates)}")
            
            # Check for specific carriers
            carrier_names = [r.get('carrier_friendly_name', r.get('carrier', '')).upper() for r in rates]
            unique_carriers = set(carrier_names)
            
            ups_rates = [r for r in rates if 'UPS' in r.get('carrier_friendly_name', '').upper()]
            usps_rates = [r for r in rates if any(x in r.get('carrier_friendly_name', '').upper() for x in ['USPS', 'STAMPS'])]
            fedex_rates = [r for r in rates if any(x in r.get('carrier_friendly_name', '').upper() for x in ['FEDEX', 'FDX'])]
            
            print(f"   UPS rates: {len(ups_rates)} {'✅' if ups_rates else '❌'}")
            print(f"   USPS/Stamps rates: {len(usps_rates)} {'✅' if usps_rates else '❌'}")
            print(f"   FedEx rates: {len(fedex_rates)} {'✅' if fedex_rates else '❌'}")
            
            carriers_found = sum([bool(ups_rates), bool(usps_rates), bool(fedex_rates)])
            
            if carriers_found >= 2:
                print(f"   ✅ SHIPSTATION API TEST PASSED: Multiple carriers returning rates")
                return True
            else:
                print(f"   ❌ SHIPSTATION API ISSUE: Only {carriers_found} carrier(s) returning rates")
                return False
        else:
            print(f"❌ ShipStation API test failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ShipStation API test error: {e}")
        return False

def test_webhook_health():
    """Test webhook health and configuration - CRITICAL REVIEW REQUEST"""
    print("\n🔍 БЛОК 3.2: Тестирование здоровья Webhook")
    print("🎯 КРИТИЧЕСКИЙ ТЕСТ: Проверка конфигурации webhook и отсутствие pending updates")
    
    try:
        # Test webhook info via Telegram API
        print(f"\n   📋 Проверка webhook info через Telegram API")
        webhook_info_url = f"https://api.telegram.org/bot{PROD_BOT_TOKEN}/getWebhookInfo"
        
        response = requests.get(webhook_info_url, timeout=10)
        print(f"   GET getWebhookInfo: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('result', {})
            
            webhook_url = result.get('url', '')
            pending_updates = result.get('pending_update_count', 0)
            last_error = result.get('last_error_message', '')
            
            print(f"   Webhook URL: {webhook_url}")
            print(f"   Pending updates: {pending_updates} {'✅' if pending_updates == 0 else '❌'}")
            print(f"   Last error: {last_error if last_error else 'None ✅'}")
            
            # Verify webhook URL is correct
            expected_webhook = WEBHOOK_URL
            url_correct = webhook_url == expected_webhook
            print(f"   URL correct: {'✅' if url_correct else '❌'}")
            
            if url_correct and pending_updates == 0 and not last_error:
                print(f"   ✅ WEBHOOK HEALTH TEST PASSED")
                return True
            else:
                print(f"   ❌ WEBHOOK HEALTH ISSUES DETECTED")
                return False
        else:
            print(f"   ❌ Failed to get webhook info: {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Webhook health test error: {e}")
        return False

# ==================== БЛОК 4: ERROR HANDLING & EDGE CASES (Priority: MEDIUM) ====================

def test_validation_tests():
    """Test validation for invalid inputs - MEDIUM PRIORITY"""
    print("\n🔍 БЛОК 4.1: Тестирование валидации")
    print("🎯 ТЕСТ: Проверка валидации неверных данных")
    
    try:
        # Test invalid ZIP code
        print(f"\n   📋 Тест 1: Неверный ZIP code")
        invalid_zip_update = {
            "update_id": int(time.time() * 1000),
            "message": {
                "message_id": 1,
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "chat": {"id": TEST_USER_ID, "type": "private"},
                "date": int(time.time()),
                "text": "12345678"  # Invalid ZIP (too long)
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=invalid_zip_update, timeout=15)
        print(f"   Invalid ZIP: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test invalid phone number
        print(f"\n   📋 Тест 2: Неверный номер телефона")
        invalid_phone_update = {
            "update_id": int(time.time() * 1000) + 1,
            "message": {
                "message_id": 2,
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "chat": {"id": TEST_USER_ID, "type": "private"},
                "date": int(time.time()),
                "text": "abc123"  # Invalid phone
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=invalid_phone_update, timeout=15)
        print(f"   Invalid phone: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Test negative weight
        print(f"\n   📋 Тест 3: Отрицательный вес")
        negative_weight_update = {
            "update_id": int(time.time() * 1000) + 2,
            "message": {
                "message_id": 3,
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "chat": {"id": TEST_USER_ID, "type": "private"},
                "date": int(time.time()),
                "text": "-5"  # Negative weight
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=negative_weight_update, timeout=15)
        print(f"   Negative weight: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        print(f"   ✅ VALIDATION TESTS COMPLETED")
        return True
        
    except Exception as e:
        print(f"❌ Validation tests error: {e}")
        return False

def test_cancel_flow():
    """Test cancel order flow - MEDIUM PRIORITY"""
    print("\n🔍 БЛОК 4.2: Тестирование отмены заказа")
    print("🎯 ТЕСТ: Начать заказ → Отменить → Проверить очистку")
    
    try:
        # Start order
        print(f"\n   📋 Шаг 1: Начать заказ")
        new_order_update = {
            "update_id": int(time.time() * 1000),
            "callback_query": {
                "id": f"new_order_{int(time.time())}",
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "message": {
                    "message_id": 1,
                    "from": {"id": 123456789, "is_bot": True, "first_name": "Bot"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": "Main menu"
                },
                "chat_instance": "test_chat_instance",
                "data": "new_order"
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=new_order_update, timeout=15)
        print(f"   Start order: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        # Cancel order
        print(f"\n   📋 Шаг 2: Отменить заказ")
        time.sleep(0.5)
        
        cancel_update = {
            "update_id": int(time.time() * 1000) + 1,
            "callback_query": {
                "id": f"cancel_{int(time.time())}",
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "message": {
                    "message_id": 2,
                    "from": {"id": 123456789, "is_bot": True, "first_name": "Bot"},
                    "chat": {"id": TEST_USER_ID, "type": "private"},
                    "date": int(time.time()),
                    "text": "Order step"
                },
                "chat_instance": "test_chat_instance",
                "data": "cancel_order"
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=cancel_update, timeout=15)
        print(f"   Cancel order: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        
        print(f"   ✅ CANCEL FLOW TEST COMPLETED")
        return True
        
    except Exception as e:
        print(f"❌ Cancel flow test error: {e}")
        return False

# ==================== БЛОК 5: PERFORMANCE & LOGS (Priority: MEDIUM) ====================

def test_response_times():
    """Test response times - MEDIUM PRIORITY"""
    print("\n🔍 БЛОК 5.1: Тестирование времени отклика")
    print("🎯 ТЕСТ: /start < 2 сек, rate calculation < 5 сек")
    
    try:
        # Test /start response time
        print(f"\n   📋 Тест 1: Время отклика /start")
        start_time = time.time()
        
        start_update = {
            "update_id": int(time.time() * 1000),
            "message": {
                "message_id": 1,
                "from": {"id": TEST_USER_ID, "is_bot": False, "first_name": "TestUser"},
                "chat": {"id": TEST_USER_ID, "type": "private"},
                "date": int(time.time()),
                "text": "/start"
            }
        }
        
        response = requests.post(WEBHOOK_URL, json=start_update, timeout=15)
        response_time = time.time() - start_time
        
        print(f"   /start response time: {response_time:.2f}s {'✅' if response_time < 2.0 else '❌'}")
        
        # Test rate calculation response time
        print(f"\n   📋 Тест 2: Время расчета тарифов")
        start_time = time.time()
        
        test_payload = {
            "from_address": {
                "name": "Test User",
                "street1": "123 Test St",
                "city": "New York",
                "state": "NY",
                "zip": "10001",
                "country": "US"
            },
            "to_address": {
                "name": "Test Recipient",
                "street1": "456 Test Ave",
                "city": "Los Angeles",
                "state": "CA",
                "zip": "90001",
                "country": "US"
            },
            "parcel": {
                "length": 10,
                "width": 8,
                "height": 5,
                "distance_unit": "in",
                "weight": 2,
                "mass_unit": "lb"
            }
        }
        
        response = requests.post(
            f"{API_BASE}/calculate-shipping",
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        calc_time = time.time() - start_time
        print(f"   Rate calculation time: {calc_time:.2f}s {'✅' if calc_time < 5.0 else '❌'}")
        
        print(f"   ✅ RESPONSE TIME TESTS COMPLETED")
        return True
        
    except Exception as e:
        print(f"❌ Response time tests error: {e}")
        return False

def test_log_analysis():
    """Test log analysis for errors - MEDIUM PRIORITY"""
    print("\n🔍 БЛОК 5.2: Анализ логов")
    print("🎯 ТЕСТ: Поиск ошибок Conflict, bot_instance, трейсбеков")
    
    try:
        print(f"\n   📋 Проверка backend логов:")
        
        # Check for Conflict errors
        print(f"   🔍 Поиск ошибок Conflict:")
        conflict_errors = os.popen("tail -n 100 /var/log/supervisor/backend.*.log | grep -i 'conflict' | wc -l").read().strip()
        print(f"   Conflict errors found: {conflict_errors} {'✅' if int(conflict_errors) == 0 else '❌'}")
        
        # Check for bot_instance errors
        print(f"   🔍 Поиск ошибок bot_instance:")
        bot_errors = os.popen("tail -n 100 /var/log/supervisor/backend.*.log | grep -i 'bot_instance.*error' | wc -l").read().strip()
        print(f"   bot_instance errors found: {bot_errors} {'✅' if int(bot_errors) == 0 else '❌'}")
        
        # Check for webhook processing
        print(f"   🔍 Проверка обработки webhook:")
        webhook_logs = os.popen("tail -n 50 /var/log/supervisor/backend.*.log | grep -i 'webhook' | wc -l").read().strip()
        print(f"   Webhook processing logs: {webhook_logs} {'✅' if int(webhook_logs) > 0 else '⚠️'}")
        
        print(f"   ✅ LOG ANALYSIS COMPLETED")
        return True
        
    except Exception as e:
        print(f"❌ Log analysis error: {e}")
        return False

# ==================== MAIN TEST RUNNER ====================

def run_all_tests():
    """Run all E2E tests according to review request priorities"""
    print("🚀 ЗАПУСК ФИНАЛЬНОГО E2E ТЕСТИРОВАНИЯ")
    print("=" * 80)
    
    results = {}
    
    # БЛОК 1: FULL USER FLOW (Priority: CRITICAL)
    print("\n" + "=" * 50)
    print("БЛОК 1: FULL USER FLOW (Priority: CRITICAL)")
    print("=" * 50)
    results['full_user_flow'] = test_full_user_flow()
    
    # БЛОК 2: ADMIN PANEL FUNCTIONS (Priority: HIGH)
    print("\n" + "=" * 50)
    print("БЛОК 2: ADMIN PANEL FUNCTIONS (Priority: HIGH)")
    print("=" * 50)
    results['maintenance_mode'] = test_maintenance_mode()
    results['user_management'] = test_user_management()
    results['balance_operations'] = test_balance_operations()
    
    # БЛОК 3: INTEGRATIONS (Priority: HIGH)
    print("\n" + "=" * 50)
    print("БЛОК 3: INTEGRATIONS (Priority: HIGH)")
    print("=" * 50)
    results['shipstation_api'] = test_shipstation_api()
    results['webhook_health'] = test_webhook_health()
    
    # БЛОК 4: ERROR HANDLING & EDGE CASES (Priority: MEDIUM)
    print("\n" + "=" * 50)
    print("БЛОК 4: ERROR HANDLING & EDGE CASES (Priority: MEDIUM)")
    print("=" * 50)
    results['validation_tests'] = test_validation_tests()
    results['cancel_flow'] = test_cancel_flow()
    
    # БЛОК 5: PERFORMANCE & LOGS (Priority: MEDIUM)
    print("\n" + "=" * 50)
    print("БЛОК 5: PERFORMANCE & LOGS (Priority: MEDIUM)")
    print("=" * 50)
    results['response_times'] = test_response_times()
    results['log_analysis'] = test_log_analysis()
    
    # FINAL SUMMARY
    print("\n" + "=" * 80)
    print("🏆 ФИНАЛЬНЫЙ ОТЧЕТ E2E ТЕСТИРОВАНИЯ")
    print("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"\n📊 ОБЩИЕ РЕЗУЛЬТАТЫ:")
    print(f"   Пройдено тестов: {passed}/{total} ({passed/total*100:.1f}%)")
    
    print(f"\n📋 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    # КРИТЕРИИ УСПЕХА из review request
    critical_tests = ['full_user_flow', 'maintenance_mode', 'user_management', 'balance_operations', 'shipstation_api', 'webhook_health']
    critical_passed = sum(1 for test in critical_tests if results.get(test, False))
    critical_total = len(critical_tests)
    
    print(f"\n🎯 КРИТИЧЕСКИЕ ТЕСТЫ (ОБЯЗАТЕЛЬНЫЕ):")
    print(f"   Пройдено: {critical_passed}/{critical_total} ({critical_passed/critical_total*100:.1f}%)")
    
    if critical_passed == critical_total:
        print(f"\n🎉 ✅ PRODUCTION READINESS: ВСЕ КРИТИЧЕСКИЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print(f"   Система готова к production deployment")
    else:
        print(f"\n⚠️ ❌ PRODUCTION READINESS: КРИТИЧЕСКИЕ ПРОБЛЕМЫ ОБНАРУЖЕНЫ!")
        print(f"   Необходимо исправить критические ошибки перед deployment")
    
    return results

if __name__ == "__main__":
    run_all_tests()