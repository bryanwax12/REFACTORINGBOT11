"""
Migration script to update tracking_number in orders from shipping_labels
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate_tracking_numbers():
    """Update tracking_number in orders from shipping_labels"""
    mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.getenv('DB_NAME', 'telegram_shipping_bot')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print('=' * 70)
    print('MIGRATION: Update tracking_number in orders from shipping_labels')
    print('=' * 70)
    
    try:
        # Get all shipping labels
        labels = await db.shipping_labels.find({}, {'_id': 0, 'order_id': 1, 'tracking_number': 1, 'label_id': 1, 'shipment_id': 1}).to_list(1000)
        
        print(f'\n✅ Found {len(labels)} shipping labels')
        
        updated_count = 0
        skipped_count = 0
        
        for label in labels:
            order_id = label.get('order_id')
            tracking_number = label.get('tracking_number')
            label_id = label.get('label_id')
            shipment_id = label.get('shipment_id')
            
            if not order_id or not tracking_number:
                skipped_count += 1
                continue
            
            # Update order
            result = await db.orders.update_one(
                {'order_id': order_id},
                {'$set': {
                    'tracking_number': tracking_number,
                    'label_id': label_id,
                    'shipment_id': shipment_id
                }}
            )
            
            if result.modified_count > 0:
                updated_count += 1
                print(f'   ✅ Updated order {order_id}: tracking={tracking_number}')
        
        print('\n' + '=' * 70)
        print('MIGRATION COMPLETE')
        print('=' * 70)
        print(f'✅ Updated orders: {updated_count}')
        print(f'⚠️  Skipped (no tracking): {skipped_count}')
        print(f'📊 Total processed: {len(labels)}')
        
    except Exception as e:
        print(f'\n❌ Migration failed: {e}')
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(migrate_tracking_numbers())
