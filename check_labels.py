#!/usr/bin/env python3
"""Check recent shipping labels"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone, timedelta

async def check_labels():
    mongo_url = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URL', '')
    db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Get labels from last 24 hours
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    labels = await db.shipping_labels.find({}, {"_id": 0}).sort([("created_at", -1)]).limit(10).to_list(10)
    
    print(f"Total labels in DB: {await db.shipping_labels.count_documents({})}")
    print(f"\n{'='*80}")
    print("Last 10 labels:")
    print('='*80)
    
    for label in labels:
        created_at = label.get('created_at', 'Unknown')
        print(f"\nOrder ID: {label.get('order_id')}")
        print(f"Tracking: {label.get('tracking_number')}")
        print(f"Carrier: {label.get('carrier')}")
        print(f"Amount: ${label.get('amount')}")
        print(f"Status: {label.get('status')}")
        print(f"Created: {created_at}")
        print('-'*80)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_labels())
