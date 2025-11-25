"""
Test Oxapay API key
"""
import asyncio
import sys
import os

sys.path.insert(0, '/app/backend')

async def test_oxapay():
    """Test Oxapay API key"""
    from services.api_services import create_oxapay_invoice
    
    print("🧪 Testing Oxapay API Key\n")
    print("=" * 70)
    
    # Test invoice creation
    print("\n1️⃣ Creating test invoice...")
    print(f"   Amount: $10.00")
    print(f"   Order ID: test_order_123")
    
    result = await create_oxapay_invoice(
        amount=10.00,
        order_id="test_order_123",
        description="Test Invoice - Shipping Label"
    )
    
    print("\n📋 Result:")
    if result.get('success'):
        print(f"   ✅ SUCCESS!")
        print(f"   Track ID: {result.get('trackId')}")
        print(f"   Payment URL: {result.get('payLink')}")
    else:
        print(f"   ❌ FAILED!")
        print(f"   Error: {result.get('error')}")
    
    print("\n" + "=" * 70)
    print("\n✅ Test completed!\n")

if __name__ == "__main__":
    asyncio.run(test_oxapay())
