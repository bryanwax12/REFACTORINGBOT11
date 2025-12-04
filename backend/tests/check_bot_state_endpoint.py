"""
Quick test to check if bot_instance is accessible in app.state via HTTP request
"""
import httpx
import asyncio


async def check_bot_state():
    """Check bot_instance via debug endpoint"""
    
    # We'll create a temporary debug endpoint to check app.state
    # For now, let's try calling an existing endpoint and check logs
    
    print("Checking if bot_instance is in app.state...")
    print("=" * 60)
    
    # Call API to trigger router code
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(
                "https://telegram-shipbot.preview.emergentagent.com/api/stats",
                headers={"x-api-key": "sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024"}
            )
            
            print(f"API Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ API is responding")
                print("\n🔍 Now check backend logs for bot_instance status:")
                print("   tail -n 100 /var/log/supervisor/backend.out.log | grep -i 'bot_instance'")
            else:
                print(f"❌ API Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")


if __name__ == "__main__":
    asyncio.run(check_bot_state())
