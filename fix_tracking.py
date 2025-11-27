#!/usr/bin/env python3
"""Fix tracking numbers in orders from labels"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def fix_tracking():
    load_dotenv('/app/backend/.env')
    mongo_url = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URL', '')
    db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Get all labels
    labels = await db.shipping_labels.find({}, {"_id": 0}).to_list(1000)
    
    print(f"Found {len(labels)} labels")
    
    updated_count = 0
    for label in labels:
        order_id = label.get('order_id')
        tracking_number = label.get('tracking_number')
        label_id = label.get('label_id')
        shipment_id = label.get('shipment_id')
        
        if order_id and tracking_number:
            # Update order
            result = await db.orders.update_one(
                {"order_id": order_id},
                {"$set": {
                    "tracking_number": tracking_number,
                    "label_id": label_id,
                    "shipment_id": shipment_id,
                    "shipping_status": "label_created"
                }}
            )
            
            if result.modified_count > 0:
                print(f"✅ Updated order {order_id} with tracking {tracking_number}")
                updated_count += 1
            else:
                print(f"⚠️ Order {order_id} not found or already updated")
    
    print(f"\n{'='*80}")
    print(f"Total updated: {updated_count}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(fix_tracking())
