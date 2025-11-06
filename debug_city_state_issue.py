#!/usr/bin/env python3
"""
Debug the specific City → State issue reported by user
"""

import sys
import os
import re
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append('/app/backend')

def analyze_last_state_timing():
    """Analyze when last_state is set in each function"""
    print("🔍 ANALYZING LAST_STATE TIMING IN ORDER FUNCTIONS...")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Functions to check
        functions_to_check = [
            'order_from_name',
            'order_from_address', 
            'order_from_address2',
            'order_from_city',
            'order_from_state'
        ]
        
        print("\n📋 LAST_STATE SETTING ANALYSIS:")
        
        for func_name in functions_to_check:
            print(f"\n{func_name}:")
            
            # Find the function
            pattern = rf'async def {func_name}\(.*?\):(.*?)(?=async def|\Z)'
            match = re.search(pattern, server_code, re.DOTALL)
            
            if not match:
                print(f"   ❌ Function not found")
                continue
            
            function_code = match.group(1)
            
            # Find all last_state assignments
            last_state_assignments = re.findall(r"context\.user_data\['last_state'\]\s*=\s*(\w+)", function_code)
            
            # Find return statements
            return_statements = re.findall(r'return (\w+)', function_code)
            
            # Find message_text assignments (to see what prompt is shown)
            message_patterns = re.findall(r'message_text = """(.*?)"""', function_code, re.DOTALL)
            
            print(f"   last_state assignments: {last_state_assignments}")
            print(f"   return statements: {return_statements}")
            
            if message_patterns:
                first_line = message_patterns[0].strip().split('\n')[0]
                print(f"   shows prompt: '{first_line}'")
            
            # Check timing - is last_state set BEFORE or AFTER showing the prompt?
            if last_state_assignments and message_patterns:
                # Find positions
                last_state_pos = function_code.find(f"context.user_data['last_state'] = {last_state_assignments[0]}")
                message_pos = function_code.find('message_text = """')
                
                if last_state_pos > message_pos:
                    print(f"   ✅ last_state set AFTER showing prompt (correct)")
                else:
                    print(f"   ⚠️ last_state set BEFORE showing prompt")
            
            # Check if there are validation returns that might interfere
            validation_returns = [ret for ret in return_statements if ret != last_state_assignments[0] if last_state_assignments]
            if validation_returns:
                print(f"   validation returns: {validation_returns}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error analyzing last_state timing: {e}")
        return False

def check_specific_user_scenario():
    """Check the specific scenario reported by the user"""
    print("\n🔍 CHECKING SPECIFIC USER SCENARIO...")
    
    print("📋 USER SCENARIO:")
    print("1. User is on step 4: 'Город отправителя' (FROM_CITY state)")
    print("2. User enters city name (e.g., 'New York')")
    print("3. Bot should show: 'Шаг 5/13: Штат отправителя (2 буквы)'")
    print("4. But user sees: 'Адрес отправителя' instead")
    
    try:
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        print("\n📋 STEP-BY-STEP ANALYSIS:")
        
        # Step 1: Check what happens when user is in FROM_CITY state
        print("1. User in FROM_CITY state - what function handles text input?")
        
        # Find FROM_CITY handler in ConversationHandler
        from_city_pattern = r'FROM_CITY:\s*\[(.*?)MessageHandler\([^,]+,\s*(\w+)\)'
        from_city_match = re.search(from_city_pattern, server_code, re.DOTALL)
        
        if from_city_match:
            handler_func = from_city_match.group(2)
            print(f"   ✅ FROM_CITY text input handled by: {handler_func}")
        else:
            print(f"   ❌ FROM_CITY handler not found")
            return False
        
        # Step 2: Check what order_from_city does
        print("2. What does order_from_city do when user enters valid city?")
        
        city_pattern = r'async def order_from_city\(.*?\):(.*?)(?=async def|\Z)'
        city_match = re.search(city_pattern, server_code, re.DOTALL)
        
        if city_match:
            city_code = city_match.group(1)
            
            # Find the success path (after validation)
            success_pattern = r"context\.user_data\['from_city'\] = city(.*?)return (\w+)"
            success_match = re.search(success_pattern, city_code, re.DOTALL)
            
            if success_match:
                success_code = success_match.group(1)
                return_value = success_match.group(2)
                
                print(f"   Success path returns: {return_value}")
                
                # Check what prompt is shown
                prompt_pattern = r'message_text = """(.*?)"""'
                prompt_match = re.search(prompt_pattern, success_code, re.DOTALL)
                
                if prompt_match:
                    prompt_text = prompt_match.group(1).strip().split('\n')[0]
                    print(f"   Shows prompt: '{prompt_text}'")
                    
                    if "Штат отправителя" in prompt_text:
                        print(f"   ✅ Correct prompt for state input")
                    else:
                        print(f"   ❌ Wrong prompt! Expected 'Штат отправителя'")
                        return False
                else:
                    print(f"   ❌ No prompt found in success path")
                    return False
            else:
                print(f"   ❌ Success path not found")
                return False
        else:
            print(f"   ❌ order_from_city function not found")
            return False
        
        # Step 3: Check what happens next - does FROM_STATE get handled correctly?
        print("3. What happens when ConversationHandler receives FROM_STATE?")
        
        from_state_pattern = r'FROM_STATE:\s*\[(.*?)MessageHandler\([^,]+,\s*(\w+)\)'
        from_state_match = re.search(from_state_pattern, server_code, re.DOTALL)
        
        if from_state_match:
            state_handler_func = from_state_match.group(2)
            print(f"   ✅ FROM_STATE text input handled by: {state_handler_func}")
            
            if state_handler_func == "order_from_state":
                print(f"   ✅ Correct handler for state input")
            else:
                print(f"   ❌ Wrong handler! Expected 'order_from_state', got '{state_handler_func}'")
                return False
        else:
            print(f"   ❌ FROM_STATE handler not found")
            return False
        
        # Step 4: Check if there could be interference
        print("4. Could there be interference from other handlers?")
        
        # Check if there are any global handlers that might intercept
        global_handlers = re.findall(r'application\.add_handler\(MessageHandler\([^)]+\)\)', server_code)
        
        if global_handlers:
            print(f"   ⚠️ Found {len(global_handlers)} global MessageHandler(s):")
            for i, handler in enumerate(global_handlers, 1):
                print(f"      {i}. {handler}")
                
                # Check if it's the topup handler
                if "handle_topup_amount_input" in handler:
                    print(f"         This is the topup handler - checking guard clause...")
                    
                    # Check guard clause
                    topup_pattern = r'async def handle_topup_amount_input\(.*?\):(.*?)if not context\.user_data\.get\(\'awaiting_topup_amount\'\):(.*?)return'
                    topup_match = re.search(topup_pattern, server_code, re.DOTALL)
                    
                    if topup_match:
                        print(f"         ✅ Has guard clause - should not interfere")
                    else:
                        print(f"         ❌ No proper guard clause - could interfere!")
                        return False
        else:
            print(f"   ✅ No global MessageHandlers found")
        
        print("\n✅ ANALYSIS COMPLETE - No obvious code issues found")
        print("The issue might be:")
        print("- Runtime state corruption")
        print("- Race condition")
        print("- User context not being preserved correctly")
        print("- Specific user flow that's not covered")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking user scenario: {e}")
        return False

def suggest_debugging_approach():
    """Suggest debugging approach for this issue"""
    print("\n🔧 SUGGESTED DEBUGGING APPROACH:")
    
    print("\n1. ADD LOGGING TO KEY FUNCTIONS:")
    print("   - Add logging to order_from_city function entry and exit")
    print("   - Log the return value and last_state setting")
    print("   - Add logging to handle_topup_amount_input to see if it's being called")
    
    print("\n2. ADD CONTEXT LOGGING:")
    print("   - Log context.user_data contents at key points")
    print("   - Log awaiting_topup_amount flag status")
    print("   - Log conversation state transitions")
    
    print("\n3. TEST SPECIFIC SCENARIOS:")
    print("   - Test normal order flow (no balance top-up)")
    print("   - Test order flow after opening balance top-up")
    print("   - Test template-based order creation")
    print("   - Test cancel/return to order flow")
    
    print("\n4. CHECK FOR RACE CONDITIONS:")
    print("   - Multiple bot instances running")
    print("   - Concurrent message processing")
    print("   - State corruption between requests")
    
    print("\n5. VERIFY HANDLER REGISTRATION ORDER:")
    print("   - Ensure ConversationHandler is registered before global handlers")
    print("   - Check handler priority and filtering")

def main():
    """Main debug function"""
    print("=" * 80)
    print("🐛 DEBUG: CITY → STATE TRANSITION ISSUE")
    print("=" * 80)
    print("Debugging the reported issue: Bot shows ADDRESS prompt instead of STATE prompt")
    print()
    
    # Run analysis
    tests = [
        ("Last State Timing Analysis", analyze_last_state_timing),
        ("Specific User Scenario Check", check_specific_user_scenario),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"DEBUG: {test_name}")
        print('='*60)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Debug failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary and suggestions
    suggest_debugging_approach()
    
    print(f"\n{'='*80}")
    print("📊 DEBUG SUMMARY")
    print('='*80)
    
    issues_found = 0
    for test_name, result in results:
        status = "✅ NO ISSUES" if result else "❌ ISSUES FOUND"
        print(f"{status} - {test_name}")
        if not result:
            issues_found += 1
    
    if issues_found == 0:
        print("\n🎯 CONCLUSION:")
        print("No obvious code issues found. The problem is likely runtime-specific.")
        print("Recommend adding logging and testing specific user scenarios.")
    else:
        print(f"\n⚠️ FOUND {issues_found} ISSUE(S)")
        print("Review the analysis above for specific problems.")

if __name__ == "__main__":
    main()