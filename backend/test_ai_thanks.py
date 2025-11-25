#!/usr/bin/env python3
"""
Test AI thank you message generation
"""
import asyncio
import sys
import os
sys.path.insert(0, '/app/backend')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

print(f"🔑 EMERGENT_LLM_KEY в окружении: {bool(os.getenv('EMERGENT_LLM_KEY'))}")
print()

from utils.telegram_utils import generate_thank_you_message

async def test():
    print("🧪 Тестирование AI-генерации благодарственных сообщений...")
    print("=" * 70)
    print()
    
    for i in range(3):
        print(f"Попытка {i+1}/3:")
        try:
            message = await generate_thank_you_message()
            print(f"✅ Успешно!")
            print(f"📝 Сообщение: {message}")
            print()
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print()
    
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test())
