#!/usr/bin/env python3
import os
import sys
from pymongo import MongoClient

def set_api_mode(mode='test'):
    """
    Set ShipStation API mode in MongoDB settings
    """
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
    
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    # Update or insert api_mode setting
    db.settings.update_one(
        {'key': 'api_mode'},
        {'$set': {'value': mode}},
        upsert=True
    )
    
    print(f"✅ API mode set to: {mode}")
    client.close()

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'test'
    if mode not in ['test', 'production']:
        print("Usage: python set_api_mode.py [test|production]")
        sys.exit(1)
    set_api_mode(mode)
