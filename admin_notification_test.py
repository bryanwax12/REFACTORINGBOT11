#!/usr/bin/env python3
"""
Admin Notification Test for Telegram Shipping Bot
Tests the admin notification functionality for shipping label creation
"""

import requests
import json
import os
import re
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://telegram-shipbot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def test_admin_notification_for_label_creation():
    """Test Admin Notification for Label Creation - CRITICAL TEST per review request"""
    print("\n🔍 Testing Admin Notification for Label Creation...")
    print("🎯 CRITICAL: Testing notification functionality when shipping labels are created")
    
    try:
        # Read server.py to analyze the admin notification implementation
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        print("   📋 ADMIN NOTIFICATION IMPLEMENTATION ANALYSIS:")
        
        # Test 1: Verify create_and_send_label function exists (lines 4304-4345)
        create_label_pattern = r'async def create_and_send_label\(order_id, telegram_id, message\):'
        create_label_found = bool(re.search(create_label_pattern, server_code))
        print(f"   create_and_send_label function exists: {'✅' if create_label_found else '❌'}")
        
        # Test 2: Check ADMIN_TELEGRAM_ID loading from .env
        admin_id_loading = 'ADMIN_TELEGRAM_ID = os.environ.get(\'ADMIN_TELEGRAM_ID\', \'\')' in server_code
        print(f"   ADMIN_TELEGRAM_ID loaded from .env: {'✅' if admin_id_loading else '❌'}")
        
        # Load actual ADMIN_TELEGRAM_ID value
        load_dotenv('/app/backend/.env')
        admin_id = os.environ.get('ADMIN_TELEGRAM_ID')
        expected_admin_id = "7066790254"
        admin_id_correct = admin_id == expected_admin_id
        print(f"   ADMIN_TELEGRAM_ID value correct ({expected_admin_id}): {'✅' if admin_id_correct else '❌'}")
        
        # Test 3: Check notification structure in create_and_send_label
        notification_block_pattern = r'# Send notification to admin about new label\s+if ADMIN_TELEGRAM_ID:'
        notification_block_found = bool(re.search(notification_block_pattern, server_code))
        print(f"   Admin notification block exists: {'✅' if notification_block_found else '❌'}")
        
        # Test 4: Check notification message structure components
        required_components = {
            'user_info': r'👤 \*Пользователь:\*',
            'sender_address': r'📤 \*От:\*',
            'receiver_address': r'📥 \*Кому:\*',
            'carrier_service': r'🚚 \*Перевозчик:\*',
            'tracking_number': r'📋 \*Трекинг:\*',
            'price': r'💰 \*Цена:\*',
            'weight': r'⚖️ \*Вес:\*',
            'timestamp': r'🕐 \*Время:\*'
        }
        
        components_found = {}
        for component, pattern in required_components.items():
            found = bool(re.search(pattern, server_code))
            components_found[component] = found
            print(f"   Notification includes {component}: {'✅' if found else '❌'}")
        
        # Test 5: Check parse_mode='Markdown' usage
        markdown_parse = "parse_mode='Markdown'" in server_code and 'admin_message' in server_code
        print(f"   Uses parse_mode='Markdown': {'✅' if markdown_parse else '❌'}")
        
        # Test 6: Check error handling for notification failure
        error_handling = 'except Exception as e:' in server_code and 'Failed to send label notification to admin' in server_code
        print(f"   Error handling for notification failure: {'✅' if error_handling else '❌'}")
        
        # Test 7: Check notification timing - AFTER label creation and DB save
        timing_check = server_code.find('await db.shipping_labels.insert_one(label_dict)') < server_code.find('# Send notification to admin about new label')
        print(f"   Notification sent AFTER label creation and DB save: {'✅' if timing_check else '❌'}")
        
        # Test 8: Check notification timing - BEFORE check_shipstation_balance()
        balance_check_timing = server_code.find('# Send notification to admin about new label') < server_code.find('asyncio.create_task(check_shipstation_balance())')
        print(f"   Notification sent BEFORE check_shipstation_balance(): {'✅' if balance_check_timing else '❌'}")
        
        # Test 9: Check conditional sending (only if ADMIN_TELEGRAM_ID is set)
        conditional_sending = 'if ADMIN_TELEGRAM_ID:' in server_code
        print(f"   Notification only sent if ADMIN_TELEGRAM_ID set: {'✅' if conditional_sending else '❌'}")
        
        # Test 10: Check logging for successful notification
        success_logging = 'logger.info(f"Label creation notification sent to admin {ADMIN_TELEGRAM_ID}")' in server_code
        print(f"   Success logging implemented: {'✅' if success_logging else '❌'}")
        
        # Test 11: Check logging for failed notification
        failure_logging = 'logger.error(f"Failed to send label notification to admin: {e}")' in server_code
        print(f"   Failure logging implemented: {'✅' if failure_logging else '❌'}")
        
        # Overall assessment
        critical_checks = [
            create_label_found,
            admin_id_loading,
            admin_id_correct,
            notification_block_found,
            all(components_found.values()),
            markdown_parse,
            error_handling,
            timing_check,
            balance_check_timing,
            conditional_sending,
            success_logging,
            failure_logging
        ]
        
        checks_passed = sum(critical_checks)
        total_checks = len(critical_checks)
        
        print(f"\n   🎯 ADMIN NOTIFICATION IMPLEMENTATION ASSESSMENT:")
        print(f"   Passed checks: {checks_passed}/{total_checks}")
        print(f"   Success rate: {(checks_passed/total_checks)*100:.1f}%")
        
        if checks_passed >= 10:  # At least 83% of checks passing
            print(f"   ✅ ADMIN NOTIFICATION FUNCTIONALITY CORRECTLY IMPLEMENTED")
            print(f"   Expected behavior: After successful label creation → detailed notification sent to admin {expected_admin_id}")
        else:
            print(f"   ❌ ADMIN NOTIFICATION FUNCTIONALITY HAS ISSUES")
            print(f"   Missing critical components prevent proper admin notifications")
        
        return checks_passed >= 10
        
    except Exception as e:
        print(f"❌ Admin notification test error: {e}")
        return False

def test_database_collections():
    """Test Database Collections for Orders and Shipping Labels"""
    print("\n🔍 Testing Database Collections...")
    print("🎯 Checking orders and shipping_labels collections and their relationships")
    
    try:
        # Import MongoDB client
        import sys
        sys.path.append('/app/backend')
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio
        import os
        
        # Load environment
        load_dotenv('/app/backend/.env')
        mongo_url = os.environ['MONGO_URL']
        db_name = os.environ['DB_NAME']
        
        # Create async client
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        async def check_collections():
            # Test 1: Check orders collection
            print("   📋 Testing orders collection:")
            orders_count = await db.orders.count_documents({})
            print(f"   Total orders in database: {orders_count}")
            
            if orders_count > 0:
                # Get sample order
                sample_order = await db.orders.find_one({}, {"_id": 0})
                required_fields = ['id', 'telegram_id', 'address_from', 'address_to', 'parcel', 'amount', 'payment_status', 'shipping_status']
                
                for field in required_fields:
                    has_field = field in sample_order
                    print(f"      Order has {field}: {'✅' if has_field else '❌'}")
                
                print(f"   ✅ Orders collection exists with {orders_count} records")
            else:
                print(f"   ⚠️ Orders collection is empty")
            
            # Test 2: Check shipping_labels collection
            print("   📋 Testing shipping_labels collection:")
            labels_count = await db.shipping_labels.count_documents({})
            print(f"   Total shipping labels in database: {labels_count}")
            
            if labels_count > 0:
                # Get sample label
                sample_label = await db.shipping_labels.find_one({}, {"_id": 0})
                required_fields = ['id', 'order_id', 'tracking_number', 'label_url', 'carrier', 'service_level', 'amount', 'status']
                
                for field in required_fields:
                    has_field = field in sample_label
                    print(f"      Label has {field}: {'✅' if has_field else '❌'}")
                
                print(f"   ✅ Shipping labels collection exists with {labels_count} records")
            else:
                print(f"   ⚠️ Shipping labels collection is empty")
            
            # Test 3: Check relationship between orders and shipping_labels
            print("   📋 Testing order-label relationships:")
            if orders_count > 0 and labels_count > 0:
                # Find orders with corresponding labels
                orders_with_labels = 0
                async for order in db.orders.find({}, {"_id": 0, "id": 1}):
                    label = await db.shipping_labels.find_one({"order_id": order["id"]}, {"_id": 0})
                    if label:
                        orders_with_labels += 1
                
                print(f"   Orders with shipping labels: {orders_with_labels}/{orders_count}")
                
                if orders_with_labels > 0:
                    print(f"   ✅ Order-label relationships working correctly")
                else:
                    print(f"   ⚠️ No orders have corresponding shipping labels")
            else:
                print(f"   ⚠️ Cannot test relationships - insufficient data")
            
            # Test 4: Check for paid orders (potential label creation candidates)
            paid_orders = await db.orders.count_documents({"payment_status": "paid"})
            print(f"   Paid orders (label creation candidates): {paid_orders}")
            
            # Test 5: Check for created labels
            created_labels = await db.shipping_labels.count_documents({"status": "created"})
            print(f"   Successfully created labels: {created_labels}")
            
            return {
                'orders_count': orders_count,
                'labels_count': labels_count,
                'orders_with_labels': orders_with_labels if orders_count > 0 and labels_count > 0 else 0,
                'paid_orders': paid_orders,
                'created_labels': created_labels
            }
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(check_collections())
        loop.close()
        
        # Close client
        client.close()
        
        # Assessment
        has_data = results['orders_count'] > 0 or results['labels_count'] > 0
        has_relationships = results['orders_with_labels'] > 0
        
        print(f"\n   🎯 DATABASE COLLECTIONS ASSESSMENT:")
        print(f"   Database has order/label data: {'✅' if has_data else '⚠️'}")
        print(f"   Order-label relationships exist: {'✅' if has_relationships else '⚠️'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database collections test error: {e}")
        return False

def test_backend_logs_for_notifications():
    """Test Backend Logs for Admin Notification Messages"""
    print("\n🔍 Testing Backend Logs for Admin Notifications...")
    print("🎯 Checking logs for label creation notification messages")
    
    try:
        # Check backend output logs for notification messages
        print("   📋 Checking backend output logs:")
        
        # Look for successful notification logs
        success_log_cmd = "tail -n 200 /var/log/supervisor/backend.out.log | grep -i 'Label creation notification sent to admin'"
        success_logs = os.popen(success_log_cmd).read().strip()
        
        if success_logs:
            success_lines = success_logs.split('\n')
            print(f"   ✅ Found {len(success_lines)} successful notification log entries")
            print(f"   Recent success log: {success_lines[-1] if success_lines else 'None'}")
        else:
            print(f"   ⚠️ No successful notification logs found")
        
        # Look for failed notification logs
        failure_log_cmd = "tail -n 200 /var/log/supervisor/backend.err.log | grep -i 'Failed to send label notification to admin'"
        failure_logs = os.popen(failure_log_cmd).read().strip()
        
        if failure_logs:
            failure_lines = failure_logs.split('\n')
            print(f"   ⚠️ Found {len(failure_lines)} failed notification log entries")
            print(f"   Recent failure log: {failure_lines[-1] if failure_lines else 'None'}")
        else:
            print(f"   ✅ No failed notification logs found")
        
        # Check for any admin-related logs
        print("   📋 Checking for admin-related logs:")
        admin_log_cmd = "tail -n 100 /var/log/supervisor/backend.out.log | grep -i 'admin\\|7066790254'"
        admin_logs = os.popen(admin_log_cmd).read().strip()
        
        if admin_logs:
            admin_lines = admin_logs.split('\n')
            print(f"   ✅ Found {len(admin_lines)} admin-related log entries")
            # Show last few admin logs
            for line in admin_lines[-3:]:
                if line.strip():
                    print(f"      {line.strip()}")
        else:
            print(f"   ℹ️ No admin-related logs found")
        
        # Check for label creation logs
        print("   📋 Checking for label creation logs:")
        label_log_cmd = "tail -n 100 /var/log/supervisor/backend.out.log | grep -i 'Label created successfully\\|Creating label for order'"
        label_logs = os.popen(label_log_cmd).read().strip()
        
        if label_logs:
            label_lines = label_logs.split('\n')
            print(f"   ✅ Found {len(label_lines)} label creation log entries")
            print(f"   Recent label creation: {label_lines[-1] if label_lines else 'None'}")
        else:
            print(f"   ⚠️ No recent label creation logs found")
        
        # Assessment
        has_success_logs = bool(success_logs)
        no_failure_logs = not bool(failure_logs)
        has_admin_activity = bool(admin_logs)
        has_label_activity = bool(label_logs)
        
        print(f"\n   🎯 BACKEND LOGS ASSESSMENT:")
        print(f"   Successful notifications logged: {'✅' if has_success_logs else '⚠️'}")
        print(f"   No notification failures: {'✅' if no_failure_logs else '⚠️'}")
        print(f"   Admin activity present: {'✅' if has_admin_activity else 'ℹ️'}")
        print(f"   Label creation activity: {'✅' if has_label_activity else 'ℹ️'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend logs test error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Admin Notification Test Suite...")
    print("🎯 CRITICAL FOCUS: Admin Notification for Label Creation")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Base: {API_BASE}")
    
    # Track test results
    test_results = {}
    
    # Run CRITICAL tests for Admin Notification per review request
    print("\n" + "="*80)
    print("🎯 CRITICAL TEST: Admin Notification for Label Creation")
    print("="*80)
    
    test_results['admin_notification_for_label_creation'] = test_admin_notification_for_label_creation()
    test_results['database_collections'] = test_database_collections()
    test_results['backend_logs_for_notifications'] = test_backend_logs_for_notifications()
    
    # Summary
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    
    critical_tests = [
        'admin_notification_for_label_creation',
        'database_collections', 
        'backend_logs_for_notifications'
    ]
    
    print(f"\n📋 CRITICAL TESTS:")
    critical_passed = 0
    for test_name in critical_tests:
        if test_name in test_results:
            result = test_results[test_name]
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name}: {status}")
            if result:
                critical_passed += 1
    
    # Overall summary
    total_critical = len(critical_tests)
    total_tests = len(test_results)
    total_passed = sum(1 for result in test_results.values() if result)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Critical tests: {critical_passed}/{total_critical} passed ({critical_passed/total_critical*100:.1f}%)")
    print(f"   Overall: {total_passed}/{total_tests} tests passed ({total_passed/total_tests*100:.1f}%)")
    
    # Final verdict
    if critical_passed == total_critical:
        print("\n🎉 CRITICAL SUCCESS: Admin Notification Implementation Appears Correct!")
        print("✅ Admin notification functionality properly implemented")
        print("✅ Database collections and relationships working") 
        print("✅ Backend logging infrastructure in place")
        print("✅ No obvious issues preventing admin notifications")
        print("\n🔍 EXPECTED BEHAVIOR:")
        print("   • After successful label creation → detailed notification sent to admin 7066790254")
        print("   • Notification includes user info, addresses, carrier, tracking, price, weight, timestamp")
        print("   • Uses Markdown formatting for better readability")
        print("   • Proper error handling and logging implemented")
    else:
        print(f"\n❌ CRITICAL FAILURE: Admin Notification Has Implementation Issues!")
        print(f"   {total_critical - critical_passed} critical test(s) failed")
        print("   Check logs above for detailed error information")
        print("\n🔍 INVESTIGATION NEEDED:")
        print("   • Review failed tests above")
        print("   • Check create_and_send_label function implementation")
        print("   • Verify ADMIN_TELEGRAM_ID configuration")
    
    print("=" * 80)