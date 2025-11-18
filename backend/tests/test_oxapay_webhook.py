"""
Test Oxapay webhook endpoint to verify bot_instance availability
"""
import httpx
import asyncio
import json


async def test_oxapay_webhook():
    """Test Oxapay webhook with sample payload"""
    
    print("🧪 Testing Oxapay Webhook bot_instance availability")
    print("=" * 60)
    
    # Sample Oxapay webhook payload (simulating successful payment)
    payload = {
        "status": "Paid",
        "trackId": "test_track_12345",
        "orderId": "test_order_12345",
        "amount": 10.0,
        "currency": "USDT",
        "telegram_id": 5594152712  # Test user
    }
    
    print(f"📝 Sending test webhook payload:")
    print(json.dumps(payload, indent=2))
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                "https://tg-fixer-hub.preview.emergentagent.com/api/oxapay/webhook",
                json=payload
            )
            
            print(f"\n   Status Code: {response.status_code}")
            print(f"   Response: {response.json()}")
            
            if response.status_code == 200:
                print(f"\n✅ Webhook endpoint accessible")
                print(f"\n📋 Check logs for bot_instance status:")
                print(f"   tail -n 50 /var/log/supervisor/backend.out.log | grep OXAPAY_WEBHOOK")
            else:
                print(f"\n❌ Webhook failed")
                
        except Exception as e:
            print(f"\n❌ Exception: {e}")


if __name__ == "__main__":
    asyncio.run(test_oxapay_webhook())
