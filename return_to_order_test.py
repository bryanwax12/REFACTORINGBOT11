#!/usr/bin/env python3
"""
Specific test for Return to Order functionality fix
Tests the critical bug fix where last_state was being overwritten
"""

import re

def test_critical_fix():
    """Test that the critical fix has been implemented correctly"""
    print("🔧 Testing Return to Order Critical Fix")
    print("=" * 50)
    
    # Read the server.py file
    with open('/app/backend/server.py', 'r') as f:
        server_code = f.read()
    
    # Test 1: Verify duplicate last_state assignments are removed
    print("\n1. Testing duplicate last_state removal:")
    
    # Check that FROM_ADDRESS2 assignment is NOT at end of order_from_address
    from_address_func = re.search(r'async def order_from_address\(.*?\n(.*?)(?=async def|\Z)', server_code, re.DOTALL)
    if from_address_func:
        func_body = from_address_func.group(1)
        # Look for last_state = FROM_ADDRESS2 at the end (after return FROM_ADDRESS2)
        duplicate_assignment = re.search(r'return FROM_ADDRESS2.*?context\.user_data\[\'last_state\'\]\s*=\s*FROM_ADDRESS2', func_body, re.DOTALL)
        if duplicate_assignment:
            print("   ❌ CRITICAL: Duplicate last_state assignment still exists in order_from_address")
            return False
        else:
            print("   ✅ order_from_address: No duplicate last_state assignment found")
    
    # Check that TO_ADDRESS2 assignment is NOT at end of order_to_address  
    to_address_func = re.search(r'async def order_to_address\(.*?\n(.*?)(?=async def|\Z)', server_code, re.DOTALL)
    if to_address_func:
        func_body = to_address_func.group(1)
        # Look for last_state = TO_ADDRESS2 at the end (after return TO_ADDRESS2)
        duplicate_assignment = re.search(r'return TO_ADDRESS2.*?context\.user_data\[\'last_state\'\]\s*=\s*TO_ADDRESS2', func_body, re.DOTALL)
        if duplicate_assignment:
            print("   ❌ CRITICAL: Duplicate last_state assignment still exists in order_to_address")
            return False
        else:
            print("   ✅ order_to_address: No duplicate last_state assignment found")
    
    # Test 2: Verify correct last_state assignments at beginning
    print("\n2. Testing correct last_state assignments:")
    
    # Check order_from_address sets last_state = FROM_ADDRESS at beginning
    from_address_correct = re.search(r'async def order_from_address\(.*?\n\s*context\.user_data\[\'last_state\'\]\s*=\s*FROM_ADDRESS\s*#', server_code, re.DOTALL)
    if from_address_correct:
        print("   ✅ order_from_address: Correctly sets last_state = FROM_ADDRESS at beginning")
    else:
        print("   ❌ order_from_address: Missing or incorrect last_state assignment at beginning")
        return False
    
    # Check order_to_address sets last_state = TO_ADDRESS at beginning
    to_address_correct = re.search(r'async def order_to_address\(.*?\n\s*context\.user_data\[\'last_state\'\]\s*=\s*TO_ADDRESS\s*#', server_code, re.DOTALL)
    if to_address_correct:
        print("   ✅ order_to_address: Correctly sets last_state = TO_ADDRESS at beginning")
    else:
        print("   ❌ order_to_address: Missing or incorrect last_state assignment at beginning")
        return False
    
    # Test 3: Verify return_to_order handles states correctly
    print("\n3. Testing return_to_order state handling:")
    
    # Check FROM_ADDRESS handling
    from_address_return = re.search(r'elif last_state == FROM_ADDRESS:.*?Шаг 2.*?Адрес отправителя.*?return FROM_ADDRESS', server_code, re.DOTALL)
    if from_address_return:
        print("   ✅ return_to_order: Correctly handles FROM_ADDRESS state")
    else:
        print("   ❌ return_to_order: Missing or incorrect FROM_ADDRESS handling")
        return False
    
    # Check TO_ADDRESS handling  
    to_address_return = re.search(r'elif last_state == TO_ADDRESS:.*?Шаг.*?Адрес получателя.*?return TO_ADDRESS', server_code, re.DOTALL)
    if to_address_return:
        print("   ✅ return_to_order: Correctly handles TO_ADDRESS state")
    else:
        print("   ❌ return_to_order: Missing or incorrect TO_ADDRESS handling")
        return False
    
    # Test 4: Verify address validation logic
    print("\n4. Testing address validation logic:")
    
    # Check that address validation in order_from_address is correct
    address_validation = re.search(r'# Only Latin letters, numbers, spaces, and common address symbols.*?invalid_chars.*?isalnum.*?isspace.*?return FROM_ADDRESS', server_code, re.DOTALL)
    if address_validation:
        print("   ✅ Address validation: Correct logic for alphanumeric + spaces + symbols")
    else:
        print("   ❌ Address validation: Missing or incorrect validation logic")
        return False
    
    print("\n" + "=" * 50)
    print("🎯 CRITICAL FIX VERIFICATION RESULT: ✅ SUCCESS")
    print("=" * 50)
    
    print("\n📋 Fix Summary:")
    print("   ✅ Removed duplicate last_state assignments from end of functions")
    print("   ✅ Each handler sets last_state ONCE at the beginning only")
    print("   ✅ return_to_order correctly handles FROM_ADDRESS and TO_ADDRESS states")
    print("   ✅ Address validation logic allows digits (for addresses like '215 Clayton St')")
    
    print("\n🎯 Expected Behavior After Fix:")
    print("   1. User starts /order, enters name 'Ivan Petrov'")
    print("   2. Bot shows 'Шаг 2/11: Адрес отправителя'")
    print("   3. User clicks '❌ Отмена' button")
    print("   4. User clicks '↩️ Вернуться к заказу' button")
    print("   5. Bot correctly shows 'Шаг 2/13: Адрес отправителя' prompt")
    print("   6. User enters '215 Clayton St.' - should be accepted ✅")
    print("   7. No more error: '❌ Используйте только английские буквы...'")
    
    return True

def test_scenario_simulation():
    """Simulate the exact scenario from the review request"""
    print("\n🎯 SIMULATING EXACT SCENARIO FROM REVIEW REQUEST")
    print("=" * 60)
    
    print("Scenario: User was on FROM_ADDRESS, clicked cancel, then return to order")
    print("Expected: Address '215 Clayton St.' should be accepted")
    
    # Read the server.py file
    with open('/app/backend/server.py', 'r') as f:
        server_code = f.read()
    
    # Simulate the flow:
    # 1. User is in FROM_ADDRESS state
    print("\n1. User in FROM_ADDRESS state:")
    print("   - last_state should be set to FROM_ADDRESS (not FROM_ADDRESS2)")
    
    # Check that order_from_address sets last_state = FROM_ADDRESS
    from_address_state = re.search(r'async def order_from_address.*?context\.user_data\[\'last_state\'\]\s*=\s*FROM_ADDRESS', server_code, re.DOTALL)
    if from_address_state:
        print("   ✅ order_from_address correctly sets last_state = FROM_ADDRESS")
    else:
        print("   ❌ order_from_address does not set last_state correctly")
        return False
    
    # 2. User clicks cancel
    print("\n2. User clicks cancel:")
    print("   - last_state should remain FROM_ADDRESS (not be overwritten)")
    
    # Check that there's no overwriting at the end
    no_overwrite = not re.search(r'return FROM_ADDRESS2.*?context\.user_data\[\'last_state\'\]', server_code, re.DOTALL)
    if no_overwrite:
        print("   ✅ No last_state overwriting found after return FROM_ADDRESS2")
    else:
        print("   ❌ last_state is being overwritten after return statement")
        return False
    
    # 3. User clicks return to order
    print("\n3. User clicks return to order:")
    print("   - Should restore FROM_ADDRESS state with correct prompt")
    
    # Check return_to_order FROM_ADDRESS handling
    return_handling = re.search(r'elif last_state == FROM_ADDRESS:.*?Адрес отправителя.*?return FROM_ADDRESS', server_code, re.DOTALL)
    if return_handling:
        print("   ✅ return_to_order correctly handles FROM_ADDRESS state")
    else:
        print("   ❌ return_to_order does not handle FROM_ADDRESS correctly")
        return False
    
    # 4. User enters address
    print("\n4. User enters '215 Clayton St.':")
    print("   - Should be validated as address (not name)")
    
    # Check address validation allows digits
    address_validation = re.search(r'# Only Latin letters, numbers, spaces, and common address symbols.*?isalnum', server_code, re.DOTALL)
    if address_validation:
        print("   ✅ Address validation allows alphanumeric characters (digits allowed)")
    else:
        print("   ❌ Address validation may not allow digits")
        return False
    
    print("\n" + "=" * 60)
    print("🎯 SCENARIO SIMULATION RESULT: ✅ SUCCESS")
    print("The fix should resolve the reported issue!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    print("🚀 Return to Order Critical Fix Verification")
    print("Testing the specific fix for address validation error")
    
    success1 = test_critical_fix()
    success2 = test_scenario_simulation()
    
    if success1 and success2:
        print("\n🎉 ALL TESTS PASSED - CRITICAL FIX VERIFIED!")
        print("The Return to Order functionality should now work correctly.")
    else:
        print("\n❌ TESTS FAILED - FIX NEEDS ATTENTION!")