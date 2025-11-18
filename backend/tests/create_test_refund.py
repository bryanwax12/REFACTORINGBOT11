"""
Create test refund request for testing admin panel
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()

MONGO_URL = os.getenv('MONGO_URL')
TEST_USER_ID = 7066790254  # Реальный пользователь

async def create_test_refund():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client['telegram_shipping_bot']
    
    try:
        # Find user's old orders (older than 5 days)
        old_date = datetime.now(timezone.utc) - timedelta(days=6)
        
        old_orders = await db.orders.find({
            "telegram_id": TEST_USER_ID,
            "label_id": {"$exists": True},
            "created_at": {"$lt": old_date.isoformat()}
        }).limit(2).to_list(2)
        
        if not old_orders:
            print("❌ No old orders found. Creating fake old order...")
            # Create a fake old order for testing
            fake_order = {
                "order_id": f"TEST-{uuid4().hex[:8]}",
                "telegram_id": TEST_USER_ID,
                "label_id": f"TEST-LABEL-{uuid4().hex[:12]}",
                "cost": 15.50,
                "carrier": "USPS",
                "service": "Priority Mail",
                "created_at": old_date.isoformat(),
                "status": "completed"
            }
            await db.orders.insert_one(fake_order)
            old_orders = [fake_order]
            print(f"✅ Created fake order with label_id: {fake_order['label_id']}")
        
        # Create refund request
        label_ids = [order['label_id'] for order in old_orders]
        request_id = str(uuid4())
        
        refund_doc = {
            "request_id": request_id,
            "telegram_id": TEST_USER_ID,
            "label_ids": label_ids,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "admin_notes": None,
            "refund_amount": None,
            "processed_at": None
        }
        
        await db.refund_requests.insert_one(refund_doc)
        
        print("\n✅ Created test refund request!")
        print(f"   Request ID: {request_id}")
        print(f"   User ID: {TEST_USER_ID}")
        print(f"   Labels: {len(label_ids)}")
        for label_id in label_ids:
            print(f"      • {label_id}")
        print("\n📋 Check admin panel at: Refunds tab")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(create_test_refund())
