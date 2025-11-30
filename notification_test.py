#!/usr/bin/env python3
"""
Notification System Test Suite - Final Testing After bot_instance Fix
Tests the notification system after fixing bot_instance availability in app.state
"""

import requests
import json
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://easyshipbot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

# Load admin API key
load_dotenv('/app/backend/.env')
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024')

# Test user ID from review request
TEST_USER_ID = 5594152712

def check_backend_logs(search_terms, description):
    """Check backend logs for specific terms"""
    print(f"   🔍 Checking logs for {description}...")
    try:
        # Check output logs
        cmd = f"tail -n 100 /var/log/supervisor/backend.out.log | grep -E \"{'|'.join(search_terms)}\""
        result = os.popen(cmd).read()
        
        if result.strip():
            print(f"   ✅ Found {description} in logs:")
            for line in result.strip().split('\n')[-5:]:  # Show last 5 matches
                print(f"      {line}")
            return True
        else:
            print(f"   ❌ No {description} found in logs")
            return False
    except Exception as e:
        print(f"   ❌ Error checking logs: {e}")
        return False

def test_balance_add_notification():
    """TEST 1: Balance Add Notification"""
    print("\n🔍 TEST 1: Balance Add Notification")
    print("🎯 EXPECTED: HTTP 200 OK, success=true, new_balance updated, bot_instance=AVAILABLE, notification sent")
    
    try:
        # Make the API request
        url = f"{BACKEND_URL}/api/users/{TEST_USER_ID}/balance/add"
        params = {"amount": "2.00"}
        headers = {"x-api-key": ADMIN_API_KEY}
        
        print(f"   📤 POST {url}")
        print(f"   📤 Params: {params}")
        print(f"   📤 Headers: x-api-key: {ADMIN_API_KEY[:20]}...")
        
        response = requests.post(url, params=params, headers=headers, timeout=15)
        
        print(f"   📥 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   📥 Response: {json.dumps(data, indent=2)}")
            
            # Check response structure
            success = data.get('success', False)
            new_balance = data.get('new_balance')
            
            print(f"   ✅ Success: {success}")
            print(f"   ✅ New Balance: {new_balance}")
            
            # Check logs for bot_instance and notification
            log_checks = [
                (["ADD_BALANCE", "bot_instance from app.state: AVAILABLE"], "bot_instance availability"),
                (["Balance notification sent to user", TEST_USER_ID], "notification sent confirmation")
            ]
            
            log_results = []
            for terms, desc in log_checks:
                result = check_backend_logs([str(term) for term in terms], desc)
                log_results.append(result)
            
            # Overall success
            api_success = success and new_balance is not None
            logs_success = all(log_results)
            
            print(f"\n   📊 TEST 1 RESULTS:")
            print(f"   API Response: {'✅' if api_success else '❌'}")
            print(f"   Log Verification: {'✅' if logs_success else '❌'}")
            print(f"   Overall: {'✅ PASS' if api_success and logs_success else '❌ FAIL'}")
            
            return api_success and logs_success
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Balance add test error: {e}")
        return False

def test_balance_deduct_notification():
    """TEST 2: Balance Deduct Notification"""
    print("\n🔍 TEST 2: Balance Deduct Notification")
    print("🎯 EXPECTED: HTTP 200 OK, success=true, bot_instance=AVAILABLE, notification sent")
    
    try:
        # Make the API request
        url = f"{BACKEND_URL}/api/users/{TEST_USER_ID}/balance/deduct"
        params = {"amount": "1.00"}
        headers = {"x-api-key": ADMIN_API_KEY}
        
        print(f"   📤 POST {url}")
        print(f"   📤 Params: {params}")
        print(f"   📤 Headers: x-api-key: {ADMIN_API_KEY[:20]}...")
        
        response = requests.post(url, params=params, headers=headers, timeout=15)
        
        print(f"   📥 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   📥 Response: {json.dumps(data, indent=2)}")
            
            # Check response structure
            success = data.get('success', False)
            new_balance = data.get('new_balance')
            
            print(f"   ✅ Success: {success}")
            print(f"   ✅ New Balance: {new_balance}")
            
            # Check logs for bot_instance and notification
            log_checks = [
                (["DEDUCT_BALANCE", "Attempting to send notification", "bot_instance=AVAILABLE"], "bot_instance availability"),
                (["Balance deduction notification sent to user"], "notification sent confirmation")
            ]
            
            log_results = []
            for terms, desc in log_checks:
                result = check_backend_logs([str(term) for term in terms], desc)
                log_results.append(result)
            
            # Overall success
            api_success = success and new_balance is not None
            logs_success = all(log_results)
            
            print(f"\n   📊 TEST 2 RESULTS:")
            print(f"   API Response: {'✅' if api_success else '❌'}")
            print(f"   Log Verification: {'✅' if logs_success else '❌'}")
            print(f"   Overall: {'✅ PASS' if api_success and logs_success else '❌ FAIL'}")
            
            return api_success and logs_success
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Balance deduct test error: {e}")
        return False

def test_block_user_notification():
    """TEST 3: Block User Notification"""
    print("\n🔍 TEST 3: Block User Notification")
    print("🎯 EXPECTED: HTTP 200 OK, bot_instance=AVAILABLE, block notification sent")
    
    try:
        # Make the API request
        url = f"{BACKEND_URL}/api/users/{TEST_USER_ID}/block"
        headers = {"x-api-key": ADMIN_API_KEY}
        
        print(f"   📤 POST {url}")
        print(f"   📤 Headers: x-api-key: {ADMIN_API_KEY[:20]}...")
        
        response = requests.post(url, headers=headers, timeout=15)
        
        print(f"   📥 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   📥 Response: {json.dumps(data, indent=2)}")
            
            # Check logs for bot_instance and notification
            log_checks = [
                (["BLOCK_USER", "bot_instance=AVAILABLE"], "bot_instance availability"),
                (["Block notification sent to user"], "notification sent confirmation")
            ]
            
            log_results = []
            for terms, desc in log_checks:
                result = check_backend_logs([str(term) for term in terms], desc)
                log_results.append(result)
            
            # Overall success
            api_success = response.status_code == 200
            logs_success = all(log_results)
            
            print(f"\n   📊 TEST 3 RESULTS:")
            print(f"   API Response: {'✅' if api_success else '❌'}")
            print(f"   Log Verification: {'✅' if logs_success else '❌'}")
            print(f"   Overall: {'✅ PASS' if api_success and logs_success else '❌ FAIL'}")
            
            return api_success and logs_success
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Block user test error: {e}")
        return False

def test_unblock_user_notification():
    """TEST 4: Unblock User Notification"""
    print("\n🔍 TEST 4: Unblock User Notification")
    print("🎯 EXPECTED: HTTP 200 OK, bot_instance=AVAILABLE, unblock notification sent")
    
    try:
        # Make the API request
        url = f"{BACKEND_URL}/api/users/{TEST_USER_ID}/unblock"
        headers = {"x-api-key": ADMIN_API_KEY}
        
        print(f"   📤 POST {url}")
        print(f"   📤 Headers: x-api-key: {ADMIN_API_KEY[:20]}...")
        
        response = requests.post(url, headers=headers, timeout=15)
        
        print(f"   📥 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   📥 Response: {json.dumps(data, indent=2)}")
            
            # Check logs for bot_instance and notification
            log_checks = [
                (["UNBLOCK_USER", "bot_instance=AVAILABLE"], "bot_instance availability"),
                (["Unblock notification sent to user"], "notification sent confirmation")
            ]
            
            log_results = []
            for terms, desc in log_checks:
                result = check_backend_logs([str(term) for term in terms], desc)
                log_results.append(result)
            
            # Overall success
            api_success = response.status_code == 200
            logs_success = all(log_results)
            
            print(f"\n   📊 TEST 4 RESULTS:")
            print(f"   API Response: {'✅' if api_success else '❌'}")
            print(f"   Log Verification: {'✅' if logs_success else '❌'}")
            print(f"   Overall: {'✅ PASS' if api_success and logs_success else '❌ FAIL'}")
            
            return api_success and logs_success
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Unblock user test error: {e}")
        return False

def test_oxapay_webhook_notification():
    """TEST 5: Oxapay Webhook Notification"""
    print("\n🔍 TEST 5: Oxapay Webhook Notification")
    print("🎯 EXPECTED: HTTP 200 OK, bot_instance=AVAILABLE, webhook processed successfully")
    
    try:
        # Make the webhook request
        url = f"{BACKEND_URL}/api/oxapay/webhook"
        payload = {
            "status": "Paid",
            "trackId": "final_test_123",
            "orderId": "test_order_final",
            "amount": 5.0,
            "telegram_id": TEST_USER_ID
        }
        headers = {"Content-Type": "application/json"}
        
        print(f"   📤 POST {url}")
        print(f"   📤 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        print(f"   📥 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   📥 Response: {json.dumps(data, indent=2)}")
            except:
                print(f"   📥 Response: {response.text}")
            
            # Check logs for bot_instance and webhook processing
            log_checks = [
                (["OXAPAY_WEBHOOK", "bot_instance from app.state: AVAILABLE"], "bot_instance availability"),
                (["OXAPAY_WEBHOOK", "Webhook processed"], "webhook processing confirmation")
            ]
            
            log_results = []
            for terms, desc in log_checks:
                result = check_backend_logs([str(term) for term in terms], desc)
                log_results.append(result)
            
            # Overall success
            api_success = response.status_code == 200
            logs_success = all(log_results)
            
            print(f"\n   📊 TEST 5 RESULTS:")
            print(f"   API Response: {'✅' if api_success else '❌'}")
            print(f"   Log Verification: {'✅' if logs_success else '❌'}")
            print(f"   Overall: {'✅ PASS' if api_success and logs_success else '❌ FAIL'}")
            
            return api_success and logs_success
        else:
            print(f"   ❌ Webhook request failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Oxapay webhook test error: {e}")
        return False

def check_error_logs():
    """Check for any errors in backend logs"""
    print("\n🔍 Checking Backend Error Logs...")
    try:
        # Check error logs
        result = os.popen("tail -n 50 /var/log/supervisor/backend.err.log | grep -i 'error\\|exception'").read()
        if result.strip():
            print("   ⚠️ Recent errors found:")
            for line in result.strip().split('\n')[-10:]:  # Show last 10 error lines
                print(f"      {line}")
            return False
        else:
            print("   ✅ No recent errors in backend logs")
            return True
    except Exception as e:
        print(f"   ❌ Error checking logs: {e}")
        return False

def main():
    """Run all notification system tests"""
    print("=" * 80)
    print("🔔 NOTIFICATION SYSTEM FINAL TESTING")
    print("=" * 80)
    print("🎯 Testing notification system after bot_instance fix")
    print(f"📍 Backend URL: {BACKEND_URL}")
    print(f"👤 Test User ID: {TEST_USER_ID}")
    print(f"🔑 Admin API Key: {ADMIN_API_KEY[:20]}...")
    print("=" * 80)
    
    # Run all tests
    test_results = []
    
    test_results.append(("Balance Add Notification", test_balance_add_notification()))
    test_results.append(("Balance Deduct Notification", test_balance_deduct_notification()))
    test_results.append(("Block User Notification", test_block_user_notification()))
    test_results.append(("Unblock User Notification", test_unblock_user_notification()))
    test_results.append(("Oxapay Webhook Notification", test_oxapay_webhook_notification()))
    
    # Check for errors
    no_errors = check_error_logs()
    
    # Final summary
    print("\n" + "=" * 80)
    print("📊 FINAL TEST RESULTS")
    print("=" * 80)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed_tests += 1
    
    print(f"\n   Error Logs Clean: {'✅ PASS' if no_errors else '❌ FAIL'}")
    
    success_rate = (passed_tests / total_tests) * 100
    print(f"\n📈 SUCCESS RATE: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
    
    if passed_tests == total_tests and no_errors:
        print("🎉 ALL TESTS PASSED - NOTIFICATION SYSTEM WORKING!")
        return True
    else:
        print("❌ SOME TESTS FAILED - NOTIFICATION SYSTEM NEEDS ATTENTION")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)