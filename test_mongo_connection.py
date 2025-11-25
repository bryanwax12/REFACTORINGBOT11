#!/usr/bin/env python3
"""Test MongoDB Atlas connection"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_connection():
    # Test credentials
    username = "bbeardy3_db_user"
    password = "HDkwF46d6rKW4riu"
    cluster = "cluster1.lfw3fr.mongodb.net"
    database = "telegram_shipping_bot"
    
    connection_string = f"mongodb+srv://{username}:{password}@{cluster}/{database}?appName=Cluster1&retryWrites=true&w=majority"
    
    print(f"Testing connection to: {cluster}")
    print(f"Username: {username}")
    print(f"Database: {database}")
    print(f"Connection string: mongodb+srv://{username}:***@{cluster}/...")
    print()
    
    try:
        client = AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=10000)
        
        # Test ping
        print("Testing ping...")
        result = await client.admin.command('ping')
        print(f"✅ Ping successful: {result}")
        
        # Test database access
        print("\nTesting database access...")
        db = client[database]
        
        # List collections
        print("Listing collections...")
        collections = await db.list_collection_names()
        print(f"✅ Collections: {collections}")
        
        # Test write
        print("\nTesting write access...")
        test_collection = db.test_connection
        insert_result = await test_collection.insert_one({"test": "connection", "timestamp": "now"})
        print(f"✅ Insert successful: {insert_result.inserted_id}")
        
        # Test read
        print("\nTesting read access...")
        doc = await test_collection.find_one({"_id": insert_result.inserted_id}, {"_id": 0})
        print(f"✅ Read successful: {doc}")
        
        # Cleanup
        await test_collection.delete_one({"_id": insert_result.inserted_id})
        print("\n✅ All tests passed!")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print(f"\nError type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)
