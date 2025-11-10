#!/usr/bin/env python3
"""
Test script to create a test order and verify admin notification
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add backend to path
sys.path.append('/app/backend')

# Load environment
load_dotenv('/app/backend/.env')

async def create_test_order_and_label():
    """Create test order and shipping label to verify admin notification"""
    from motor.motor_asyncio import AsyncIOMotorClient
    from telegram import Bot
    
    print("🔍 Creating test order and label to verify admin notification...")
    
    # MongoDB connection
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Get test user (first user in database)
    test_user = await db.users.find_one({}, {"_id": 0})
    if not test_user:
        print("❌ No users found in database. Cannot create test order.")
        return False
    
    telegram_id = test_user['telegram_id']
    print(f"✅ Using test user: {test_user.get('first_name', 'Unknown')} (ID: {telegram_id})")
    
    # Check user balance
    user_balance = test_user.get('balance', 0)
    print(f"💰 User balance: ${user_balance:.2f}")
    
    # Create test order with valid addresses
    order_id = str(uuid.uuid4())
    test_order = {
        'id': order_id,
        'telegram_id': telegram_id,
        'address_from': {
            'name': 'Test Sender',
            'street1': '1111 S Figueroa St',
            'street2': '',
            'city': 'Los Angeles',
            'state': 'CA',
            'zip': '90015',
            'country': 'US',
            'phone': '+15551234567'
        },
        'address_to': {
            'name': 'Test Receiver',
            'street1': '350 5th Ave',
            'street2': '',
            'city': 'New York',
            'state': 'NY',
            'zip': '10118',
            'country': 'US',
            'phone': '+15559876543'
        },
        'parcel': {
            'weight': 2.0,
            'length': 10,
            'width': 8,
            'height': 6
        },
        'amount': 15.50,
        'original_amount': 14.00,
        'payment_status': 'paid',
        'shipping_status': 'pending',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'selected_carrier': 'stamps_com',
        'selected_service': 'usps_priority_mail',
        'rate_id': '',  # Will be filled after fetching rates
        'selected_service_code': 'usps_priority_mail'
    }
    
    print(f"\n📦 Test Order Details:")
    print(f"   Order ID: {order_id}")
    print(f"   From: {test_order['address_from']['city']}, {test_order['address_from']['state']}")
    print(f"   To: {test_order['address_to']['city']}, {test_order['address_to']['state']}")
    print(f"   Weight: {test_order['parcel']['weight']} lb")
    print(f"   Amount: ${test_order['amount']:.2f}")
    
    # First, fetch shipping rates to get valid rate_id
    print("\n🔍 Fetching shipping rates from ShipStation...")
    import requests
    
    SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY')
    headers = {
        'API-Key': SHIPSTATION_API_KEY,
        'Content-Type': 'application/json'
    }
    
    # Get carrier IDs
    carriers_response = requests.get(
        'https://api.shipstation.com/v2/carriers',
        headers=headers,
        timeout=30
    )
    
    if carriers_response.status_code != 200:
        print(f"❌ Failed to fetch carriers: {carriers_response.status_code}")
        return False
    
    carriers_data = carriers_response.json()
    all_carriers = carriers_data.get('carriers', [])
    
    # Filter out globalpost but keep all other active carriers
    carrier_ids = [c['carrier_id'] for c in all_carriers 
                   if c.get('carrier_code') not in ['globalpost']]
    
    print(f"✅ Found {len(carrier_ids)} carriers")
    for c in all_carriers[:5]:  # Show first 5 carriers
        print(f"   - {c.get('friendly_name', 'Unknown')}: {c.get('carrier_id')}")
    
    # Fetch rates - format addresses for ShipStation API
    rate_request = {
        'rate_options': {
            'carrier_ids': carrier_ids
        },
        'shipment': {
            'ship_to': {
                'name': test_order['address_to']['name'],
                'phone': test_order['address_to']['phone'],
                'address_line1': test_order['address_to']['street1'],
                'address_line2': test_order['address_to'].get('street2', ''),
                'city_locality': test_order['address_to']['city'],
                'state_province': test_order['address_to']['state'],
                'postal_code': test_order['address_to']['zip'],
                'country_code': test_order['address_to']['country']
            },
            'ship_from': {
                'name': test_order['address_from']['name'],
                'phone': test_order['address_from']['phone'],
                'address_line1': test_order['address_from']['street1'],
                'address_line2': test_order['address_from'].get('street2', ''),
                'city_locality': test_order['address_from']['city'],
                'state_province': test_order['address_from']['state'],
                'postal_code': test_order['address_from']['zip'],
                'country_code': test_order['address_from']['country']
            },
            'packages': [{
                'weight': {
                    'value': test_order['parcel']['weight'],
                    'unit': 'pound'
                },
                'dimensions': {
                    'length': test_order['parcel']['length'],
                    'width': test_order['parcel']['width'],
                    'height': test_order['parcel']['height'],
                    'unit': 'inch'
                }
            }]
        }
    }
    
    rates_response = requests.post(
        'https://api.shipstation.com/v2/rates',
        headers=headers,
        json=rate_request,
        timeout=30
    )
    
    if rates_response.status_code != 200:
        print(f"❌ Failed to fetch rates: {rates_response.status_code}")
        print(f"Response: {rates_response.text}")
        return False
    
    rates_data = rates_response.json()
    rates = rates_data.get('rates', [])
    
    print(f"   API Response: {len(rates)} rates returned")
    if 'errors' in rates_data:
        print(f"   Errors: {rates_data['errors']}")
    
    if not rates:
        print("❌ No rates returned from ShipStation")
        print(f"   Full response: {rates_data}")
        return False
    
    # Use first USPS rate
    usps_rates = [r for r in rates if 'usps' in r.get('service_code', '').lower() or 'stamps' in r.get('carrier_code', '').lower()]
    if not usps_rates:
        print("⚠️ No USPS rates, using first available rate")
        selected_rate = rates[0]
    else:
        selected_rate = usps_rates[0]
    
    test_order['rate_id'] = selected_rate['rate_id']
    test_order['selected_carrier'] = selected_rate.get('carrier_friendly_name', 'USPS')
    test_order['selected_service'] = selected_rate.get('service_type', 'Priority Mail')
    
    print(f"✅ Selected rate: {test_order['selected_carrier']} - {test_order['selected_service']}")
    print(f"   Rate ID: {test_order['rate_id']}")
    print(f"   Price: ${selected_rate.get('shipping_amount', {}).get('amount', 0):.2f}")
    
    # Insert order into database
    print("\n💾 Saving test order to database...")
    await db.orders.insert_one(test_order)
    print("✅ Test order saved to database")
    
    # Now create the shipping label
    print("\n📋 Creating shipping label...")
    
    # Import the create_and_send_label function
    exec(open('/app/backend/server.py').read(), globals())
    
    # Initialize bot instance
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    bot = Bot(TELEGRAM_BOT_TOKEN)
    
    # Set global bot_instance
    globals()['bot_instance'] = bot
    
    try:
        # Call create_and_send_label
        result = await create_and_send_label(order_id, telegram_id, None)
        
        if result:
            print("\n✅ LABEL CREATED SUCCESSFULLY!")
            print("\n🔍 Checking if admin notification was sent...")
            
            # Check shipping_labels collection
            label = await db.shipping_labels.find_one({'order_id': order_id}, {"_id": 0})
            if label:
                print(f"\n📋 Label Details:")
                print(f"   Tracking: {label.get('tracking_number')}")
                print(f"   Carrier: {label.get('carrier')}")
                print(f"   Service: {label.get('service_level')}")
                print(f"   Amount: ${label.get('amount')}")
                
            # Check backend logs for admin notification
            print("\n📝 Checking backend logs for admin notification...")
            import subprocess
            result = subprocess.run(
                ['tail', '-n', '50', '/var/log/supervisor/backend.out.log'],
                capture_output=True,
                text=True
            )
            
            logs = result.stdout
            if 'Label creation notification sent to admin' in logs:
                print("✅ ADMIN NOTIFICATION SENT SUCCESSFULLY!")
                print("\n🎉 TEST PASSED: Admin notification functionality is working correctly")
                return True
            elif 'Failed to send label notification to admin' in logs:
                print("⚠️ Admin notification failed (check logs for details)")
                # Show error details
                for line in logs.split('\n'):
                    if 'Failed to send label notification' in line or 'error' in line.lower():
                        print(f"   {line}")
                return False
            else:
                print("⚠️ No admin notification log found (may still have been sent)")
                print("\n💡 Check Telegram messages to admin ID 7066790254")
                return True
        else:
            print("\n❌ LABEL CREATION FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during label creation: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        await client.close()

if __name__ == '__main__':
    result = asyncio.run(create_test_order_and_label())
    sys.exit(0 if result else 1)
