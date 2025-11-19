#!/usr/bin/env python3
"""
Скрипт для исправления last_state во всех order flow handlers.
Проблема: last_state сохраняет СЛЕДУЮЩИЙ шаг вместо ТЕКУЩЕГО.
Решение: Изменить last_state чтобы он указывал на текущий шаг, где показывается сообщение.
"""
import re
import os

# Файлы для обработки
files = [
    '/app/backend/handlers/order_flow/parcel.py',
    '/app/backend/handlers/order_flow/to_address.py',
    '/app/backend/handlers/order_flow/from_address.py',
    '/app/backend/handlers/order_flow/payment.py',
    '/app/backend/handlers/order_flow/confirmation.py',
    '/app/backend/handlers/order_flow/skip_handlers.py',
    '/app/backend/handlers/order_flow/entry_points.py',
]

def fix_file(filepath):
    """Исправляет last_state в файле"""
    print(f"\n{'='*60}")
    print(f"Обработка: {filepath}")
    print('='*60)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changes = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Ищем строку с last_state
        if "context.user_data['last_state'] = STATE_NAMES[" in line:
            match = re.search(r"STATE_NAMES\[(\w+)\]", line)
            if match:
                current_state = match.group(1)
                
                # Ищем return statement в следующих 5 строках
                for j in range(i+1, min(i+6, len(lines))):
                    return_match = re.search(r"return (\w+)", lines[j])
                    if return_match:
                        return_state = return_match.group(1)
                        
                        # Найдем имя функции
                        func_start = i
                        while func_start > 0:
                            if 'async def ' in lines[func_start] or 'def ' in lines[func_start]:
                                break
                            func_start -= 1
                        
                        func_name = ''
                        if func_start >= 0:
                            func_match = re.search(r'def (\w+)', lines[func_start])
                            if func_match:
                                func_name = func_match.group(1)
                        
                        print(f"  Строка {i+1}: last_state={current_state}, return={return_state}, func={func_name}")
                        
                        if current_state == return_state:
                            print(f"    ✅ Правильно")
                        else:
                            print(f"    ⚠️  Исправляем: {current_state} → {return_state}")
                            changes.append({
                                'line': i,
                                'old': current_state,
                                'new': return_state,
                                'func': func_name
                            })
                        break
        i += 1
    
    # Применяем изменения
    if changes:
        print(f"\n🔧 Применение {len(changes)} изменений...")
        for change in changes:
            line_idx = change['line']
            old_line = lines[line_idx]
            new_line = old_line.replace(
                f"STATE_NAMES[{change['old']}]",
                f"STATE_NAMES[{change['new']}]"
            )
            lines[line_idx] = new_line
            print(f"  ✅ {change['func']}: {change['old']} → {change['new']}")
        
        new_content = '\n'.join(lines)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return len(changes)
    else:
        print("✅ Изменений не требуется")
        return 0

# Обрабатываем все файлы
total_changes = 0
for filepath in files:
    if os.path.exists(filepath):
        changes = fix_file(filepath)
        total_changes += changes

print(f"\n{'='*60}")
print(f"✅ ЗАВЕРШЕНО: {total_changes} изменений")
print('='*60)
