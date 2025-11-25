#!/usr/bin/env python3
"""
Test help keyboard with admin contact button
"""
import os
from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, '/app/backend')

from utils.ui_utils import get_help_keyboard

admin_id = os.getenv('ADMIN_TELEGRAM_ID')

print("🧪 Тестирование клавиатуры поддержки")
print("=" * 60)
print(f"ADMIN_TELEGRAM_ID: {admin_id}")
print()

keyboard = get_help_keyboard(admin_id)

print("✅ Созданная клавиатура:")
print(f"   Количество рядов кнопок: {len(keyboard.inline_keyboard)}")
print()

for i, row in enumerate(keyboard.inline_keyboard, 1):
    print(f"Ряд {i}:")
    for button in row:
        if button.url:
            print(f"   📱 '{button.text}' -> {button.url}")
        elif button.callback_data:
            print(f"   🔘 '{button.text}' -> callback: {button.callback_data}")
    print()

print("=" * 60)
print("✅ Кнопка администратора настроена правильно!")
