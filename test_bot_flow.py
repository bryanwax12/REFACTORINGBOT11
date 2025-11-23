#!/usr/bin/env python3
"""
Скрипт для мониторинга логов бота в реальном времени
Используется для отладки дублирования сообщений
"""
import subprocess
import sys
import re
from datetime import datetime

def monitor_logs():
    """Мониторинг логов бота для отслеживания дублирования"""
    
    print("=" * 80)
    print("🔍 МОНИТОРИНГ ЛОГОВ БОТА")
    print("=" * 80)
    print("📋 Инструкция:")
    print("   1. Запустите этот скрипт")
    print("   2. Откройте бота в Telegram")
    print("   3. Начните создание нового заказа (/neworder)")
    print("   4. Следите за логами ниже")
    print("=" * 80)
    print()
    
    # Паттерны для поиска
    patterns = {
        'handler_start': re.compile(r'▶️.*user=(\d+).*calling handler'),
        'handler_end': re.compile(r'✅.*user=(\d+).*Handler completed.*state=(\w+)'),
        'message_sent': re.compile(r'Шаг (\d+)/(\d+)'),
        'session_check': re.compile(r'SESSION CHECK.*user=(\d+)'),
        'persistence': re.compile(r'Restored (\d+) user data items from MongoDB'),
    }
    
    # Счетчики для отслеживания дублей
    message_counter = {}
    handler_counter = {}
    
    try:
        # Следим за логами в реальном времени
        process = subprocess.Popen(
            ['tail', '-f', '/var/log/supervisor/backend.err.log'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("🟢 Мониторинг начат. Нажмите Ctrl+C для остановки.\n")
        
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # Проверяем на паттерны
            if patterns['persistence'].search(line):
                match = patterns['persistence'].search(line)
                items = match.group(1)
                print(f"[{timestamp}] 📥 PERSISTENCE: Restored {items} items from MongoDB")
                print(f"   ⚠️ WARNING: Это должно происходить ТОЛЬКО через MongoDBPersistence!")
            
            if patterns['session_check'].search(line):
                match = patterns['session_check'].search(line)
                user_id = match.group(1)
                print(f"[{timestamp}] 🔍 DECORATOR: Session check for user={user_id}")
            
            if patterns['handler_start'].search(line):
                match = patterns['handler_start'].search(line)
                user_id = match.group(1)
                
                # Счетчик для отслеживания дублирования вызовов хендлера
                key = f"{user_id}:{timestamp[:5]}"  # Группируем по минуте
                handler_counter[key] = handler_counter.get(key, 0) + 1
                
                count_str = f" (#{handler_counter[key]})" if handler_counter[key] > 1 else ""
                print(f"[{timestamp}] ▶️ HANDLER START: user={user_id}{count_str}")
                
                if handler_counter[key] > 1:
                    print(f"   🚨 ДУБЛИРОВАНИЕ: Handler вызван {handler_counter[key]} раз!")
            
            if patterns['handler_end'].search(line):
                match = patterns['handler_end'].search(line)
                user_id, state = match.groups()
                print(f"[{timestamp}] ✅ HANDLER END: user={user_id}, state={state}")
            
            if patterns['message_sent'].search(line):
                match = patterns['message_sent'].search(line)
                step_num, total = match.groups()
                
                # Счетчик для отслеживания дублирования сообщений
                msg_key = f"step_{step_num}:{timestamp[:5]}"  # Группируем по минуте
                message_counter[msg_key] = message_counter.get(msg_key, 0) + 1
                
                count_str = f" (#{message_counter[msg_key]})" if message_counter[msg_key] > 1 else ""
                print(f"[{timestamp}] 💬 MESSAGE: Шаг {step_num}/{total}{count_str}")
                
                if message_counter[msg_key] > 1:
                    print(f"   🚨 ДУБЛИРОВАНИЕ: Сообщение отправлено {message_counter[msg_key]} раз!")
            
    except KeyboardInterrupt:
        print("\n\n🛑 Мониторинг остановлен.")
        process.terminate()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    monitor_logs()
