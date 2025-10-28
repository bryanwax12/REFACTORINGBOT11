#!/usr/bin/env python3
"""
Backend Test Suite for GoShippo Integration
Tests the LIVE GoShippo API integration for UPS, USPS, and FedEx carriers
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://cryptoship-bot.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def test_api_health():
    """Test if the API is running"""
    print("🔍 Testing API Health...")
    try:
        response = requests.get(f"{API_BASE}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Health: {data}")
            return True
        else:
            print(f"❌ API Health failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API Health error: {e}")
        return False

def test_carriers():
    """Test fetching carrier accounts (GET /api/carriers)"""
    print("\n🔍 Testing Carrier Accounts...")
    try:
        response = requests.get(f"{API_BASE}/carriers", timeout=15)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Carriers Response: {json.dumps(data, indent=2)}")
            
            carriers = data.get('carriers', [])
            active_carriers = [c for c in carriers if c.get('active', False)]
            
            print(f"\n📊 Carrier Summary:")
            print(f"   Total carriers: {len(carriers)}")
            print(f"   Active carriers: {len(active_carriers)}")
            
            # Check for specific carriers
            carrier_names = [c.get('carrier', '').upper() for c in active_carriers]
            ups_found = any('UPS' in name for name in carrier_names)
            usps_found = any('USPS' in name for name in carrier_names)
            fedex_found = any('FEDEX' in name or 'FDX' in name for name in carrier_names)
            
            print(f"   UPS found: {'✅' if ups_found else '❌'}")
            print(f"   USPS found: {'✅' if usps_found else '❌'}")
            print(f"   FedEx found: {'✅' if fedex_found else '❌'}")
            
            return True, data
        else:
            print(f"❌ Carriers test failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Carriers test error: {e}")
        return False, None

def test_shipping_rates():
    """Test shipping rate calculation (POST /api/calculate-shipping)"""
    print("\n🔍 Testing Shipping Rate Calculation...")
    
    # Test payload from review request
    test_payload = {
        "from_address": {
            "name": "John Sender",
            "street1": "215 Clayton St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94117",
            "country": "US"
        },
        "to_address": {
            "name": "Jane Receiver",
            "street1": "525 Market St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "country": "US"
        },
        "parcel": {
            "length": 10,
            "width": 8,
            "height": 5,
            "distance_unit": "in",
            "weight": 2,
            "mass_unit": "lb"
        }
    }
    
    try:
        print(f"📦 Test Payload: {json.dumps(test_payload, indent=2)}")
        
        response = requests.post(
            f"{API_BASE}/calculate-shipping",
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30  # Longer timeout for rate calculation
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Shipping Rates Response: {json.dumps(data, indent=2)}")
            
            rates = data.get('rates', [])
            carriers = data.get('carriers', [])
            
            print(f"\n📊 Rates Summary:")
            print(f"   Total rates: {len(rates)}")
            print(f"   Carriers: {carriers}")
            
            # Check for specific carriers in rates
            rate_carriers = [r.get('carrier', '').upper() for r in rates]
            ups_rates = [r for r in rates if 'UPS' in r.get('carrier', '').upper()]
            usps_rates = [r for r in rates if 'USPS' in r.get('carrier', '').upper()]
            fedex_rates = [r for r in rates if 'FEDEX' in r.get('carrier', '').upper() or 'FDX' in r.get('carrier', '').upper()]
            
            print(f"   UPS rates: {len(ups_rates)} {'✅' if ups_rates else '❌'}")
            print(f"   USPS rates: {len(usps_rates)} {'✅' if usps_rates else '❌'}")
            print(f"   FedEx rates: {len(fedex_rates)} {'✅' if fedex_rates else '❌'}")
            
            # Show rate details
            if rates:
                print(f"\n💰 Rate Details:")
                for i, rate in enumerate(rates[:5], 1):  # Show first 5 rates
                    print(f"   {i}. {rate.get('carrier')} - {rate.get('service')}")
                    print(f"      Price: ${rate.get('amount', 0):.2f}")
                    print(f"      Days: {rate.get('estimated_days', 'N/A')}")
            
            return True, data
        else:
            print(f"❌ Shipping rates test failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Error: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Shipping rates test error: {e}")
        return False, None

def check_backend_logs():
    """Check backend logs for any errors"""
    print("\n🔍 Checking Backend Logs...")
    try:
        # Check error logs
        result = os.popen("tail -n 50 /var/log/supervisor/backend.err.log").read()
        if result.strip():
            print("📋 Recent Backend Error Logs:")
            print(result)
        else:
            print("✅ No recent errors in backend logs")
            
        # Check output logs for GoShippo related entries
        result = os.popen("tail -n 50 /var/log/supervisor/backend.out.log | grep -i 'shippo\\|carrier\\|rate'").read()
        if result.strip():
            print("\n📋 GoShippo Related Logs:")
            print(result)
        else:
            print("ℹ️ No GoShippo related logs found")
            
    except Exception as e:
        print(f"❌ Error checking logs: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting GoShippo Integration Tests")
    print("=" * 60)
    
    # Test results
    results = {}
    
    # 1. Test API Health
    results['api_health'] = test_api_health()
    
    # 2. Test Carriers
    results['carriers'], carriers_data = test_carriers()
    
    # 3. Test Shipping Rates
    results['shipping_rates'], rates_data = test_shipping_rates()
    
    # 4. Check Backend Logs
    check_backend_logs()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    # Overall result
    all_passed = all(results.values())
    overall_status = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    print(f"\nOverall Result: {overall_status}")
    
    # Specific findings for GoShippo
    print("\n🎯 GoShippo Integration Status:")
    if results.get('carriers') and carriers_data:
        active_carriers = [c for c in carriers_data.get('carriers', []) if c.get('active', False)]
        if active_carriers:
            print(f"   ✅ {len(active_carriers)} active carrier accounts found")
        else:
            print(f"   ❌ No active carrier accounts found")
    
    if results.get('shipping_rates') and rates_data:
        rates = rates_data.get('rates', [])
        carriers = rates_data.get('carriers', [])
        if rates:
            print(f"   ✅ {len(rates)} shipping rates returned from {len(carriers)} carriers")
            # Check for UPS specifically (main concern from review request)
            ups_found = any('UPS' in str(carrier).upper() for carrier in carriers)
            if ups_found:
                print(f"   ✅ UPS rates are now working in LIVE mode!")
            else:
                print(f"   ⚠️ UPS rates not found - may need carrier account setup")
        else:
            print(f"   ❌ No shipping rates returned")
    
    return all_passed

if __name__ == "__main__":
    main()