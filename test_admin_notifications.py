#!/usr/bin/env python3
"""
Test Admin Notifications
Тестирует уведомления админу о:
1. Пополнении баланса пользователем
2. Создании лейбла (если есть pending order)
"""

import asyncio
import sys
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import httpx

# Load environment
load_dotenv('/app/backend/.env')

MONGO_URL = os.getenv('MONGO_URL')
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID')

async def test_balance_topup_notification():
    """Test admin notification for balance top-up"""
    
    print("\n" + "=" * 60)
    print("🧪 TEST 1: ADMIN NOTIFICATION - BALANCE TOP-UP")
    print("=" * 60)
    
    # Connect to DB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client['telegram_shipping_bot']
    
    # Test data
    test_telegram_id = 5594152712  # CALL SERVICE user
    test_amount = 25.0
    test_track_id = f"TEST_ADMIN_NOTIF_{int(asyncio.get_event_loop().time())}"
    
    try:
        # Step 1: Get current balance
        user = await db.users.find_one({'telegram_id': test_telegram_id}, {'_id': 0})
        if not user:
            print(f"❌ Test user not found")
            return False
        
        initial_balance = user.get('balance', 0.0)
        print(f"✅ Test user: {user.get('username')} (ID: {test_telegram_id})")
        print(f"💰 Initial balance: ${initial_balance:.2f}")
        
        # Step 2: Create payment record
        payment_record = {
            "order_id": f"topup_{test_telegram_id}",
            "amount": test_amount,
            "invoice_id": test_track_id,
            "track_id": test_track_id,
            "pay_url": "https://test-payment.com",
            "status": "pending",
            "telegram_id": test_telegram_id,
            "type": "topup",
            "created_at": "2025-11-19T23:45:00+00:00"
        }
        
        # Delete old test payment
        await db.payments.delete_many({"track_id": test_track_id})
        
        # Insert new payment
        await db.payments.insert_one(payment_record)
        print(f"✅ Payment record created with track_id: {test_track_id}")
        
        # Step 3: Simulate webhook from Oxapay
        webhook_payload = {
            "trackId": test_track_id,
            "status": "paid",
            "amount": str(test_amount),
            "paidAmount": str(test_amount),
            "currency": "USD"
        }
        
        print(f"\n📤 Sending webhook to trigger admin notification...")
        print(f"   Track ID: {test_track_id}")
        print(f"   Amount: ${test_amount}")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{BACKEND_URL}/api/oxapay/webhook",
                json=webhook_payload
            )
        
        print(f"📥 Webhook response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Webhook processed: {result}")
            
            # Wait a bit for async notification
            await asyncio.sleep(2)
            
            # Step 4: Verify balance updated
            updated_user = await db.users.find_one(
                {'telegram_id': test_telegram_id},
                {'_id': 0}
            )
            new_balance = updated_user.get('balance', 0.0)
            
            # Step 5: Verify payment status
            payment = await db.payments.find_one(
                {'track_id': test_track_id},
                {'_id': 0}
            )
            payment_status = payment.get('status') if payment else 'NOT_FOUND'
            
            print(f"\n💰 Balance verification:")
            print(f"   Initial: ${initial_balance:.2f}")
            print(f"   Expected: ${initial_balance + test_amount:.2f}")
            print(f"   Actual: ${new_balance:.2f}")
            
            print(f"\n📝 Payment status: {payment_status}")
            
            # Verify
            balance_correct = abs(new_balance - (initial_balance + test_amount)) < 0.01
            status_correct = payment_status == "paid"
            
            print("\n" + "=" * 60)
            if balance_correct and status_correct:
                print("✅ TEST 1 PASSED")
                print(f"\n📱 Проверьте Telegram админа (ID: {ADMIN_TELEGRAM_ID})")
                print("   Должно прийти уведомление:")
                print("   💰 Пополнение баланса")
                print(f"   💵 Сумма: ${test_amount:.2f}")
                print(f"   💳 Новый баланс: ${new_balance:.2f}")
                print(f"   🔖 Track ID: {test_track_id}")
                return True
            else:
                print("❌ TEST 1 FAILED")
                if not balance_correct:
                    print(f"   Balance mismatch!")
                if not status_correct:
                    print(f"   Payment status: {payment_status} (expected: paid)")
                return False
        else:
            print(f"❌ Webhook failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


async def test_label_creation_notification():
    """Test admin notification for label creation"""
    
    print("\n" + "=" * 60)
    print("🧪 TEST 2: ADMIN NOTIFICATION - LABEL CREATION")
    print("=" * 60)
    
    print("⚠️  Этот тест требует:")
    print("   1. Реальный pending order в БД")
    print("   2. Достаточный баланс у пользователя")
    print("   3. Валидные адреса и данные заказа")
    print("   4. Рабочий ShipStation API")
    print("\n⏭️  SKIPPED - требует ручного тестирования")
    print("\n📝 Для ручного теста:")
    print("   1. Создайте заказ через Telegram бота")
    print("   2. Оплатите его с баланса или через Oxapay")
    print("   3. Дождитесь создания лейбла")
    print(f"   4. Проверьте, что админ (ID: {ADMIN_TELEGRAM_ID}) получил уведомление:")
    print("      📦 Новый лейбл создан!")
    print("      👤 Пользователь: [имя]")
    print("      📍 От: [адрес отправителя]")
    print("      📍 Кому: [адрес получателя]")
    print("      🚚 Перевозчик: [carrier]")
    print("      📦 Трекинг: [tracking_number]")
    
    return None  # Not tested automatically


async def run_all_tests():
    """Run all admin notification tests"""
    
    print("\n" + "=" * 60)
    print("🚀 ADMIN NOTIFICATIONS TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Balance top-up notification
    try:
        results['balance_topup'] = await test_balance_topup_notification()
    except Exception as e:
        print(f"Test 1 crashed: {e}")
        results['balance_topup'] = False
    
    # Test 2: Label creation notification (manual)
    try:
        results['label_creation'] = await test_label_creation_notification()
    except Exception as e:
        print(f"Test 2 crashed: {e}")
        results['label_creation'] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    total_tests = sum(1 for v in results.values() if v is not None)
    passed_tests = sum(1 for v in results.values() if v is True)
    
    print(f"\n✅ Test 1 (Balance Top-up): {'PASSED' if results.get('balance_topup') else 'FAILED'}")
    print(f"⏭️  Test 2 (Label Creation): SKIPPED (manual test)")
    
    print(f"\n📈 Results: {passed_tests}/{total_tests} automated tests passed")
    
    if results.get('balance_topup'):
        print("\n✅ MAIN TEST PASSED!")
        print(f"📱 Проверьте Telegram админа (ID: {ADMIN_TELEGRAM_ID})")
        print("   для подтверждения получения уведомления")
    else:
        print("\n❌ MAIN TEST FAILED")
        print("   Проверьте логи backend для деталей")
    
    print("=" * 60)
    
    return results.get('balance_topup', False)


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
