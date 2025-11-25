#!/usr/bin/env python3
"""Set API mode in database"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def set_test_mode():
    mongo_url = os.getenv('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client.telegram_shipping_bot
    
    # Установить режим "test"
    result = await db.settings.update_one(
        {'key': 'api_mode'},
        {'$set': {'value': 'test'}},
        upsert=True
    )
    
    print('✅ API режим установлен в БД: TEST')
    print(f'   Matched: {result.matched_count}, Modified: {result.modified_count}')
    
    # Проверка
    setting = await db.settings.find_one({'key': 'api_mode'})
    print(f'   Текущее значение в БД: {setting}')
    print()
    print('Теперь будет использоваться ключ SHIPSTATION_API_KEY_TEST')
    
    client.close()

if __name__ == "__main__":
    asyncio.run(set_test_mode())
