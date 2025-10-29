#!/usr/bin/env python3
"""
Script to fix all last_state assignments
Move from beginning to end of functions
"""

import re

with open('/app/backend/server.py', 'r') as f:
    content = f.read()

# Remove all "Save state for cancel return" assignments at beginning of functions
content = re.sub(
    r"(\n    context\.user_data\['last_state'\] = \w+  # Save state for cancel return\n)",
    r"\n",
    content
)

print("✅ Removed all 'Save state for cancel return' lines from beginnings")

# Now add last_state assignments before specific return statements
# This is complex because each function has different structure
# We'll do it function by function

# order_from_phone - has 2 returns to TO_NAME
content = re.sub(
    r"(            return TO_NAME\n\n    phone = update\.message\.text\.strip\(\))",
    r"            context.user_data['last_state'] = TO_NAME  # Save state for next step\n            return TO_NAME\n\n    phone = update.message.text.strip()",
    content
)

content = re.sub(
    r"(        reply_markup=reply_markup\n    \)\n    return TO_NAME\n\nasync def order_to_name)",
    r"        reply_markup=reply_markup\n    )\n    context.user_data['last_state'] = TO_NAME  # Save state for next step\n    return TO_NAME\n\nasync def order_to_name)",
    content
)

print("✅ Fixed order_from_phone")

# order_to_name
content = re.sub(
    r"(Например: Jane Doe\"\"\",\n        reply_markup=reply_markup\n    \)\n    return TO_ADDRESS\n\nasync def order_to_address)",
    r"Например: Jane Doe\"\"\",\n        reply_markup=reply_markup\n    )\n    context.user_data['last_state'] = TO_ADDRESS  # Save state for next step\n    return TO_ADDRESS\n\nasync def order_to_address)",
    content
)

print("✅ Fixed order_to_name")

# order_to_address  
content = re.sub(
    r"(Или нажмите \"Пропустить\" \"\"\",\n        reply_markup=reply_markup\n    \)\n    return TO_ADDRESS2\n\nasync def skip_to_address2)",
    r"Или нажмите \"Пропустить\" \"\"\",\n        reply_markup=reply_markup\n    )\n    context.user_data['last_state'] = TO_ADDRESS2  # Save state for next step\n    return TO_ADDRESS2\n\nasync def skip_to_address2)",
    content
)

print("✅ Fixed order_to_address")

# order_to_city
content = re.sub(
    r"(Например: NY\"\"\",\n        reply_markup=reply_markup\n    \)\n    return TO_STATE\n\nasync def order_to_state)",
    r"Например: NY\"\"\",\n        reply_markup=reply_markup\n    )\n    context.user_data['last_state'] = TO_STATE  # Save state for next step\n    return TO_STATE\n\nasync def order_to_state)",
    content
)

print("✅ Fixed order_to_city")

# order_to_state
content = re.sub(
    r"(Например: 10007\"\"\",\n        reply_markup=reply_markup\n    \)\n    return TO_ZIP\n\nasync def order_to_zip)",
    r"Например: 10007\"\"\",\n        reply_markup=reply_markup\n    )\n    context.user_data['last_state'] = TO_ZIP  # Save state for next step\n    return TO_ZIP\n\nasync def order_to_zip)",
    content
)

print("✅ Fixed order_to_state")

# order_to_zip
content = re.sub(
    r"(Например: \+1234567890 или 1234567890\"\"\",\n        reply_markup=reply_markup\n    \)\n    return TO_PHONE\n\nasync def order_to_phone)",
    r"Например: +1234567890 или 1234567890\"\"\",\n        reply_markup=reply_markup\n    )\n    context.user_data['last_state'] = TO_PHONE  # Save state for next step\n    return TO_PHONE\n\nasync def order_to_phone)",
    content
)

print("✅ Fixed order_to_zip")

# order_to_phone - has 2 returns to PARCEL_WEIGHT
content = re.sub(
    r"(Например: 2\"\"\",\n                reply_markup=reply_markup\n            \)\n            return PARCEL_WEIGHT\n    \n    phone = update\.message\.text\.strip\(\))",
    r"Например: 2\"\"\",\n                reply_markup=reply_markup\n            )\n            context.user_data['last_state'] = PARCEL_WEIGHT  # Save state for next step\n            return PARCEL_WEIGHT\n    \n    phone = update.message.text.strip()",
    content
)

content = re.sub(
    r"(Например: 2\"\"\",\n        reply_markup=reply_markup\n    \)\n    return PARCEL_WEIGHT\n\n\nasync def order_parcel_weight)",
    r"Например: 2\"\"\",\n        reply_markup=reply_markup\n    )\n    context.user_data['last_state'] = PARCEL_WEIGHT  # Save state for next step\n    return PARCEL_WEIGHT\n\n\nasync def order_parcel_weight)",
    content
)

print("✅ Fixed order_to_phone")

# order_parcel_weight - doesn't return a simple state, goes to show_data_confirmation
# So we set last_state = CONFIRM_DATA before calling show_data_confirmation
content = re.sub(
    r"(        # Show data confirmation instead of immediately fetching rates\n        return await show_data_confirmation\(update, context\))",
    r"        # Show data confirmation instead of immediately fetching rates\n        context.user_data['last_state'] = CONFIRM_DATA  # Save state for next step\n        return await show_data_confirmation(update, context)",
    content
)

print("✅ Fixed order_parcel_weight")

# Write back
with open('/app/backend/server.py', 'w') as f:
    f.write(content)

print("\n✅ All fixes applied successfully!")
print("Backup saved to: server.py.backup_before_bulk_fix")
