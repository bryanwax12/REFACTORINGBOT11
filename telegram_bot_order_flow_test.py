#!/usr/bin/env python3
"""
Telegram Bot Order Flow Test - City to State Transition Issue
Tests the specific issue reported: After entering CITY, bot shows ADDRESS prompt instead of STATE prompt
"""

import sys
import os
import re
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append('/app/backend')

def analyze_order_from_city_function():
    """Analyze the order_from_city function implementation"""
    print("🔍 ANALYZING ORDER_FROM_CITY FUNCTION...")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Find the order_from_city function
        pattern = r'async def order_from_city\(.*?\):(.*?)(?=async def|\Z)'
        match = re.search(pattern, server_code, re.DOTALL)
        
        if not match:
            print("❌ order_from_city function not found")
            return False
        
        function_code = match.group(1)
        print("✅ order_from_city function found")
        
        # Check 1: Function should show "Шаг 5/13: Штат отправителя (2 буквы)"
        correct_prompt = "Шаг 5/13: Штат отправителя (2 буквы)" in function_code
        print(f"   Shows correct state prompt: {'✅' if correct_prompt else '❌'}")
        
        if not correct_prompt:
            # Check what prompt it actually shows
            prompt_pattern = r'message_text = """(.*?)"""'
            prompt_match = re.search(prompt_pattern, function_code, re.DOTALL)
            if prompt_match:
                actual_prompt = prompt_match.group(1).strip()
                print(f"   Actual prompt: '{actual_prompt}'")
        
        # Check 2: Function should save last_state = FROM_STATE
        saves_from_state = "context.user_data['last_state'] = FROM_STATE" in function_code
        print(f"   Saves last_state = FROM_STATE: {'✅' if saves_from_state else '❌'}")
        
        # Check 3: Function should return FROM_STATE
        returns_from_state = "return FROM_STATE" in function_code
        print(f"   Returns FROM_STATE: {'✅' if returns_from_state else '❌'}")
        
        # Check 4: Function should store city in context.user_data['from_city']
        stores_city = "context.user_data['from_city'] = city" in function_code
        print(f"   Stores city in context: {'✅' if stores_city else '❌'}")
        
        # Check 5: Function should call mark_message_as_selected
        calls_mark_selected = "await mark_message_as_selected(update, context)" in function_code
        print(f"   Calls mark_message_as_selected: {'✅' if calls_mark_selected else '❌'}")
        
        return correct_prompt and saves_from_state and returns_from_state and stores_city
        
    except Exception as e:
        print(f"❌ Error analyzing order_from_city function: {e}")
        return False

def check_conversation_handler_states():
    """Check ConversationHandler state configuration"""
    print("\n🔍 CHECKING CONVERSATION HANDLER STATES...")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Find the ConversationHandler configuration
        conv_handler_pattern = r'order_conv_handler = ConversationHandler\((.*?)\)'
        match = re.search(conv_handler_pattern, server_code, re.DOTALL)
        
        if not match:
            print("❌ ConversationHandler configuration not found")
            return False
        
        conv_config = match.group(1)
        print("✅ ConversationHandler configuration found")
        
        # Check FROM_CITY state configuration
        from_city_pattern = r'FROM_CITY:\s*\[(.*?)\]'
        from_city_match = re.search(from_city_pattern, conv_config, re.DOTALL)
        
        if not from_city_match:
            print("❌ FROM_CITY state not found in ConversationHandler")
            return False
        
        from_city_handlers = from_city_match.group(1)
        print("✅ FROM_CITY state found in ConversationHandler")
        
        # Check if FROM_CITY maps to order_from_city function
        maps_to_order_from_city = "order_from_city" in from_city_handlers
        print(f"   FROM_CITY maps to order_from_city: {'✅' if maps_to_order_from_city else '❌'}")
        
        # Check FROM_STATE state configuration
        from_state_pattern = r'FROM_STATE:\s*\[(.*?)\]'
        from_state_match = re.search(from_state_pattern, conv_config, re.DOTALL)
        
        if not from_state_match:
            print("❌ FROM_STATE state not found in ConversationHandler")
            return False
        
        from_state_handlers = from_state_match.group(1)
        print("✅ FROM_STATE state found in ConversationHandler")
        
        # Check if FROM_STATE maps to order_from_state function
        maps_to_order_from_state = "order_from_state" in from_state_handlers
        print(f"   FROM_STATE maps to order_from_state: {'✅' if maps_to_order_from_state else '❌'}")
        
        return maps_to_order_from_city and maps_to_order_from_state
        
    except Exception as e:
        print(f"❌ Error checking ConversationHandler states: {e}")
        return False

def check_global_handlers_interference():
    """Check for global handlers that might interfere with conversation flow"""
    print("\n🔍 CHECKING FOR GLOBAL HANDLER INTERFERENCE...")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Find all MessageHandler registrations
        message_handler_pattern = r'application\.add_handler\(MessageHandler\([^)]+\)\)'
        message_handlers = re.findall(message_handler_pattern, server_code)
        
        print(f"Found {len(message_handlers)} MessageHandler registrations")
        
        # Check for handle_topup_amount_input handler
        topup_handler_found = False
        for handler in message_handlers:
            if "handle_topup_amount_input" in handler:
                topup_handler_found = True
                print(f"   ⚠️ Global topup handler found: {handler}")
                break
        
        if topup_handler_found:
            print("   🔍 Analyzing handle_topup_amount_input function...")
            
            # Find the handle_topup_amount_input function
            topup_pattern = r'async def handle_topup_amount_input\(.*?\):(.*?)(?=async def|\Z)'
            topup_match = re.search(topup_pattern, server_code, re.DOTALL)
            
            if topup_match:
                topup_function = topup_match.group(1)
                
                # Check if function has proper guard clause
                has_guard = "if not context.user_data.get('awaiting_topup_amount'):" in topup_function
                returns_early = "return" in topup_function.split('\n')[2]  # Should return early if not awaiting
                
                print(f"   Has guard clause: {'✅' if has_guard else '❌'}")
                print(f"   Returns early if not awaiting: {'✅' if returns_early else '❌'}")
                
                # Check if awaiting_topup_amount flag is cleared in order functions
                order_new_clears = "context.user_data['awaiting_topup_amount'] = False" in server_code
                print(f"   Order functions clear awaiting flag: {'✅' if order_new_clears else '❌'}")
                
                return has_guard and returns_early and order_new_clears
            else:
                print("   ❌ handle_topup_amount_input function not found")
                return False
        else:
            print("   ✅ No global topup handler interference detected")
            return True
        
    except Exception as e:
        print(f"❌ Error checking global handlers: {e}")
        return False

def check_handler_order():
    """Check the order of handler registration"""
    print("\n🔍 CHECKING HANDLER REGISTRATION ORDER...")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Find handler registration section
        handler_section_pattern = r'(application\.add_handler\(template_rename_handler\).*?application\.add_handler\(CallbackQueryHandler\(button_callback\)\))'
        match = re.search(handler_section_pattern, server_code, re.DOTALL)
        
        if not match:
            print("❌ Handler registration section not found")
            return False
        
        handler_section = match.group(1)
        lines = handler_section.split('\n')
        
        print("Handler registration order:")
        conv_handler_line = -1
        topup_handler_line = -1
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                print(f"   {i+1}. {line}")
                if "order_conv_handler" in line:
                    conv_handler_line = i
                elif "handle_topup_amount_input" in line:
                    topup_handler_line = i
        
        if conv_handler_line == -1:
            print("❌ ConversationHandler not found in registration")
            return False
        
        if topup_handler_line == -1:
            print("✅ No global topup handler found")
            return True
        
        # ConversationHandler should be registered BEFORE global MessageHandler
        correct_order = conv_handler_line < topup_handler_line
        print(f"\nHandler order analysis:")
        print(f"   ConversationHandler at position: {conv_handler_line + 1}")
        print(f"   Global topup handler at position: {topup_handler_line + 1}")
        print(f"   Correct order (ConversationHandler first): {'✅' if correct_order else '❌'}")
        
        if not correct_order:
            print("   ⚠️ ISSUE: Global MessageHandler registered before ConversationHandler!")
            print("   This can cause the global handler to intercept conversation messages.")
        
        return correct_order
        
    except Exception as e:
        print(f"❌ Error checking handler order: {e}")
        return False

def check_step_sequence():
    """Check the step sequence in order creation"""
    print("\n🔍 CHECKING STEP SEQUENCE...")
    
    expected_sequence = [
        ("FROM_NAME", "Шаг 1/13: Имя отправителя"),
        ("FROM_ADDRESS", "Шаг 2/13: Адрес отправителя"),
        ("FROM_ADDRESS2", "Шаг 3/13: Квартира/Офис отправителя"),
        ("FROM_CITY", "Шаг 4/13: Город отправителя"),
        ("FROM_STATE", "Шаг 5/13: Штат отправителя"),
        ("FROM_ZIP", "Шаг 6/13: ZIP код отправителя"),
    ]
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        print("Expected step sequence:")
        all_correct = True
        
        for state, expected_text in expected_sequence:
            # Find the function that handles this state
            function_name = f"order_{state.lower()}"
            if state == "FROM_ADDRESS2":
                function_name = "order_from_address2"
            
            # Find the function and check its prompt
            pattern = rf'async def {function_name}\(.*?\):(.*?)(?=async def|\Z)'
            match = re.search(pattern, server_code, re.DOTALL)
            
            if match:
                function_code = match.group(1)
                has_correct_prompt = expected_text in function_code
                print(f"   {state}: {'✅' if has_correct_prompt else '❌'} - {expected_text}")
                
                if not has_correct_prompt:
                    all_correct = False
                    # Try to find what prompt it actually shows
                    prompt_pattern = r'message_text = """(.*?)"""'
                    prompt_match = re.search(prompt_pattern, function_code, re.DOTALL)
                    if prompt_match:
                        actual_prompt = prompt_match.group(1).strip().split('\n')[0]
                        print(f"      Actual: {actual_prompt}")
            else:
                print(f"   {state}: ❌ - Function {function_name} not found")
                all_correct = False
        
        return all_correct
        
    except Exception as e:
        print(f"❌ Error checking step sequence: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 80)
    print("🤖 TELEGRAM BOT ORDER FLOW TEST - CITY TO STATE TRANSITION")
    print("=" * 80)
    print("Testing the reported issue: After entering CITY, bot shows ADDRESS prompt instead of STATE prompt")
    print()
    
    # Run all tests
    tests = [
        ("Order From City Function Analysis", analyze_order_from_city_function),
        ("ConversationHandler States Check", check_conversation_handler_states),
        ("Global Handler Interference Check", check_global_handlers_interference),
        ("Handler Registration Order Check", check_handler_order),
        ("Step Sequence Check", check_step_sequence),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print('='*60)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print('='*80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Order flow should work correctly")
    else:
        print("⚠️ ISSUES DETECTED - Order flow may have problems")
        print("\nPOSSIBLE ROOT CAUSES:")
        
        # Analyze failed tests to suggest root causes
        failed_tests = [name for name, result in results if not result]
        
        if "Global Handler Interference Check" in failed_tests:
            print("- Global MessageHandler may be intercepting conversation messages")
            print("- Check if awaiting_topup_amount flag is properly cleared")
        
        if "Handler Registration Order Check" in failed_tests:
            print("- Handler registration order is incorrect")
            print("- ConversationHandler should be registered before global MessageHandlers")
        
        if "Order From City Function Analysis" in failed_tests:
            print("- order_from_city function implementation has issues")
            print("- Check prompt text, return value, and state saving")
        
        if "ConversationHandler States Check" in failed_tests:
            print("- ConversationHandler state mapping is incorrect")
            print("- Check FROM_CITY and FROM_STATE state configurations")
        
        if "Step Sequence Check" in failed_tests:
            print("- Step sequence prompts are inconsistent")
            print("- Check step numbering and prompt text in all functions")

if __name__ == "__main__":
    main()