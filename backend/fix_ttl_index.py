"""
Script to fix TTL index on user_sessions collection
Drops old index and creates new one with TTL
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

async def fix_ttl_index():
    # Connect to MongoDB
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    
    # Auto-select database
    webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
    if 'crypto-shipping.emergent.host' in webhook_base_url:
        db_name = os.environ.get('DB_NAME_PRODUCTION', 'async-tg-bot-telegram_shipping_bot')
        print(f"🟢 PRODUCTION DATABASE: {db_name}")
    else:
        db_name = os.environ.get('DB_NAME_PREVIEW', os.environ.get('DB_NAME', 'telegram_shipping_bot'))
        print(f"🔵 PREVIEW DATABASE: {db_name}")
    
    db = client[db_name]
    sessions = db['user_sessions']
    
    print("\n📊 Current indexes:")
    indexes = await sessions.list_indexes().to_list(100)
    for idx in indexes:
        print(f"  - {idx}")
    
    # Drop old timestamp index (without TTL)
    try:
        print("\n🗑️ Dropping old timestamp index...")
        await sessions.drop_index("timestamp_1")
        print("✅ Old index dropped")
    except Exception as e:
        print(f"⚠️ Could not drop index (might not exist): {e}")
    
    # Create new index with TTL
    try:
        print("\n🆕 Creating new TTL index...")
        await sessions.create_index("timestamp", expireAfterSeconds=900)
        print("✅ TTL index created (expires after 15 minutes)")
    except Exception as e:
        print(f"❌ Error creating TTL index: {e}")
    
    print("\n📊 Updated indexes:")
    indexes = await sessions.list_indexes().to_list(100)
    for idx in indexes:
        print(f"  - {idx}")
    
    # Check if TTL is working
    ttl_index = None
    for idx in indexes:
        if 'timestamp' in idx.get('key', {}):
            ttl_index = idx
            break
    
    if ttl_index and 'expireAfterSeconds' in ttl_index:
        print(f"\n✅ SUCCESS! TTL index active: expires after {ttl_index['expireAfterSeconds']} seconds")
    else:
        print("\n❌ WARNING: TTL index not found or not configured properly")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(fix_ttl_index())
