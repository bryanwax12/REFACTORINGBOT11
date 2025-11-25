#!/usr/bin/env python3
"""
MongoDB Connection Verification Script
This script verifies connection to existing MongoDB Atlas cluster
Used instead of migration for external MongoDB
"""
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def verify_connection():
    """Verify MongoDB connection"""
    try:
        mongo_url = os.environ.get('MONGO_URL', '')
        db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
        
        print(f"[VERIFY] Connecting to MongoDB...")
        print(f"[VERIFY] Database: {db_name}")
        
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Test connection
        await db.command('ping')
        
        print(f"[VERIFY] ✅ MongoDB connection successful!")
        print(f"[VERIFY] ✅ Database '{db_name}' is accessible")
        
        # List collections
        collections = await db.list_collection_names()
        print(f"[VERIFY] ✅ Found {len(collections)} collections")
        
        client.close()
        return 0
        
    except Exception as e:
        print(f"[VERIFY] ❌ MongoDB connection failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(verify_connection())
    sys.exit(exit_code)
