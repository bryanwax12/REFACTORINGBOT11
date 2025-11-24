#!/usr/bin/env python3
"""
Force clear bot by making getUpdates calls to consume any pending updates
and release the bot from other instances
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def force_clear():
    token = os.getenv('TEST_BOT_TOKEN')
    
    print("🔧 Force clearing bot instance...")
    print(f"   Bot token: {token[:20]}...")
    
    # First, delete webhook with drop_pending_updates
    print("\n1️⃣ Deleting webhook and dropping pending updates...")
    url = f'https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true'
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    
    # Now make several getUpdates calls to consume any remaining updates
    print("\n2️⃣ Consuming pending updates...")
    
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(5):
            print(f"\n   Attempt {i+1}/5:")
            try:
                url = f'https://api.telegram.org/bot{token}/getUpdates?offset=-1&timeout=1'
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    updates = data.get('result', [])
                    print(f"   ✅ Success! Got {len(updates)} updates")
                    
                    if updates:
                        # Get last update_id and confirm it
                        last_id = max(u['update_id'] for u in updates)
                        confirm_url = f'https://api.telegram.org/bot{token}/getUpdates?offset={last_id + 1}&timeout=1'
                        await client.get(confirm_url)
                        print(f"   ✅ Confirmed offset: {last_id + 1}")
                elif response.status_code == 409:
                    print(f"   ⚠️  Conflict still exists, waiting...")
                    await asyncio.sleep(3)
                else:
                    print(f"   ❌ Error: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")
                await asyncio.sleep(2)
    
    print("\n✅ Force clear completed!")
    print("   You can now restart the backend service.")

if __name__ == "__main__":
    asyncio.run(force_clear())
