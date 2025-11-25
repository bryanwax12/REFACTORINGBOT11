#!/usr/bin/env python3
"""Simple MongoDB Atlas connection test"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_simple():
    username = "bbeardy3_db_user"
    password = "vSGSbgmaKDhC3ZIz"
    cluster = "cluster1.lfw3fr.mongodb.net"
    
    # Test without database name in connection string
    connection_string = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority"
    
    print(f"Testing connection without database name...")
    print(f"Username: {username}")
    print(f"Cluster: {cluster}")
    print()
    
    try:
        client = AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=10000)
        
        # Test admin.ping
        print("Testing admin.ping...")
        result = await client.admin.command('ping')
        print(f"✅ Ping successful: {result}")
        
        # List databases
        print("\nListing databases...")
        db_list = await client.list_database_names()
        print(f"✅ Databases: {db_list}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Try with authSource=admin explicitly
        print("\n" + "="*50)
        print("Trying with authSource=admin explicitly...")
        print("="*50)
        
        connection_string2 = f"mongodb+srv://{username}:{password}@{cluster}/?authSource=admin&retryWrites=true&w=majority"
        
        try:
            client2 = AsyncIOMotorClient(connection_string2, serverSelectionTimeoutMS=10000)
            result = await client2.admin.command('ping')
            print(f"✅ Ping successful with authSource=admin: {result}")
            client2.close()
            return True
        except Exception as e2:
            print(f"❌ Still failed: {e2}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_simple())
    exit(0 if success else 1)
