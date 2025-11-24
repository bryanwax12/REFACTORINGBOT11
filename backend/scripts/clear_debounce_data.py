#!/usr/bin/env python3
"""
Очистка старых данных debounce из user_sessions в MongoDB
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def clear_debounce_data():
    """Clear all debounce-related data from user_sessions"""
    
    # Load MongoDB URL from environment only
    mongo_url = os.environ.get('MONGO_URL')
    print(f"✅ Using MongoDB URL from environment")
    
    if not mongo_url:
        print("❌ No MongoDB URL found!")
        return
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongo_url)
    db = client.telegram_shipping_bot
    
    print("🔍 Checking user_sessions collection...")
    
    # Find all sessions
    sessions = await db.user_sessions.find({}, {"_id": 0, "user_id": 1}).to_list(1000)
    print(f"📊 Found {len(sessions)} sessions")
    
    if len(sessions) == 0:
        print("✅ No sessions to clean")
        return
    
    # Update all sessions to remove debounce-related fields
    # These fields were stored in context.user_data by the old @debounce_input decorator
    debounce_fields = [
        "last_conversation_state",  # Stored by debounce decorator
    ]
    
    # Also remove any fields that look like debounce counters
    # Pattern: "{user_id}_{handler_name}_fast_count"
    
    print("🧹 Clearing debounce data from all sessions...")
    
    # Remove specific known debounce fields
    unset_dict = {}
    for field in debounce_fields:
        unset_dict[f"order_data.{field}"] = ""
    
    result = await db.user_sessions.update_many(
        {},
        {"$unset": unset_dict}
    )
    
    print(f"✅ Updated {result.modified_count} sessions")
    
    # Also clear any fields ending with "_fast_count"
    print("🧹 Checking for _fast_count fields...")
    
    # We need to iterate through each session to find and remove dynamic fields
    sessions_with_data = await db.user_sessions.find({}).to_list(1000)
    
    count_cleared = 0
    for session in sessions_with_data:
        order_data = session.get('order_data', {})
        
        # Find all keys ending with _fast_count
        keys_to_remove = [k for k in order_data.keys() if k.endswith('_fast_count')]
        
        if keys_to_remove:
            unset_dict = {f"order_data.{k}": "" for k in keys_to_remove}
            
            await db.user_sessions.update_one(
                {"user_id": session['user_id']},
                {"$unset": unset_dict}
            )
            
            count_cleared += 1
            print(f"  🗑️ Cleared {len(keys_to_remove)} debounce counters for user {session['user_id']}")
    
    print(f"✅ Cleared debounce counters from {count_cleared} sessions")
    print("🎉 All debounce data cleaned!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(clear_debounce_data())
