"""
Test state validation with ASCII check
"""
from utils.validation import validate_state

# Test cases
test_cases = [
    ("CA", True, "Valid ASCII state code"),
    ("NY", True, "Valid ASCII state code"),
    ("TX", True, "Valid ASCII state code"),
    ("ca", True, "Valid lowercase (will be uppercased)"),
    ("СА", False, "Cyrillic CA - should fail"),
    ("СФ", False, "Cyrillic SF - should fail"),
    ("AB1", False, "Contains digit"),
    ("A", False, "Too short"),
    ("ABC", False, "Too long"),
    ("12", False, "Only digits"),
    ("", False, "Empty string"),
]

print("🧪 Testing state validation with ASCII check\n")
print("=" * 70)

for state, should_pass, description in test_cases:
    is_valid, error_msg = validate_state(state)
    
    # Check if result matches expectation
    if (is_valid == should_pass):
        status = "✅ PASS"
    else:
        status = "❌ FAIL"
    
    print(f"\n{status} | Input: '{state}' | {description}")
    print(f"   Expected: {'Valid' if should_pass else 'Invalid'} | Got: {'Valid' if is_valid else 'Invalid'}")
    
    if not is_valid:
        print(f"   Error message: {error_msg.replace(chr(10), ' ')[:100]}")

print("\n" + "=" * 70)
print("\n✅ Test completed!\n")
