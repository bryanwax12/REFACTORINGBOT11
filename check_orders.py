#!/usr/bin/env python3
"""Check orders in database"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def check_orders():
    load_dotenv('/app/backend/.env')
    mongo_url = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URL', '')
    db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Get last 5 orders
    orders = await db.orders.find({}, {"_id": 0}).sort([("created_at", -1)]).limit(5).to_list(5)
    
    print(f"Total orders in DB: {await db.orders.count_documents({})}")
    print(f"\n{'='*80}")
    print("Last 5 orders:")
    print('='*80)
    
    for order in orders:
        print(f"\nOrder ID: {order.get('order_id')}")
        print(f"Tracking Number: {order.get('tracking_number', 'NOT SET')}")
        print(f"Label ID: {order.get('label_id', 'NOT SET')}")
        print(f"Shipment ID: {order.get('shipment_id', 'NOT SET')}")
        print(f"Shipping Status: {order.get('shipping_status', 'NOT SET')}")
        print(f"Payment Status: {order.get('payment_status')}")
        print(f"Amount: ${order.get('amount')}")
        print(f"Created: {order.get('created_at')}")
        print('-'*80)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_orders())
