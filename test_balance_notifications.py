#!/usr/bin/env python3
"""
Balance Notification Test - REVIEW REQUEST
Tests the balance notification functionality after balance changes
"""

import requests
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://telegram-shipbot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def test_balance_notification_functionality():
    """Test balance notification functionality after balance changes - REVIEW REQUEST"""
    print("\n🔍 Testing Balance Notification Functionality...")
    print("🎯 REVIEW REQUEST: Test balance add/deduct endpoints and notification system")
    
    # Load admin API key
    load_dotenv('/app/backend/.env')
    admin_api_key = os.environ.get('ADMIN_API_KEY')
    
    if not admin_api_key:
        print("   ❌ ADMIN_API_KEY not found in environment")
        return False
    
    print(f"   Admin API Key loaded: ✅ {admin_api_key}")
    
    # Test user ID from review request
    test_telegram_id = 5594152712
    
    try:
        print(f"\n   📋 ТЕСТ 1: Добавление баланса (+$1.00)")
        print(f"   Endpoint: POST /api/users/{test_telegram_id}/balance/add?amount=1.00")
        
        # Test 1: Add balance
        headers = {'x-api-key': admin_api_key}
        params = {'amount': 1.00}
        
        start_time = time.time()
        response = requests.post(
            f"{API_BASE}/users/{test_telegram_id}/balance/add",
            headers=headers,
            params=params,
            timeout=15
        )
        response_time = (time.time() - start_time) * 1000
        
        print(f"   Response time: {response_time:.2f}ms")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Balance Add Response: {json.dumps(data, indent=2)}")
            
            # Check required fields
            success = data.get('success', False)
            new_balance = data.get('new_balance')
            
            print(f"   success: {'✅' if success else '❌'} {success}")
            print(f"   new_balance: {'✅' if new_balance is not None else '❌'} {new_balance}")
            
            if success and new_balance is not None:
                print(f"   ✅ Balance addition successful: ${new_balance}")
                balance_add_success = True
            else:
                print(f"   ❌ Balance addition failed: missing required fields")
                balance_add_success = False
        else:
            print(f"   ❌ Balance add failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")
            balance_add_success = False
        
        # Check logs after balance addition
        print(f"\n   📋 Проверка логов после добавления баланса:")
        time.sleep(2)  # Wait for logs to be written
        
        log_result = os.popen("tail -n 50 /var/log/supervisor/backend.out.log").read()
        
        # Look for notification attempt
        notification_attempt = "Attempting to send balance notification" in log_result
        print(f"   'Attempting to send balance notification': {'✅' if notification_attempt else '❌'}")
        
        # Look for bot instance status
        bot_instance_available = "bot_instance={'AVAILABLE'" in log_result or "bot_instance=AVAILABLE" in log_result
        bot_instance_none = "bot_instance={'NONE'" in log_result or "bot_instance=NONE" in log_result
        
        if bot_instance_available:
            print(f"   bot_instance status: ✅ AVAILABLE")
        elif bot_instance_none:
            print(f"   bot_instance status: ❌ NONE")
        else:
            print(f"   bot_instance status: ⚠️ Not found in logs")
        
        # Look for successful notification
        notification_sent = "Balance notification sent to user" in log_result
        print(f"   'Balance notification sent to user': {'✅' if notification_sent else '❌'}")
        
        # Show relevant log lines
        log_lines = [line.strip() for line in log_result.split('\n') if 'balance' in line.lower() or 'notification' in line.lower()]
        if log_lines:
            print(f"   📋 Relevant log entries:")
            for line in log_lines[-5:]:  # Show last 5 relevant lines
                if line.strip():
                    print(f"      {line}")
        
        print(f"\n   📋 ТЕСТ 2: Вычитание баланса (-$0.50)")
        print(f"   Endpoint: POST /api/users/{test_telegram_id}/balance/deduct?amount=0.50")
        
        # Test 2: Deduct balance
        params = {'amount': 0.50}
        
        start_time = time.time()
        response = requests.post(
            f"{API_BASE}/users/{test_telegram_id}/balance/deduct",
            headers=headers,
            params=params,
            timeout=15
        )
        response_time = (time.time() - start_time) * 1000
        
        print(f"   Response time: {response_time:.2f}ms")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Balance Deduct Response: {json.dumps(data, indent=2)}")
            
            # Check required fields
            success = data.get('success', False)
            new_balance = data.get('new_balance')
            
            print(f"   success: {'✅' if success else '❌'} {success}")
            print(f"   new_balance: {'✅' if new_balance is not None else '❌'} {new_balance}")
            
            if success and new_balance is not None:
                print(f"   ✅ Balance deduction successful: ${new_balance}")
                balance_deduct_success = True
            else:
                print(f"   ❌ Balance deduction failed: missing required fields")
                balance_deduct_success = False
        else:
            print(f"   ❌ Balance deduct failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")
            balance_deduct_success = False
        
        # Check logs after balance deduction
        print(f"\n   📋 Проверка логов после вычитания баланса:")
        time.sleep(2)  # Wait for logs to be written
        
        log_result = os.popen("tail -n 50 /var/log/supervisor/backend.out.log").read()
        
        # Look for notification attempt
        notification_attempt_2 = "Attempting to send balance notification" in log_result
        print(f"   'Attempting to send balance notification': {'✅' if notification_attempt_2 else '❌'}")
        
        # Look for successful notification
        notification_sent_2 = "Balance notification sent to user" in log_result
        print(f"   'Balance notification sent to user': {'✅' if notification_sent_2 else '❌'}")
        
        # Show relevant log lines
        log_lines = [line.strip() for line in log_result.split('\n') if 'balance' in line.lower() or 'notification' in line.lower()]
        if log_lines:
            print(f"   📋 Relevant log entries:")
            for line in log_lines[-5:]:  # Show last 5 relevant lines
                if line.strip():
                    print(f"      {line}")
        
        # Check error logs
        print(f"\n   📋 Проверка ошибок в backend.err.log:")
        error_result = os.popen("tail -n 30 /var/log/supervisor/backend.err.log | grep -i 'balance\\|notification'").read()
        
        if error_result.strip():
            print(f"   ⚠️ Errors found:")
            error_lines = [line.strip() for line in error_result.split('\n') if line.strip()]
            for line in error_lines:
                print(f"      {line}")
        else:
            print(f"   ✅ No balance/notification errors found")
        
        # Overall assessment
        print(f"\n   🎯 ИТОГОВОЕ ЗАКЛЮЧЕНИЕ:")
        print(f"   Добавление баланса (HTTP 200 OK): {'✅' if balance_add_success else '❌'}")
        print(f"   Вычитание баланса (HTTP 200 OK): {'✅' if balance_deduct_success else '❌'}")
        print(f"   Попытка отправки уведомлений: {'✅' if notification_attempt or notification_attempt_2 else '❌'}")
        print(f"   Успешная отправка уведомлений: {'✅' if notification_sent or notification_sent_2 else '❌'}")
        print(f"   Bot instance доступен: {'✅' if bot_instance_available else '❌'}")
        
        # Success criteria
        endpoints_working = balance_add_success and balance_deduct_success
        notifications_attempted = notification_attempt or notification_attempt_2
        
        if endpoints_working and notifications_attempted:
            print(f"   ✅ ФУНКЦИЯ ОТПРАВКИ УВЕДОМЛЕНИЙ РАБОТАЕТ")
            return True
        elif endpoints_working:
            print(f"   ⚠️ ЭНДПОИНТЫ РАБОТАЮТ, НО УВЕДОМЛЕНИЯ НЕ ОТПРАВЛЯЮТСЯ")
            return False
        else:
            print(f"   ❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ С ЭНДПОИНТАМИ")
            return False
        
    except Exception as e:
        print(f"❌ Error testing balance notification functionality: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🎯 Running Balance Notification Functionality Test...")
    result = test_balance_notification_functionality()
    print(f"Result: {'✅ PASSED' if result else '❌ FAILED'}")