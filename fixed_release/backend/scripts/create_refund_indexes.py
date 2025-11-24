"""
Create indexes for refund_requests collection
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def create_indexes():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client['telegram_shipping_bot']
    coll = db.refund_requests
    
    print("Creating indexes for refund_requests...")
    
    # Index for request_id (unique)
    await coll.create_index("request_id", unique=True, name="idx_request_id")
    print("✅ Created index: request_id (unique)")
    
    # Index for telegram_id
    await coll.create_index("telegram_id", name="idx_telegram_id")
    print("✅ Created index: telegram_id")
    
    # Index for status
    await coll.create_index("status", name="idx_status")
    print("✅ Created index: status")
    
    # Compound index for telegram_id + created_at (for user queries)
    await coll.create_index(
        [("telegram_id", 1), ("created_at", -1)],
        name="idx_user_refunds"
    )
    print("✅ Created index: telegram_id + created_at")
    
    # Compound index for status + created_at (for admin queries)
    await coll.create_index(
        [("status", 1), ("created_at", -1)],
        name="idx_status_date"
    )
    print("✅ Created index: status + created_at")
    
    # Index for label_id (for checking duplicates)
    await coll.create_index("label_id", name="idx_label_id", sparse=True)
    print("✅ Created index: label_id (sparse)")
    
    print("\n✅ All indexes created successfully!")
    
    # Show all indexes
    indexes = await coll.list_indexes().to_list(100)
    print(f"\nTotal indexes: {len(indexes)}")
    for idx in indexes:
        print(f"  • {idx.get('name')}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_indexes())
