#!/usr/bin/env python3
"""
Script to clear debounce data from user_sessions collection

Usage:
    python clear_debounce_data.py
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def clear_debounce_data():
    """
    Clear all debounce data from user_sessions
    """
    try:
        # Connect to MongoDB
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
        
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        print("🔄 Clearing debounce data from user_sessions...")
        
        # Update all documents to remove debounce fields
        result = db.user_sessions.update_many(
            {},
            {'$unset': {'last_button_press': '', 'button_debounce': ''}}
        )
        
        print(f"✅ Updated {result.modified_count} sessions")
        print(f"   Matched {result.matched_count} total sessions")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    clear_debounce_data()
