#!/usr/bin/env python3
"""
Скрипт для перемещения установки last_state ПЕРЕД отправкой сообщения.
Проблема: last_state устанавливается только если bot_msg != None.
Решение: Установить last_state ДО отправки сообщения.
"""
import re

files = [
    '/app/backend/handlers/order_flow/parcel.py',
    '/app/backend/handlers/order_flow/to_address.py',
    '/app/backend/handlers/order_flow/from_address.py',
    '/app/backend/handlers/order_flow/confirmation.py',
    '/app/backend/handlers/order_flow/entry_points.py',
]

def fix_file(filepath):
    print(f"\n{'='*60}")
    print(f"Файл: {filepath}")
    print('='*60)
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    changes_made = 0
    
    # Паттерн: ищем блок где last_state внутри if bot_msg:
    pattern = r"(    bot_msg = await safe_telegram_call\([^)]+\))\n(    \n)?    if bot_msg:\n        context\.user_data\['last_bot_message_id'\] = bot_msg\.message_id\n        context\.user_data\['last_bot_message_text'\] = ([^\n]+)\n        context\.user_data\['last_state'\] = (STATE_NAMES\[\w+\])"
    
    def replacer(match):
        nonlocal changes_made
        changes_made += 1
        
        bot_msg_line = match.group(1)
        message_text_var = match.group(3)
        last_state_value = match.group(4)
        
        return f"""    # Save last_state BEFORE sending (so it's saved even if send fails)
    context.user_data['last_state'] = {last_state_value}
    context.user_data['last_bot_message_text'] = {message_text_var}
    
{bot_msg_line}
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id"""
    
    content = re.sub(pattern, replacer, content)
    
    if changes_made > 0:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Сделано {changes_made} изменений")
    else:
        print("✅ Изменений не требуется")
    
    return changes_made

total = 0
for f in files:
    total += fix_file(f)

print(f"\n{'='*60}")
print(f"✅ ВСЕГО: {total} изменений")
print('='*60)
