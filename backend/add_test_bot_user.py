#!/usr/bin/env python3
"""
Script to add test bot as a user in admin panel
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

async def add_test_bot():
    mongo_url = os.getenv('MONGO_URL')
    print(f"🔗 Connecting to MongoDB...")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client.get_default_database()
    
    # Test bot info
    test_bot_telegram_id = 8560388458  # This is the bot's telegram ID from token
    test_bot_username = "whitelabel_shipping_bot_test_bot"
    
    # Check if user already exists
    existing_user = await db.users.find_one({"telegram_id": test_bot_telegram_id})
    
    if existing_user:
        print(f"⚠️  User already exists: {existing_user}")
        response = input("Update existing user? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled")
            client.close()
            return
        
        # Update existing user
        await db.users.update_one(
            {"telegram_id": test_bot_telegram_id},
            {"$set": {
                "username": test_bot_username,
                "balance": 1000.0,  # Give test bot some balance
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        print(f"✅ Updated user: @{test_bot_username}")
    else:
        # Create new user
        user_doc = {
            "telegram_id": test_bot_telegram_id,
            "username": test_bot_username,
            "first_name": "Test Bot",
            "last_name": "",
            "balance": 1000.0,  # Give test bot some balance
            "total_spent": 0.0,
            "total_orders": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
            "is_admin": False
        }
        
        result = await db.users.insert_one(user_doc)
        print(f"✅ Created user: @{test_bot_username}")
        print(f"   Telegram ID: {test_bot_telegram_id}")
        print(f"   Balance: $1000")
        print(f"   Document ID: {result.inserted_id}")
    
    # Verify
    user = await db.users.find_one({"telegram_id": test_bot_telegram_id}, {"_id": 0})
    print(f"\n📋 User details:")
    for key, value in user.items():
        print(f"   {key}: {value}")
    
    client.close()
    print(f"\n✅ Test bot added to admin panel!")

if __name__ == "__main__":
    asyncio.run(add_test_bot())
