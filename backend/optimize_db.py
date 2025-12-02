#!/usr/bin/env python3
"""
Database Optimization Script
Creates indexes for frequently queried fields
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def create_indexes():
    """Create indexes for better performance"""
    # Get MongoDB connection
    mongo_url = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URL')
    if not mongo_url:
        print("❌ MongoDB URL not found in environment")
        return
    
    print("🔗 Connecting to MongoDB...")
    client = AsyncIOMotorClient(mongo_url)
    db = client['shipping_bot']
    
    print("\n📊 Creating indexes...")
    
    # Users collection
    print("  • users.telegram_id (unique)")
    await db.users.create_index("telegram_id", unique=True)
    
    print("  • users.blocked")
    await db.users.create_index("blocked")
    
    print("  • users.is_blocked")
    await db.users.create_index("is_blocked")
    
    # Orders collection
    print("  • orders.telegram_id")
    await db.orders.create_index("telegram_id")
    
    print("  • orders.order_id (unique)")
    await db.orders.create_index("order_id", unique=True)
    
    print("  • orders.created_at (descending)")
    await db.orders.create_index([("created_at", -1)])
    
    # Pending orders
    print("  • pending_orders.telegram_id (unique)")
    await db.pending_orders.create_index("telegram_id", unique=True)
    
    # Bot settings
    print("  • bot_settings.key (unique)")
    await db.bot_settings.create_index("key", unique=True)
    
    print("  • settings.key (unique)")
    await db.settings.create_index("key", unique=True)
    
    print("\n✅ Indexes created successfully!")
    
    # List all indexes
    print("\n📋 Current indexes:")
    for collection_name in ['users', 'orders', 'pending_orders', 'bot_settings', 'settings']:
        indexes = await db[collection_name].index_information()
        print(f"\n  {collection_name}:")
        for index_name, index_info in indexes.items():
            print(f"    - {index_name}: {index_info.get('key', [])}")
    
    client.close()
    print("\n🎉 Database optimization complete!")

if __name__ == "__main__":
    asyncio.run(create_indexes())
