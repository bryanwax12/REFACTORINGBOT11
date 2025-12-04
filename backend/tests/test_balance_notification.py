"""
Test script for verifying balance notification functionality
This tests if admin panel can send notifications to users via Telegram
"""
import httpx
import asyncio

# Configuration
BACKEND_URL = "https://telegram-shipbot.preview.emergentagent.com"
ADMIN_API_KEY = "sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024"
TEST_USER_TELEGRAM_ID = 5594152712  # Test user from database


async def test_add_balance_notification():
    """Test adding balance and check if notification is sent"""
    
    print("🧪 Testing Balance Notification System")
    print("=" * 60)
    
    # Test 1: Add balance
    print(f"\n📝 Test 1: Adding $5.00 to user {TEST_USER_TELEGRAM_ID}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/users/{TEST_USER_TELEGRAM_ID}/balance/add",
                params={"amount": 5.0},
                headers={"x-api-key": ADMIN_API_KEY}
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.json()}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print("   ✅ Balance added successfully!")
                    print(f"   💰 New balance: ${data.get('new_balance', 0):.2f}")
                    print("\n📱 Check Telegram for notification!")
                    print("   Expected: User should receive beautiful notification")
                else:
                    print(f"   ❌ Failed: {data}")
            else:
                print(f"   ❌ HTTP Error: {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed!")
    print("\nNext steps:")
    print("1. Check backend logs for bot_instance status")
    print("2. Verify user received Telegram notification")
    print("3. If no notification, check bot_instance in app.state")


if __name__ == "__main__":
    asyncio.run(test_add_balance_notification())
