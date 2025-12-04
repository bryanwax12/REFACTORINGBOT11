#!/usr/bin/env python3
import requests
import json

# Test with cross-country shipping (CA to NY)
payload = {
    'from_address': {
        'name': 'West Coast Sender',
        'street1': '1600 Amphitheatre Parkway',
        'city': 'Mountain View',
        'state': 'CA',
        'zip': '94043',
        'country': 'US'
    },
    'to_address': {
        'name': 'East Coast Receiver',
        'street1': '350 5th Ave',
        'city': 'New York',
        'state': 'NY',
        'zip': '10118',
        'country': 'US'
    },
    'parcel': {
        'length': 12,
        'width': 10,
        'height': 8,
        'distance_unit': 'in',
        'weight': 5,
        'mass_unit': 'lb'
    }
}

print('🔍 Testing Cross-Country Shipping (CA to NY)...')
response = requests.post(
    'https://telebot-fixer-1.preview.emergentagent.com/api/calculate-shipping',
    json=payload,
    timeout=30
)

if response.status_code == 200:
    data = response.json()
    rates = data.get('rates', [])
    carriers = data.get('carriers', [])
    print(f'✅ Cross-country test successful!')
    print(f'   Rates: {len(rates)}')
    print(f'   Carriers: {carriers}')
    
    # Show cheapest and fastest options
    if rates:
        cheapest = min(rates, key=lambda x: x.get('amount', 999))
        fastest = min(rates, key=lambda x: x.get('estimated_days', 999))
        print(f'   Cheapest: {cheapest["carrier"]} - {cheapest["service"]} - ${cheapest["amount"]:.2f}')
        print(f'   Fastest: {fastest["carrier"]} - {fastest["service"]} - {fastest["estimated_days"]} days')
else:
    print(f'❌ Cross-country test failed: {response.status_code}')
    print(f'   Error: {response.text}')