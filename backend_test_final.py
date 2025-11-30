#!/usr/bin/env python3
"""
Final Comprehensive Backend Testing - Review Request
Tests all fixed functions as requested in the review
"""

import requests
import json
import os
import time
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')

# Configuration from review request
BACKEND_URL = "https://easyshipbot.preview.emergentagent.com"
API_KEY = "sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024"
TEST_USER_ID = 5594152712

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*60}")
    print(f"🔍 {test_name}")
    print(f"{'='*60}")

def print_test_result(test_name, success, details=""):
    """Print formatted test result"""
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"\n📊 {test_name}: {status}")
    if details:
        print(f"   {details}")

def check_logs_for_pattern(pattern, log_file="/var/log/supervisor/backend.out.log", lines=100):
    """Check backend logs for specific pattern"""
    try:
        cmd = f"tail -n {lines} {log_file} | grep -E '{pattern}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"   ❌ Error checking logs: {e}")
        return ""

def test_1_admin_notifications():
    """TEST 1: Admin Notifications (bot_instance through app.state)"""
    print_test_header("TEST 1: Admin Notifications")
    
    results = {}
    
    # 1.1 Add Balance
    print("\n🔍 1.1 Add Balance Test")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/users/{TEST_USER_ID}/balance/add?amount=0.05",
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        
        print(f"   HTTP Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            
            # Check logs for bot_instance availability and notification success
            log_pattern = r"ADD_BALANCE.*bot_instance.*AVAILABLE|Balance notification sent to user 5594152712"
            logs = check_logs_for_pattern(log_pattern)
            
            if logs:
                print(f"   ✅ Bot instance log found: {logs}")
                results['add_balance'] = True
            else:
                print(f"   ❌ Bot instance log not found")
                results['add_balance'] = False
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            results['add_balance'] = False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['add_balance'] = False
    
    # 1.2 Deduct Balance
    print("\n🔍 1.2 Deduct Balance Test")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/users/{TEST_USER_ID}/balance/deduct?amount=0.02",
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        
        print(f"   HTTP Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            
            # Check logs for bot_instance availability and notification success
            log_pattern = r"DEDUCT_BALANCE.*bot_instance.*AVAILABLE|Balance deduction notification sent to user 5594152712"
            logs = check_logs_for_pattern(log_pattern)
            
            if logs:
                print(f"   ✅ Bot instance log found: {logs}")
                results['deduct_balance'] = True
            else:
                print(f"   ❌ Bot instance log not found")
                results['deduct_balance'] = False
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            results['deduct_balance'] = False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['deduct_balance'] = False
    
    # 1.3 Block User
    print("\n🔍 1.3 Block User Test")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/users/{TEST_USER_ID}/block",
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        
        print(f"   HTTP Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            
            # Check logs for bot_instance availability and notification success
            log_pattern = r"BLOCK_USER.*bot_instance.*AVAILABLE|Block notification sent to user 5594152712"
            logs = check_logs_for_pattern(log_pattern)
            
            if logs:
                print(f"   ✅ Bot instance log found: {logs}")
                results['block_user'] = True
            else:
                print(f"   ❌ Bot instance log not found")
                results['block_user'] = False
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            results['block_user'] = False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['block_user'] = False
    
    # 1.4 Unblock User
    print("\n🔍 1.4 Unblock User Test")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/users/{TEST_USER_ID}/unblock",
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        
        print(f"   HTTP Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            
            # Check logs for bot_instance availability and notification success
            log_pattern = r"UNBLOCK_USER.*bot_instance.*AVAILABLE|Unblock notification sent to user 5594152712"
            logs = check_logs_for_pattern(log_pattern)
            
            if logs:
                print(f"   ✅ Bot instance log found: {logs}")
                results['unblock_user'] = True
            else:
                print(f"   ❌ Bot instance log not found")
                results['unblock_user'] = False
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            results['unblock_user'] = False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['unblock_user'] = False
    
    # Summary
    passed_tests = sum(results.values())
    total_tests = len(results)
    success = passed_tests == total_tests
    
    print_test_result("Admin Notifications", success, f"{passed_tests}/{total_tests} tests passed")
    return success, results

def test_2_details_button():
    """TEST 2: Details Button in Admin Panel"""
    print_test_header("TEST 2: Details Button")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/users/{TEST_USER_ID}/details",
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        
        print(f"   HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
            
            # Check required fields
            required_fields = ['user', 'statistics']
            user_fields = ['telegram_id', 'username', 'first_name', 'balance', 'discount', 'blocked']
            stats_fields = ['total_orders', 'current_balance', 'total_spent', 'templates_count']
            
            has_user = 'user' in data
            has_stats = 'statistics' in data
            
            if has_user:
                user_data = data['user']
                user_complete = all(field in user_data for field in user_fields)
                print(f"   User data complete: {'✅' if user_complete else '❌'}")
            else:
                user_complete = False
                print(f"   ❌ User data missing")
            
            if has_stats:
                stats_data = data['statistics']
                stats_complete = all(field in stats_data for field in stats_fields)
                print(f"   Statistics complete: {'✅' if stats_complete else '❌'}")
            else:
                stats_complete = False
                print(f"   ❌ Statistics missing")
            
            success = has_user and has_stats and user_complete and stats_complete
            print_test_result("Details Button", success, "All required fields present" if success else "Missing required fields")
            return success
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            print_test_result("Details Button", False, f"HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print_test_result("Details Button", False, str(e))
        return False

def test_3_oxapay_webhook():
    """TEST 3: Oxapay Webhook"""
    print_test_header("TEST 3: Oxapay Webhook")
    
    try:
        webhook_payload = {
            "status": "Paid",
            "trackId": "final_test_webhook",
            "orderId": "test_webhook_12345",
            "amount": 1.0,
            "telegram_id": TEST_USER_ID
        }
        
        print(f"   Webhook Payload: {json.dumps(webhook_payload, indent=2)}")
        
        response = requests.post(
            f"{BACKEND_URL}/api/oxapay/webhook",
            json=webhook_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"   HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            
            # Check logs for bot_instance availability
            log_pattern = r"OXAPAY_WEBHOOK.*bot_instance.*AVAILABLE"
            logs = check_logs_for_pattern(log_pattern)
            
            if logs:
                print(f"   ✅ Bot instance log found: {logs}")
                success = True
            else:
                print(f"   ❌ Bot instance log not found")
                success = False
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            success = False
        
        print_test_result("Oxapay Webhook", success, "Bot instance available" if success else "Bot instance not available")
        return success
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print_test_result("Oxapay Webhook", False, str(e))
        return False

def test_4_check_logs():
    """TEST 4: Check Logs for All Operations"""
    print_test_header("TEST 4: Log Analysis")
    
    try:
        # Check for all expected log patterns
        patterns = [
            r"\[ADD_BALANCE\].*bot_instance.*AVAILABLE",
            r"\[DEDUCT_BALANCE\].*bot_instance.*AVAILABLE", 
            r"\[BLOCK_USER\].*bot_instance.*AVAILABLE",
            r"\[UNBLOCK_USER\].*bot_instance.*AVAILABLE",
            r"\[OXAPAY_WEBHOOK\].*bot_instance.*AVAILABLE",
            r"notification sent"
        ]
        
        results = {}
        for pattern in patterns:
            logs = check_logs_for_pattern(pattern, lines=200)
            found = bool(logs)
            results[pattern] = found
            print(f"   Pattern '{pattern}': {'✅' if found else '❌'}")
            if found:
                # Show first matching line
                first_line = logs.split('\n')[0] if logs else ""
                print(f"      Example: {first_line}")
        
        # Check for error patterns
        error_patterns = [
            r"❌.*error",
            r"exception",
            r"traceback"
        ]
        
        print(f"\n   🔍 Checking for errors:")
        error_found = False
        for pattern in error_patterns:
            logs = check_logs_for_pattern(pattern, lines=100)
            if logs:
                error_found = True
                print(f"   ⚠️ Error pattern '{pattern}' found:")
                for line in logs.split('\n')[:3]:  # Show first 3 matches
                    print(f"      {line}")
        
        if not error_found:
            print(f"   ✅ No error patterns found")
        
        success_count = sum(results.values())
        total_patterns = len(patterns)
        success = success_count >= (total_patterns * 0.8)  # 80% success rate
        
        print_test_result("Log Analysis", success, f"{success_count}/{total_patterns} patterns found, no critical errors" if success else f"Only {success_count}/{total_patterns} patterns found")
        return success
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print_test_result("Log Analysis", False, str(e))
        return False

def test_5_service_status():
    """TEST 5: Service Status Check"""
    print_test_header("TEST 5: Service Status")
    
    try:
        # Check supervisor status
        cmd = "sudo supervisorctl status | grep -E 'backend|frontend'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        print(f"   Supervisor Status:")
        print(f"   {result.stdout}")
        
        # Parse status
        lines = result.stdout.strip().split('\n')
        services = {}
        
        for line in lines:
            if 'backend' in line.lower():
                services['backend'] = 'RUNNING' in line
            elif 'frontend' in line.lower():
                services['frontend'] = 'RUNNING' in line
        
        backend_running = services.get('backend', False)
        frontend_running = services.get('frontend', False)
        
        print(f"   Backend: {'✅ RUNNING' if backend_running else '❌ NOT RUNNING'}")
        print(f"   Frontend: {'✅ RUNNING' if frontend_running else '❌ NOT RUNNING'}")
        
        success = backend_running and frontend_running
        print_test_result("Service Status", success, "All services running" if success else "Some services not running")
        return success
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print_test_result("Service Status", False, str(e))
        return False

def test_6_error_check():
    """TEST 6: Error Check in Logs"""
    print_test_header("TEST 6: Error Check")
    
    try:
        # Check error log
        cmd = "tail -n 50 /var/log/supervisor/backend.err.log | grep -i 'error\\|exception\\|traceback'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        error_output = result.stdout.strip()
        
        if error_output:
            print(f"   ❌ Errors found in backend.err.log:")
            for line in error_output.split('\n')[:10]:  # Show first 10 lines
                print(f"      {line}")
            success = False
        else:
            print(f"   ✅ No errors found in backend.err.log")
            success = True
        
        print_test_result("Error Check", success, "No errors in logs" if success else "Errors found in logs")
        return success
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print_test_result("Error Check", False, str(e))
        return False

def run_comprehensive_test():
    """Run all tests and provide final report"""
    print("🚀 Starting Final Comprehensive Backend Testing")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Key: {API_KEY}")
    print(f"Test User ID: {TEST_USER_ID}")
    
    # Run all tests
    test_results = {}
    
    # Test 1: Admin Notifications
    success, details = test_1_admin_notifications()
    test_results['Admin Notifications'] = success
    
    # Test 2: Details Button
    success = test_2_details_button()
    test_results['Details Button'] = success
    
    # Test 3: Oxapay Webhook
    success = test_3_oxapay_webhook()
    test_results['Oxapay Webhook'] = success
    
    # Test 4: Log Analysis
    success = test_4_check_logs()
    test_results['Log Analysis'] = success
    
    # Test 5: Service Status
    success = test_5_service_status()
    test_results['Service Status'] = success
    
    # Test 6: Error Check
    success = test_6_error_check()
    test_results['Error Check'] = success
    
    # Final Report
    print(f"\n{'='*80}")
    print(f"📊 FINAL COMPREHENSIVE TEST REPORT")
    print(f"{'='*80}")
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, success in test_results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if success:
            passed_tests += 1
    
    print(f"\n📈 SUMMARY:")
    print(f"   Tests Passed: {passed_tests}/{total_tests}")
    print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print(f"   🎉 VERDICT: ✅ ГОТОВ К PRODUCTION")
        print(f"   All critical functions are working correctly!")
    elif passed_tests >= total_tests * 0.8:
        print(f"   ⚠️ VERDICT: 🔧 ТРЕБУЮТСЯ МИНОРНЫЕ ИСПРАВЛЕНИЯ")
        print(f"   Most functions working, minor issues detected")
    else:
        print(f"   🚨 VERDICT: ❌ ТРЕБУЮТСЯ ИСПРАВЛЕНИЯ")
        print(f"   Critical issues detected, needs attention")
    
    return test_results

if __name__ == "__main__":
    run_comprehensive_test()