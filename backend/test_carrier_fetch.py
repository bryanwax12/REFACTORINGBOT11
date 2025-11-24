#!/usr/bin/env python3
"""
Quick test to verify carrier fetching works with updated keys
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, '/app/backend')

from services.api_services import get_shipstation_carrier_ids

async def main():
    print("🧪 Testing carrier fetch with updated API keys...\n")
    
    # Show which keys are loaded
    test_key = os.environ.get('SHIPSTATION_API_KEY_TEST', 'NOT SET')
    prod_key = os.environ.get('SHIPSTATION_API_KEY_PROD', 'NOT SET')
    
    print(f"📋 Environment Variables:")
    print(f"   TEST_KEY: {test_key[:20]}... (len: {len(test_key)})")
    print(f"   PROD_KEY: {prod_key[:20]}... (len: {len(prod_key)})")
    print()
    
    # Try fetching carriers
    print("🔍 Fetching carriers from ShipStation...\n")
    carriers = await get_shipstation_carrier_ids()
    
    if carriers:
        print(f"✅ SUCCESS! Found {len(carriers)} carriers:")
        for name, carrier_id in carriers.items():
            print(f"   • {name}: {carrier_id}")
    else:
        print("❌ FAILED: No carriers returned")
    
    return carriers

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
