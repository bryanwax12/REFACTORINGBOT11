#!/usr/bin/env python3
"""
Test ShipStation rates API with valid data
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_rates():
    api_key = os.getenv('SHIPSTATION_API_KEY_TEST')
    
    # Valid test data
    request_data = {
        'rate_options': {
            'carrier_ids': ['se-4002273', 'se-4002274', 'se-4013427']
        },
        'shipment': {
            'ship_to': {
                'name': 'Jane Doe',
                'phone': '+13105551234',
                'address_line1': '123 Main St',
                'address_line2': '',
                'city_locality': 'Los Angeles',
                'state_province': 'CA',
                'postal_code': '90001',
                'country_code': 'US',
                'address_residential_indicator': 'unknown'
            },
            'ship_from': {
                'name': 'John Smith',
                'phone': '+14155551234',
                'address_line1': '456 Market St',
                'address_line2': '',
                'city_locality': 'San Francisco',
                'state_province': 'CA',
                'postal_code': '94102',
                'country_code': 'US'
            },
            'packages': [{
                'weight': {
                    'value': 1.0,
                    'unit': 'pound'
                },
                'dimensions': {
                    'length': 10.0,
                    'width': 10.0,
                    'height': 10.0,
                    'unit': 'inch'
                }
            }]
        }
    }
    
    headers = {
        'API-Key': api_key,
        'Content-Type': 'application/json'
    }
    
    print("🧪 Testing ShipStation rates API with VALID data...")
    print(f"   From: San Francisco, CA 94102")
    print(f"   To: Los Angeles, CA 90001")
    print()
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            'https://api.shipstation.com/v2/rates',
            json=request_data,
            headers=headers
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rate_response', {}).get('rates', [])
            
            print(f"✅ SUCCESS! Received {len(rates)} rates:")
            for i, rate in enumerate(rates, 1):
                carrier = rate.get('carrier_friendly_name', 'Unknown')
                service = rate.get('service_type', 'Unknown')
                amount = rate.get('shipping_amount', {}).get('amount', 0)
                print(f"   {i}. {carrier} - {service}: ${amount}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_rates())
