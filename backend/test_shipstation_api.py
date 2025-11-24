#!/usr/bin/env python3
"""
Script to test ShipStation API keys
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_api_key(key_name, api_key):
    """Test a ShipStation API key"""
    print(f"\n🔑 Testing {key_name}:")
    print(f"   Key: {api_key[:20]}... (length: {len(api_key)})")
    
    if not api_key:
        print(f"   ❌ Key not set")
        return False
    
    url = "https://api.shipstation.com/v2/carriers"
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                carriers = data.get('carriers', [])
                print(f"   ✅ SUCCESS! Found {len(carriers)} carriers")
                if carriers:
                    print(f"   First carrier: {carriers[0].get('carrier_name', 'N/A')}")
                return True
            elif response.status_code == 401:
                print(f"   ❌ UNAUTHORIZED - Key is invalid or expired")
                print(f"   Response: {response.text[:200]}")
                return False
            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
                
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

async def main():
    print("🧪 ShipStation API Key Testing")
    print("=" * 60)
    
    # Get keys from environment
    test_key = os.getenv('SHIPSTATION_API_KEY_TEST')
    prod_key = os.getenv('SHIPSTATION_API_KEY_PROD')
    default_key = os.getenv('SHIPSTATION_API_KEY')
    
    results = []
    
    if test_key:
        result = await test_api_key("SHIPSTATION_API_KEY_TEST", test_key)
        results.append(("TEST", result))
    
    if prod_key:
        result = await test_api_key("SHIPSTATION_API_KEY_PROD", prod_key)
        results.append(("PROD", result))
    
    if default_key:
        result = await test_api_key("SHIPSTATION_API_KEY", default_key)
        results.append(("DEFAULT", result))
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    for key_type, success in results:
        status = "✅ VALID" if success else "❌ INVALID"
        print(f"   {key_type}: {status}")
    
    if not any(r[1] for r in results):
        print("\n⚠️  NO VALID API KEYS FOUND!")
        print("   Please provide a valid ShipStation API key.")

if __name__ == "__main__":
    asyncio.run(main())
