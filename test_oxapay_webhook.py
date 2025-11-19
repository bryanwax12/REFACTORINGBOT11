#!/usr/bin/env python3
"""
Test script for Oxapay webhook flow
Simulates complete payment cycle:
1. Create a payment record in DB with track_id
2. Send webhook POST request simulating Oxapay notification
3. Verify balance was updated
"""

import asyncio
import sys
import os
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import httpx

# Load environment
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')

async def test_webhook_flow():
    """Test complete Oxapay webhook flow"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client['labelgen']
    
    print("=" * 60)
    print("🧪 TESTING OXAPAY WEBHOOK FLOW")
    print("=" * 60)
    
    # Test data
    test_telegram_id = 123456789
    test_amount = 50.0
    test_track_id = "TEST_TRACK_12345"
    
    try:
        # Step 1: Get user's current balance
        user = await db.users.find_one({"telegram_id": test_telegram_id}, {"_id": 0})
        if not user:
            print(f"❌ Test user with telegram_id={test_telegram_id} not found")
            print("Creating test user...")
            await db.users.insert_one({
                "telegram_id": test_telegram_id,
                "username": "test_user",
                "balance": 0.0,
                "is_admin": False,
                "bot_blocked_by_user": False
            })
            initial_balance = 0.0
        else:
            initial_balance = user.get('balance', 0.0)
        
        print(f"✅ Initial balance: ${initial_balance:.2f}")
        
        # Step 2: Create payment record with track_id
        payment_record = {
            "order_id": f"topup_{test_telegram_id}",
            "amount": test_amount,
            "invoice_id": test_track_id,
            "track_id": test_track_id,  # ВАЖНО: это поле должно быть
            "pay_url": "https://fake-pay-link.com",
            "status": "pending",
            "telegram_id": test_telegram_id,
            "type": "topup",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Delete old test payments
        await db.payments.delete_many({"track_id": test_track_id})
        
        # Insert new payment
        result = await db.payments.insert_one(payment_record)
        print(f"✅ Payment record created with track_id: {test_track_id}")
        
        # Step 3: Simulate Oxapay webhook
        webhook_payload = {
            "track_id": test_track_id,
            "status": "Paid",
            "paidAmount": test_amount,
            "amount": test_amount
        }
        
        print(f"\n📤 Sending webhook POST to {BACKEND_URL}/api/oxapay/webhook")
        print(f"Payload: {webhook_payload}")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{BACKEND_URL}/api/oxapay/webhook",
                json=webhook_payload
            )
        
        print(f"📥 Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        # Step 4: Verify balance was updated
        await asyncio.sleep(1)  # Give it a moment to process
        
        updated_user = await db.users.find_one(
            {"telegram_id": test_telegram_id},
            {"_id": 0}
        )
        new_balance = updated_user.get('balance', 0.0)
        
        print(f"\n💰 Balance after webhook:")
        print(f"   Initial: ${initial_balance:.2f}")
        print(f"   Expected: ${initial_balance + test_amount:.2f}")
        print(f"   Actual: ${new_balance:.2f}")
        
        # Step 5: Check payment status
        updated_payment = await db.payments.find_one(
            {"track_id": test_track_id},
            {"_id": 0}
        )
        
        payment_status = updated_payment.get('status') if updated_payment else 'NOT_FOUND'
        print(f"\n📝 Payment status: {payment_status}")
        
        # Verify results
        expected_balance = initial_balance + test_amount
        balance_correct = abs(new_balance - expected_balance) < 0.01
        status_correct = payment_status == "paid"
        
        print("\n" + "=" * 60)
        if balance_correct and status_correct:
            print("✅ TEST PASSED - Webhook работает корректно!")
            print(f"   ✓ Баланс обновлен: ${initial_balance:.2f} → ${new_balance:.2f}")
            print(f"   ✓ Статус платежа: {payment_status}")
        else:
            print("❌ TEST FAILED")
            if not balance_correct:
                print(f"   ✗ Баланс НЕ обновлен корректно")
                print(f"     Ожидалось: ${expected_balance:.2f}, получено: ${new_balance:.2f}")
            if not status_correct:
                print(f"   ✗ Статус платежа НЕ обновлен: {payment_status}")
        print("=" * 60)
        
        return balance_correct and status_correct
        
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(test_webhook_flow())
    sys.exit(0 if success else 1)
