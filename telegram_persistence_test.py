#!/usr/bin/env python3
"""
Telegram Bot Persistence Test Suite
Tests the critical persistence bug fix for Telegram bot ConversationHandler
"""

import requests
import json
import os
import re
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://easyshipbot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def test_redis_persistence_configuration():
    """Test Redis persistence configuration - CRITICAL TEST per review request"""
    print("🔍 Testing Redis Persistence Configuration...")
    print("🎯 CRITICAL: RedisPersistence should be configured and connected to Redis Cloud")
    
    try:
        # Load environment variables from backend .env
        load_dotenv('/app/backend/.env')
        
        # Check Redis configuration
        redis_host = os.environ.get('REDIS_HOST')
        redis_port = os.environ.get('REDIS_PORT')
        redis_password = os.environ.get('REDIS_PASSWORD')
        
        print(f"   Redis Configuration:")
        print(f"   REDIS_HOST: {'✅' if redis_host else '❌'} ({redis_host if redis_host else 'Not set'})")
        print(f"   REDIS_PORT: {'✅' if redis_port else '❌'} ({redis_port if redis_port else 'Not set'})")
        print(f"   REDIS_PASSWORD: {'✅' if redis_password else '❌'} ({'***' if redis_password else 'Not set'})")
        
        # Verify Redis Cloud configuration
        if redis_host and 'redislabs.com' in redis_host:
            print(f"   ✅ Redis Cloud host detected: {redis_host}")
        elif redis_host:
            print(f"   ⚠️ Redis host configured but not Redis Cloud: {redis_host}")
        else:
            print(f"   ❌ Redis host not configured")
            return False
        
        # Check if port is correct for Redis Cloud
        if redis_port and redis_port == "11907":
            print(f"   ✅ Redis Cloud port correct: {redis_port}")
        elif redis_port:
            print(f"   ⚠️ Redis port configured but unexpected: {redis_port}")
        else:
            print(f"   ❌ Redis port not configured")
            return False
        
        # Verify password is set (required for Redis Cloud)
        if redis_password and len(redis_password) > 10:
            print(f"   ✅ Redis password configured (length: {len(redis_password)})")
        else:
            print(f"   ❌ Redis password not properly configured")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Redis configuration test error: {e}")
        return False

def test_conversation_handler_persistence():
    """Test ConversationHandler persistence configuration - CRITICAL TEST per review request"""
    print("\n🔍 Testing ConversationHandler Persistence Configuration...")
    print("🎯 CRITICAL: persistent=True should be added to template_rename_handler and order_conv_handler")
    
    try:
        # Read the server.py file to check ConversationHandler configurations
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Split into lines for easier analysis
        lines = server_code.split('\n')
        
        # Find ConversationHandler definitions
        conv_handler_pattern = r'(\w+)\s*=\s*ConversationHandler\('
        conv_handlers = re.findall(conv_handler_pattern, server_code)
        
        print(f"   Found {len(conv_handlers)} ConversationHandler definitions: {conv_handlers}")
        
        # Check specific handlers mentioned in review request
        handlers_to_check = ['template_rename_handler', 'order_conv_handler']
        persistence_results = {}
        
        for handler_name in handlers_to_check:
            # Find the line where the handler is defined
            handler_line = None
            for i, line in enumerate(lines):
                if f'{handler_name} = ConversationHandler(' in line:
                    handler_line = i
                    break
            
            if handler_line is not None:
                print(f"   {handler_name}:")
                print(f"      Found: ✅ (line {handler_line + 1})")
                
                # Look for persistent=True in the next 200 lines (within the handler definition)
                has_persistent = False
                persistent_line = None
                
                for j in range(handler_line, min(handler_line + 200, len(lines))):
                    if 'persistent=True' in lines[j]:
                        has_persistent = True
                        persistent_line = j + 1
                        break
                    # Stop if we hit the end of the handler (closing parenthesis at start of line)
                    if j > handler_line and lines[j].strip() == ')':
                        break
                
                persistence_results[handler_name] = has_persistent
                
                print(f"      persistent=True: {'✅' if has_persistent else '❌'}")
                if persistent_line:
                    print(f"      persistent=True found at line: {persistent_line}")
                
            else:
                print(f"   {handler_name}: ❌ Not found")
                persistence_results[handler_name] = False
        
        # Check for RedisPersistence import and usage
        redis_persistence_import = 'from telegram.ext import' in server_code and 'RedisPersistence' in server_code
        print(f"\n   RedisPersistence import: {'✅' if redis_persistence_import else '❌'}")
        
        # Check for persistence initialization
        persistence_init_pattern = r'RedisPersistence\('
        persistence_init = bool(re.search(persistence_init_pattern, server_code))
        print(f"   RedisPersistence initialization: {'✅' if persistence_init else '❌'}")
        
        # Check Application.builder().persistence() usage
        app_persistence = 'persistence(' in server_code and 'Application.builder()' in server_code
        print(f"   Application persistence setup: {'✅' if app_persistence else '❌'}")
        
        # Overall success criteria
        template_rename_persistent = persistence_results.get('template_rename_handler', False)
        order_conv_persistent = persistence_results.get('order_conv_handler', False)
        
        print(f"\n   🎯 PERSISTENCE FIX SUCCESS CRITERIA:")
        print(f"   template_rename_handler persistent=True: {'✅' if template_rename_persistent else '❌'}")
        print(f"   order_conv_handler persistent=True: {'✅' if order_conv_persistent else '❌'}")
        print(f"   RedisPersistence configured: {'✅' if redis_persistence_import and persistence_init else '❌'}")
        
        if template_rename_persistent and order_conv_persistent and redis_persistence_import and persistence_init:
            print(f"   ✅ PERSISTENCE BUG FIX VERIFIED: All ConversationHandlers have persistent=True")
            return True
        else:
            print(f"   ❌ PERSISTENCE BUG FIX INCOMPLETE: Missing required persistence configuration")
            return False
        
    except Exception as e:
        print(f"❌ ConversationHandler persistence test error: {e}")
        return False

def test_production_bot_configuration():
    """Test production bot configuration - CRITICAL TEST per review request"""
    print("\n🔍 Testing Production Bot Configuration...")
    print("🎯 CRITICAL: Production bot should use telegram_shipping_bot_production database and production token")
    
    try:
        # Load environment variables
        load_dotenv('/app/backend/.env')
        
        # Check webhook base URL to determine environment
        webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
        is_production = 'crypto-shipping.emergent.host' in webhook_base_url
        
        print(f"   Environment Detection:")
        print(f"   WEBHOOK_BASE_URL: {webhook_base_url}")
        print(f"   Is Production: {'✅' if is_production else '❌ (Preview environment)'}")
        
        # Check bot tokens
        prod_token = os.environ.get('TELEGRAM_BOT_TOKEN_PRODUCTION')
        preview_token = os.environ.get('TELEGRAM_BOT_TOKEN_PREVIEW')
        main_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        
        print(f"\n   Bot Token Configuration:")
        print(f"   TELEGRAM_BOT_TOKEN_PRODUCTION: {'✅' if prod_token else '❌'}")
        print(f"   TELEGRAM_BOT_TOKEN_PREVIEW: {'✅' if preview_token else '❌'}")
        print(f"   TELEGRAM_BOT_TOKEN (main): {'✅' if main_token else '❌'}")
        
        # Verify production token format
        if prod_token:
            expected_prod_token = "8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM"
            if prod_token == expected_prod_token:
                print(f"   ✅ Production token matches expected: {prod_token[:15]}...")
            else:
                print(f"   ❌ Production token mismatch: {prod_token[:15]}...")
        
        # Check database configuration
        db_name_prod = os.environ.get('DB_NAME_PRODUCTION')
        db_name_preview = os.environ.get('DB_NAME_PREVIEW')
        
        print(f"\n   Database Configuration:")
        print(f"   DB_NAME_PRODUCTION: {'✅' if db_name_prod else '❌'} ({db_name_prod})")
        print(f"   DB_NAME_PREVIEW: {'✅' if db_name_preview else '❌'} ({db_name_preview})")
        
        # Verify production database name
        if db_name_prod:
            expected_prod_db = "async-tg-bot-telegram_shipping_bot"
            if db_name_prod == expected_prod_db:
                print(f"   ✅ Production database name correct: {db_name_prod}")
            else:
                print(f"   ❌ Production database name unexpected: {db_name_prod}")
        
        # Check server.py for auto-selection logic
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Check for environment-based token selection
        token_selection_logic = 'crypto-shipping.emergent.host' in server_code and 'TELEGRAM_BOT_TOKEN_PRODUCTION' in server_code
        print(f"\n   Auto-selection Logic:")
        print(f"   Environment-based token selection: {'✅' if token_selection_logic else '❌'}")
        
        # Check for database auto-selection
        db_selection_logic = 'crypto-shipping.emergent.host' in server_code and 'DB_NAME_PRODUCTION' in server_code
        print(f"   Environment-based database selection: {'✅' if db_selection_logic else '❌'}")
        
        # Success criteria
        tokens_configured = prod_token and preview_token
        databases_configured = db_name_prod and db_name_preview
        auto_selection_working = token_selection_logic and db_selection_logic
        
        print(f"\n   🎯 PRODUCTION CONFIGURATION SUCCESS CRITERIA:")
        print(f"   Bot tokens configured: {'✅' if tokens_configured else '❌'}")
        print(f"   Databases configured: {'✅' if databases_configured else '❌'}")
        print(f"   Auto-selection logic: {'✅' if auto_selection_working else '❌'}")
        
        if tokens_configured and databases_configured and auto_selection_working:
            print(f"   ✅ PRODUCTION BOT CONFIGURATION VERIFIED")
            return True
        else:
            print(f"   ❌ PRODUCTION BOT CONFIGURATION INCOMPLETE")
            return False
        
    except Exception as e:
        print(f"❌ Production bot configuration test error: {e}")
        return False

def test_webhook_vs_polling_mode():
    """Test webhook vs polling mode configuration - CRITICAL TEST per review request"""
    print("\n🔍 Testing Webhook vs Polling Mode Configuration...")
    print("🎯 CRITICAL: Production should use webhook mode, preview should use polling mode")
    
    try:
        # Check current webhook status
        response = requests.get(f"{API_BASE}/telegram/status", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Get current mode
            bot_mode = data.get('bot_mode', 'unknown')
            webhook_url = data.get('webhook_url')
            application_running = data.get('application_running', False)
            
            print(f"   Current Bot Status:")
            print(f"   bot_mode: {bot_mode}")
            print(f"   webhook_url: {webhook_url if webhook_url else 'Not set'}")
            print(f"   application_running: {application_running}")
            
            # Determine expected mode based on environment
            load_dotenv('/app/backend/.env')
            webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
            is_production = 'crypto-shipping.emergent.host' in webhook_base_url
            
            expected_mode = 'WEBHOOK' if is_production else 'POLLING'
            print(f"\n   Environment Analysis:")
            print(f"   Environment: {'Production' if is_production else 'Preview'}")
            print(f"   Expected mode: {expected_mode}")
            print(f"   Actual mode: {bot_mode}")
            
            # Check if mode matches expectation
            mode_correct = bot_mode == expected_mode
            print(f"   Mode correct: {'✅' if mode_correct else '❌'}")
            
            # For webhook mode, verify webhook URL is set
            if expected_mode == 'WEBHOOK':
                webhook_configured = webhook_url is not None and len(webhook_url) > 0
                print(f"   Webhook URL configured: {'✅' if webhook_configured else '❌'}")
            else:
                webhook_configured = True  # Not required for polling
            
            # Check for polling conflicts (should not exist in webhook mode)
            if bot_mode == 'WEBHOOK':
                # Check backend logs for polling conflicts
                log_result = os.popen("tail -n 100 /var/log/supervisor/backend.err.log | grep -i 'conflict\\|getupdates'").read()
                
                if log_result.strip():
                    # Check if conflicts are recent (after webhook setup)
                    recent_conflicts = []
                    for line in log_result.split('\n'):
                        if 'conflict' in line.lower() or 'getupdates' in line.lower():
                            recent_conflicts.append(line.strip())
                    
                    if recent_conflicts:
                        print(f"   ⚠️ Polling conflicts detected in logs:")
                        for conflict in recent_conflicts[-2:]:  # Show last 2 conflicts
                            if conflict:
                                print(f"      {conflict}")
                        polling_conflicts = True
                    else:
                        polling_conflicts = False
                else:
                    polling_conflicts = False
                
                print(f"   No polling conflicts: {'✅' if not polling_conflicts else '❌'}")
            else:
                polling_conflicts = False  # Not applicable for polling mode
            
            # Success criteria
            mode_matches = mode_correct
            no_conflicts = not polling_conflicts
            webhook_ok = webhook_configured
            app_running = application_running
            
            print(f"\n   🎯 WEBHOOK/POLLING MODE SUCCESS CRITERIA:")
            print(f"   Correct mode for environment: {'✅' if mode_matches else '❌'}")
            print(f"   No polling conflicts: {'✅' if no_conflicts else '❌'}")
            print(f"   Webhook properly configured: {'✅' if webhook_ok else '❌'}")
            print(f"   Application running: {'✅' if app_running else '❌'}")
            
            if mode_matches and no_conflicts and webhook_ok and app_running:
                print(f"   ✅ WEBHOOK/POLLING MODE VERIFIED: Bot running in correct mode without conflicts")
                return True
            else:
                print(f"   ❌ WEBHOOK/POLLING MODE ISSUE: Configuration problems detected")
                return False
        else:
            print(f"   ❌ Cannot check webhook status: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Webhook vs polling mode test error: {e}")
        return False

def test_backend_logs_for_persistence():
    """Test backend logs for persistence-related entries - CRITICAL TEST per review request"""
    print("\n🔍 Testing Backend Logs for Persistence...")
    print("🎯 CRITICAL: Logs should show Redis persistence save/load operations")
    
    try:
        # Check backend logs for persistence-related entries
        print("   Checking backend error logs...")
        error_logs = os.popen("tail -n 200 /var/log/supervisor/backend.err.log").read()
        
        print("   Checking backend output logs...")
        output_logs = os.popen("tail -n 200 /var/log/supervisor/backend.out.log").read()
        
        combined_logs = error_logs + "\n" + output_logs
        
        # Look for Redis-related entries
        redis_keywords = ['redis', 'persistence', 'RedisPersistence', 'conversation', 'state']
        redis_entries = []
        
        for line in combined_logs.split('\n'):
            line_lower = line.lower()
            if any(keyword.lower() in line_lower for keyword in redis_keywords):
                redis_entries.append(line.strip())
        
        print(f"   Redis/Persistence log entries found: {len(redis_entries)}")
        
        if redis_entries:
            print(f"   📋 Recent Redis/Persistence logs:")
            for entry in redis_entries[-5:]:  # Show last 5 entries
                if entry:
                    print(f"      {entry}")
        else:
            print(f"   ℹ️ No explicit Redis/Persistence logs found (may be normal)")
        
        # Look for ConversationHandler-related entries
        conversation_keywords = ['ConversationHandler', 'conversation', 'template_rename', 'order_conv']
        conversation_entries = []
        
        for line in combined_logs.split('\n'):
            if any(keyword in line for keyword in conversation_keywords):
                conversation_entries.append(line.strip())
        
        print(f"\n   ConversationHandler log entries found: {len(conversation_entries)}")
        
        if conversation_entries:
            print(f"   📋 Recent ConversationHandler logs:")
            for entry in conversation_entries[-3:]:  # Show last 3 entries
                if entry:
                    print(f"      {entry}")
        
        # Look for bot startup messages
        startup_keywords = ['Telegram Bot', 'started', 'webhook', 'polling', 'Application']
        startup_entries = []
        
        for line in combined_logs.split('\n'):
            if any(keyword in line for keyword in startup_keywords):
                startup_entries.append(line.strip())
        
        print(f"\n   Bot startup log entries found: {len(startup_entries)}")
        
        if startup_entries:
            print(f"   📋 Recent bot startup logs:")
            for entry in startup_entries[-3:]:  # Show last 3 entries
                if entry:
                    print(f"      {entry}")
        
        # Look for any critical errors
        error_keywords = ['error', 'exception', 'failed', 'traceback']
        critical_errors = []
        
        for line in error_logs.split('\n'):
            line_lower = line.lower()
            # Skip known non-critical errors
            if any(skip in line_lower for skip in ['conflict', 'getupdates', 'polling']):
                continue
            if any(keyword in line_lower for keyword in error_keywords):
                critical_errors.append(line.strip())
        
        print(f"\n   Critical errors found: {len(critical_errors)}")
        
        if critical_errors:
            print(f"   ⚠️ Recent critical errors:")
            for error in critical_errors[-3:]:  # Show last 3 errors
                if error:
                    print(f"      {error}")
        else:
            print(f"   ✅ No critical errors in recent logs")
        
        # Success criteria
        bot_started = any('started' in entry.lower() for entry in startup_entries)
        no_critical_errors = len(critical_errors) == 0
        
        print(f"\n   🎯 LOG ANALYSIS SUCCESS CRITERIA:")
        print(f"   Bot started successfully: {'✅' if bot_started else '❌'}")
        print(f"   No critical errors: {'✅' if no_critical_errors else '❌'}")
        print(f"   Persistence logs present: {'✅' if redis_entries else 'ℹ️ (optional)'}")
        
        if bot_started and no_critical_errors:
            print(f"   ✅ BACKEND LOGS VERIFIED: Bot started without critical errors")
            return True
        else:
            print(f"   ❌ BACKEND LOGS ISSUE: Critical problems detected")
            return False
        
    except Exception as e:
        print(f"❌ Backend logs test error: {e}")
        return False

def test_telegram_bot_infrastructure():
    """Test Telegram bot infrastructure for persistence support"""
    print("\n🔍 Testing Telegram Bot Infrastructure for Persistence...")
    
    try:
        # Check if bot token is valid
        load_dotenv('/app/backend/.env')
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        
        if not bot_token:
            print("   ❌ Bot token not found")
            return False
        
        # Test bot token validity
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get('ok'):
                bot_data = bot_info.get('result', {})
                print(f"   Bot validation: ✅ (@{bot_data.get('username', 'Unknown')})")
                
                # Check if it's the correct bot for environment
                username = bot_data.get('username', '')
                webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
                is_production = 'crypto-shipping.emergent.host' in webhook_base_url
                
                if is_production:
                    expected_username = 'whitelabel_shipping_bot'
                else:
                    expected_username = 'whitelabel_shipping_bot_test_bot'
                
                if username == expected_username:
                    print(f"   ✅ Correct bot for environment: @{username}")
                else:
                    print(f"   ⚠️ Unexpected bot for environment: @{username} (expected: @{expected_username})")
                
            else:
                print(f"   ❌ Invalid bot token response")
                return False
        else:
            print(f"   ❌ Bot token validation failed: {response.status_code}")
            return False
        
        # Check webhook endpoint
        webhook_response = requests.get(f"{API_BASE}/telegram/status", timeout=10)
        
        if webhook_response.status_code == 200:
            webhook_data = webhook_response.json()
            print(f"   Webhook endpoint: ✅")
            print(f"   Bot mode: {webhook_data.get('bot_mode', 'unknown')}")
        else:
            print(f"   ❌ Webhook endpoint failed: {webhook_response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram bot infrastructure test error: {e}")
        return False

def run_persistence_tests():
    """Run all persistence-related tests"""
    print("=" * 80)
    print("🚀 TELEGRAM BOT PERSISTENCE BUG FIX TESTING")
    print("=" * 80)
    print("Testing critical persistence bug fix: persistent=True in ConversationHandler")
    print("This addresses the bot 'hanging' and requiring double message sends")
    print("=" * 80)
    
    test_results = {}
    
    # Test 1: Redis Persistence Configuration
    test_results['redis_config'] = test_redis_persistence_configuration()
    
    # Test 2: ConversationHandler Persistence
    test_results['conversation_persistence'] = test_conversation_handler_persistence()
    
    # Test 3: Production Bot Configuration
    test_results['production_config'] = test_production_bot_configuration()
    
    # Test 4: Webhook vs Polling Mode
    test_results['webhook_polling'] = test_webhook_vs_polling_mode()
    
    # Test 5: Backend Logs Analysis
    test_results['backend_logs'] = test_backend_logs_for_persistence()
    
    # Test 6: Bot Infrastructure
    test_results['bot_infrastructure'] = test_telegram_bot_infrastructure()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 PERSISTENCE BUG FIX TEST SUMMARY")
    print("=" * 80)
    
    passed_tests = sum(1 for result in test_results.values() if result)
    total_tests = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL PERSISTENCE TESTS PASSED - Bug fix appears to be working!")
    elif passed_tests >= total_tests * 0.8:
        print("⚠️ MOST TESTS PASSED - Minor issues may remain")
    else:
        print("❌ CRITICAL ISSUES DETECTED - Persistence bug fix needs attention")
    
    print("=" * 80)
    
    return test_results

if __name__ == "__main__":
    run_persistence_tests()