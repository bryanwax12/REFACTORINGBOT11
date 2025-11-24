#!/usr/bin/env python3
"""
Script to clear MongoDB collections
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def clear_database():
    # Get MongoDB URL
    mongo_url = os.getenv('MONGO_URL')
    if not mongo_url:
        print("❌ MONGO_URL not found in environment")
        return
    
    print(f"🔗 Connecting to MongoDB...")
    print(f"   URL: {mongo_url[:50]}...")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongo_url)
    
    # Get database (will use default database from URL or create new one)
    db = client.get_default_database()
    db_name = db.name
    
    print(f"📊 Database: {db_name}")
    
    # List all collections
    collections = await db.list_collection_names()
    print(f"📋 Found {len(collections)} collections:")
    for col in collections:
        print(f"   - {col}")
    
    # Ask for confirmation
    print("\n⚠️  WARNING: This will DELETE ALL DATA from these collections!")
    response = input("Type 'YES' to confirm deletion: ")
    
    if response != 'YES':
        print("❌ Cancelled. No data was deleted.")
        return
    
    # Drop all collections
    print("\n🗑️  Deleting collections...")
    for collection_name in collections:
        await db.drop_collection(collection_name)
        print(f"   ✅ Deleted: {collection_name}")
    
    print(f"\n✅ Database '{db_name}' cleared successfully!")
    print("🔄 The collections will be recreated automatically when the bot starts.")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(clear_database())
