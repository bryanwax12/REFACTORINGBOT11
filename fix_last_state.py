#!/usr/bin/env python3
"""
Script to fix last_state assignments in server.py
Move last_state from beginning of functions to end (before return)
"""

# Mapping of which function returns which next state
FUNCTION_RETURNS = {
    'order_from_zip': 'FROM_PHONE',
    'order_from_phone': 'TO_NAME',
    'order_to_name': 'TO_ADDRESS',
    'order_to_address': 'TO_ADDRESS2',
    'order_to_city': 'TO_STATE',
    'order_to_state': 'TO_ZIP',
    'order_to_zip': 'TO_PHONE',
    'order_to_phone': 'PARCEL_WEIGHT',
    'order_parcel_weight': None,  # Goes to show_data_confirmation, not a simple state
}

# Lines to remove (beginning of function assignments)
LINES_TO_REMOVE = [
    (746, "    context.user_data['last_state'] = FROM_ZIP  # Save state for cancel return"),
    (775, "    context.user_data['last_state'] = FROM_PHONE  # Save state for cancel return"),
    (828, "    context.user_data['last_state'] = TO_NAME  # Save state for cancel return"),
    (863, "    context.user_data['last_state'] = TO_ADDRESS  # Save state for cancel return"),
    (945, "    context.user_data['last_state'] = TO_CITY  # Save state for cancel return"),
    (980, "    context.user_data['last_state'] = TO_STATE  # Save state for cancel return"),
    (1019, "    context.user_data['last_state'] = TO_ZIP  # Save state for cancel return"),
    (1048, "    context.user_data['last_state'] = TO_PHONE  # Save state for cancel return"),
    (1101, "    context.user_data['last_state'] = PARCEL_WEIGHT  # Save state for cancel return"),
]

print("This script needs manual implementation due to complexity.")
print("Each function has different structure and return patterns.")
print("\nPlease manually fix each function by:")
print("1. Removing last_state assignment from the beginning")
print("2. Adding last_state = <NEXT_STATE> before the final return statement")
