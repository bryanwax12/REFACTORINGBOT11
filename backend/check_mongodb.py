#!/usr/bin/env python3
"""
Script to check MongoDB connection and collections
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def check_database():
    mongo_url = os.getenv('MONGO_URL')
    print(f"🔗 Connecting to MongoDB...")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client.get_default_database()
    
    print(f"📊 Database: {db.name}")
    
    # List collections
    collections = await db.list_collection_names()
    print(f"📋 Collections ({len(collections)}):")
    for col in collections:
        count = await db[col].count_documents({})
        print(f"   - {col}: {count} documents")
    
    # Test insert
    print("\n🧪 Testing insert into 'users' collection...")
    result = await db.users.insert_one({
        "telegram_id": 123456789,
        "username": "test_user",
        "balance": 0
    })
    print(f"   ✅ Inserted document with ID: {result.inserted_id}")
    
    # Test read
    user = await db.users.find_one({"telegram_id": 123456789})
    print(f"   ✅ Read document: {user}")
    
    # Clean up test
    await db.users.delete_one({"telegram_id": 123456789})
    print(f"   ✅ Cleaned up test document")
    
    print("\n✅ MongoDB connection working correctly!")
    client.close()

if __name__ == "__main__":
    asyncio.run(check_database())
