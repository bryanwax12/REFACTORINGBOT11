#!/usr/bin/env python3
"""
Simulate the City → State Transition Issue
This script simulates the exact scenario described in the review request
"""

import sys
import os
import re
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append('/app/backend')

def simulate_conversation_flow():
    """Simulate the conversation flow to identify the issue"""
    print("🔍 SIMULATING CONVERSATION FLOW...")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Simulate the flow step by step
        print("\n📋 STEP-BY-STEP FLOW SIMULATION:")
        
        # Step 1: User starts order creation
        print("1. User clicks 'Создать заказ' → new_order_start()")
        
        # Step 2: User enters name
        print("2. User enters name → order_from_name() → returns FROM_ADDRESS")
        
        # Step 3: User enters address
        print("3. User enters address → order_from_address() → returns FROM_ADDRESS2")
        
        # Step 4: User enters/skips address2
        print("4. User enters/skips address2 → order_from_address2() → returns FROM_CITY")
        
        # Step 5: User enters city (THIS IS WHERE THE ISSUE OCCURS)
        print("5. User enters city → order_from_city() → should return FROM_STATE")
        
        # Check what order_from_city actually returns
        city_pattern = r'async def order_from_city\(.*?\):(.*?)return (FROM_\w+)'
        city_match = re.search(city_pattern, server_code, re.DOTALL)
        
        if city_match:
            return_value = city_match.group(2)
            print(f"   ✅ order_from_city returns: {return_value}")
            
            if return_value == "FROM_STATE":
                print("   ✅ Correct return value")
            else:
                print(f"   ❌ WRONG return value! Should be FROM_STATE, got {return_value}")
        else:
            print("   ❌ Could not find order_from_city return value")
        
        # Step 6: Check what happens in FROM_STATE
        print("6. ConversationHandler should route to FROM_STATE → order_from_state()")
        
        # Check ConversationHandler mapping
        from_state_pattern = r'FROM_STATE:\s*\[(.*?)MessageHandler\([^,]+,\s*(\w+)\)'
        from_state_match = re.search(from_state_pattern, server_code, re.DOTALL)
        
        if from_state_match:
            handler_function = from_state_match.group(2)
            print(f"   ✅ FROM_STATE maps to: {handler_function}")
            
            if handler_function == "order_from_state":
                print("   ✅ Correct handler mapping")
            else:
                print(f"   ❌ WRONG handler! Should be order_from_state, got {handler_function}")
        else:
            print("   ❌ Could not find FROM_STATE handler mapping")
        
        # Check what order_from_state shows
        state_pattern = r'async def order_from_state\(.*?\):(.*?)message_text = """(.*?)"""'
        state_match = re.search(state_pattern, server_code, re.DOTALL)
        
        if state_match:
            state_prompt = state_match.group(2).strip().split('\n')[0]
            print(f"   ✅ order_from_state shows: '{state_prompt}'")
            
            if "Штат отправителя" in state_prompt:
                print("   ✅ Correct prompt for state input")
            else:
                print(f"   ❌ WRONG prompt! Should mention 'Штат отправителя'")
        else:
            print("   ❌ Could not find order_from_state prompt")
        
        return True
        
    except Exception as e:
        print(f"❌ Error simulating flow: {e}")
        return False

def check_potential_interference():
    """Check for potential interference scenarios"""
    print("\n🔍 CHECKING POTENTIAL INTERFERENCE SCENARIOS...")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Scenario 1: User opened balance top-up before creating order
        print("\n📋 SCENARIO 1: User opened balance top-up, then created order")
        
        # Check if order creation functions clear the awaiting_topup_amount flag
        order_new_pattern = r'async def order_new\(.*?\):(.*?)(?=async def|\Z)'
        order_new_match = re.search(order_new_pattern, server_code, re.DOTALL)
        
        if order_new_match:
            order_new_code = order_new_match.group(1)
            clears_flag = "context.user_data['awaiting_topup_amount'] = False" in order_new_code
            print(f"   order_new() clears awaiting_topup_amount: {'✅' if clears_flag else '❌'}")
        else:
            print("   ❌ order_new function not found")
        
        # Check start_order_with_template
        template_pattern = r'async def start_order_with_template\(.*?\):(.*?)(?=async def|\Z)'
        template_match = re.search(template_pattern, server_code, re.DOTALL)
        
        if template_match:
            template_code = template_match.group(1)
            clears_flag = "context.user_data['awaiting_topup_amount'] = False" in template_code
            print(f"   start_order_with_template() clears awaiting_topup_amount: {'✅' if clears_flag else '❌'}")
        else:
            print("   ❌ start_order_with_template function not found")
        
        # Scenario 2: Check if there are any other global handlers
        print("\n📋 SCENARIO 2: Other global handlers interference")
        
        # Find all global MessageHandler registrations
        global_handlers = re.findall(r'application\.add_handler\(MessageHandler\([^)]+\)\)', server_code)
        print(f"   Found {len(global_handlers)} global MessageHandler(s)")
        
        for i, handler in enumerate(global_handlers, 1):
            print(f"   {i}. {handler}")
        
        # Scenario 3: Check handler registration order
        print("\n📋 SCENARIO 3: Handler registration order")
        
        # Find the section where handlers are registered
        handler_section_start = server_code.find("application.add_handler(template_rename_handler)")
        handler_section_end = server_code.find("await application.initialize()")
        
        if handler_section_start != -1 and handler_section_end != -1:
            handler_section = server_code[handler_section_start:handler_section_end]
            
            # Check order of ConversationHandler vs global MessageHandler
            conv_handler_pos = handler_section.find("application.add_handler(order_conv_handler)")
            global_handler_pos = handler_section.find("MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topup_amount_input)")
            
            if conv_handler_pos != -1 and global_handler_pos != -1:
                correct_order = conv_handler_pos < global_handler_pos
                print(f"   ConversationHandler registered first: {'✅' if correct_order else '❌'}")
                
                if not correct_order:
                    print("   ⚠️ CRITICAL: Global handler registered before ConversationHandler!")
                    print("   This means global handler will intercept messages before conversation!")
            else:
                print("   ❌ Could not determine handler registration order")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking interference: {e}")
        return False

def analyze_user_reported_scenario():
    """Analyze the exact scenario reported by the user"""
    print("\n🔍 ANALYZING USER REPORTED SCENARIO...")
    
    print("📋 USER REPORT:")
    print("   - User is on step 4: 'Город отправителя' (FROM_CITY)")
    print("   - User enters city name")
    print("   - Bot shows 'Адрес отправителя' instead of 'Штат отправителя'")
    print("   - Expected: 'Шаг 5/13: Штат отправителя (2 буквы)'")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Check what could cause "Адрес отправителя" to be shown
        print("\n📋 POSSIBLE CAUSES ANALYSIS:")
        
        # Cause 1: order_from_city returns wrong state
        print("1. Checking if order_from_city returns wrong state...")
        city_return_pattern = r'async def order_from_city\(.*?\):(.*?)return (FROM_\w+)'
        city_return_match = re.search(city_return_pattern, server_code, re.DOTALL)
        
        if city_return_match:
            return_state = city_return_match.group(2)
            if return_state == "FROM_ADDRESS":
                print("   ❌ FOUND ISSUE: order_from_city returns FROM_ADDRESS!")
                print("   This would cause the bot to show address prompt instead of state prompt")
                return False
            elif return_state == "FROM_STATE":
                print("   ✅ order_from_city correctly returns FROM_STATE")
            else:
                print(f"   ⚠️ Unexpected return value: {return_state}")
        
        # Cause 2: Wrong handler mapping in ConversationHandler
        print("2. Checking ConversationHandler state mappings...")
        
        # Check if FROM_STATE maps to wrong function
        from_state_handler_pattern = r'FROM_STATE:\s*\[(.*?)MessageHandler\([^,]+,\s*(\w+)\)'
        from_state_handler_match = re.search(from_state_handler_pattern, server_code, re.DOTALL)
        
        if from_state_handler_match:
            handler_func = from_state_handler_match.group(2)
            if handler_func == "order_from_address":
                print("   ❌ FOUND ISSUE: FROM_STATE maps to order_from_address!")
                print("   This would show address prompt when expecting state prompt")
                return False
            elif handler_func == "order_from_state":
                print("   ✅ FROM_STATE correctly maps to order_from_state")
            else:
                print(f"   ⚠️ Unexpected handler function: {handler_func}")
        
        # Cause 3: Global handler interference
        print("3. Checking for global handler interference...")
        
        # Check if handle_topup_amount_input could be triggered
        topup_pattern = r'async def handle_topup_amount_input\(.*?\):(.*?)if not context\.user_data\.get\(\'awaiting_topup_amount\'\):(.*?)return'
        topup_match = re.search(topup_pattern, server_code, re.DOTALL)
        
        if topup_match:
            guard_section = topup_match.group(2)
            # Check if there's anything between the guard and return that could cause issues
            if guard_section.strip():
                print(f"   ⚠️ Code between guard clause and return: {guard_section.strip()}")
            else:
                print("   ✅ handle_topup_amount_input has proper guard clause")
        
        # Cause 4: Check if there's conditional logic in order_from_city
        print("4. Checking for conditional logic in order_from_city...")
        
        city_function_pattern = r'async def order_from_city\(.*?\):(.*?)(?=async def|\Z)'
        city_function_match = re.search(city_function_pattern, server_code, re.DOTALL)
        
        if city_function_match:
            city_function_code = city_function_match.group(1)
            
            # Check for multiple return statements
            return_statements = re.findall(r'return (FROM_\w+)', city_function_code)
            print(f"   Found {len(return_statements)} return statements: {return_statements}")
            
            if len(return_statements) > 1:
                print("   ⚠️ Multiple return statements found - check conditional logic")
                
                # Check for validation errors that return FROM_CITY
                validation_returns = city_function_code.count("return FROM_CITY")
                final_return = city_function_code.count("return FROM_STATE")
                
                print(f"   Validation error returns (FROM_CITY): {validation_returns}")
                print(f"   Success returns (FROM_STATE): {final_return}")
                
                if final_return == 0:
                    print("   ❌ FOUND ISSUE: No successful return to FROM_STATE!")
                    return False
            else:
                print("   ✅ Single return statement found")
        
        print("\n✅ No obvious issues found in code analysis")
        print("   The issue might be runtime-specific or related to user context")
        
        return True
        
    except Exception as e:
        print(f"❌ Error analyzing user scenario: {e}")
        return False

def main():
    """Main analysis function"""
    print("=" * 80)
    print("🔍 CITY → STATE TRANSITION ISSUE ANALYSIS")
    print("=" * 80)
    print("Analyzing the reported issue: Bot shows ADDRESS prompt instead of STATE prompt after city input")
    print()
    
    # Run analysis
    tests = [
        ("Conversation Flow Simulation", simulate_conversation_flow),
        ("Potential Interference Check", check_potential_interference),
        ("User Reported Scenario Analysis", analyze_user_reported_scenario),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"ANALYSIS: {test_name}")
        print('='*60)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Analysis failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 ANALYSIS SUMMARY")
    print('='*80)
    
    issues_found = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ NO ISSUES" if result else "❌ ISSUES FOUND"
        print(f"{status} - {test_name}")
        if not result:
            issues_found += 1
    
    if issues_found == 0:
        print("\n🎉 NO CODE ISSUES DETECTED")
        print("The problem might be:")
        print("- Runtime-specific (user context state)")
        print("- Race condition between handlers")
        print("- User following unexpected flow")
        print("- Browser/client-side caching")
        
        print("\n🔧 RECOMMENDED DEBUGGING STEPS:")
        print("1. Add logging to order_from_city function")
        print("2. Add logging to handle_topup_amount_input function")
        print("3. Check user context state when issue occurs")
        print("4. Verify ConversationHandler state transitions")
        
    else:
        print(f"\n⚠️ {issues_found} ISSUE(S) DETECTED")
        print("Review the analysis above for specific problems found.")

if __name__ == "__main__":
    main()