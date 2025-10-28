#!/usr/bin/env python3
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
api_key = os.environ.get('SHIPSTATION_API_KEY', '')

headers = {
    'API-Key': api_key,
    'Content-Type': 'application/json'
}

print("Testing ShipStation V2 API directly...")

# Get carrier IDs first
print("\n1. Getting carrier IDs...")
try:
    carrier_response = requests.get('https://api.shipstation.com/v2/carriers', headers=headers, timeout=10)
    print(f"Carrier Status Code: {carrier_response.status_code}")
    
    if carrier_response.status_code == 200:
        carriers_data = carrier_response.json()
        carriers = carriers_data.get('carriers', [])
        carrier_ids = [c['carrier_id'] for c in carriers if c.get('carrier_id')]
        print(f"Found {len(carrier_ids)} carrier IDs: {carrier_ids}")
    else:
        print(f"Carrier Error: {carrier_response.text}")
        exit(1)
except Exception as e:
    print(f"Carrier Exception: {e}")
    exit(1)

# Create rate request
print("\n2. Testing rate request...")
rate_request = {
    'rate_options': {
        'carrier_ids': carrier_ids
    },
    'shipment': {
        'ship_from': {
            'name': 'John Smith',
            'address_line1': '1600 Amphitheatre Parkway',
            'city_locality': 'Mountain View',
            'state_province': 'CA',
            'postal_code': '94043',
            'country_code': 'US'
        },
        'ship_to': {
            'name': 'Jane Doe',
            'address_line1': '350 5th Ave',
            'city_locality': 'New York',
            'state_province': 'NY',
            'postal_code': '10118',
            'country_code': 'US',
            'address_residential_indicator': 'unknown'
        },
        'packages': [{
            'weight': {
                'value': 2,
                'unit': 'pound'
            },
            'dimensions': {
                'length': 10,
                'width': 8,
                'height': 5,
                'unit': 'inch'
            }
        }]
    }
}

print(f"Rate request payload:")
print(json.dumps(rate_request, indent=2))

try:
    response = requests.post('https://api.shipstation.com/v2/rates', headers=headers, json=rate_request, timeout=15)
    print(f"\nRate Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        rates = data.get('rate_response', {}).get('rates', [])
        print(f"✅ SUCCESS: Found {len(rates)} rates")
        
        if rates:
            print("\nSample rates:")
            for i, rate in enumerate(rates[:5]):
                carrier = rate.get('carrier_friendly_name', 'Unknown')
                service = rate.get('service_type', 'Unknown')
                amount = rate.get('shipping_amount', {}).get('amount', 0)
                days = rate.get('delivery_days', 'N/A')
                print(f"  {i+1}. {carrier} - {service} - ${amount} ({days} days)")
    else:
        print(f"❌ FAILED: {response.text}")
        
        # Try to parse error details
        try:
            error_data = response.json()
            print(f"Error details: {json.dumps(error_data, indent=2)}")
        except:
            pass
            
except Exception as e:
    print(f"Rate Exception: {e}")