#!/usr/bin/env python3
import os
from pymongo import MongoClient

def set_production_mode():
    """
    Set ShipStation API to production mode
    """
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
    
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    # Update api_mode setting to production
    db.settings.update_one(
        {'key': 'api_mode'},
        {'$set': {'value': 'production'}},
        upsert=True
    )
    
    print("✅ ShipStation API mode set to: PRODUCTION")
    print("⚠️  Make sure SHIPSTATION_API_KEY_PROD and SHIPSTATION_API_SECRET_PROD are set in .env")
    client.close()

if __name__ == '__main__':
    set_production_mode()
