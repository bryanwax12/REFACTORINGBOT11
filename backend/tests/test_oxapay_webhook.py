"""
Test Oxapay webhook endpoint with comprehensive duplicate protection testing
"""
import httpx
import asyncio
import json
import time
from motor.motor_asyncio import AsyncIOMotorClient
import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'telegram_shipping_bot')

WEBHOOK_URL = "https://telebot-fixer-1.preview.emergentagent.com/api/oxapay/webhook"
TEST_USER_ID = 5594152712


async def setup_test_payment(db, track_id, status="pending"):
    """Setup a test payment in the database"""
    payment = {
        "id": f"test_payment_{track_id}",
        "track_id": track_id,
        "invoice_id": track_id,
        "telegram_id": TEST_USER_ID,
        "amount": 10.0,
        "currency": "USDT",
        "status": status,
        "type": "topup",
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    # Remove existing test payment
    await db.payments.delete_many({"track_id": track_id})
    
    # Insert new test payment
    result = await db.payments.insert_one(payment)
    print(f"✅ Test payment created: track_id={track_id}, status={status}")
    return result.inserted_id


async def get_payment_status(db, track_id):
    """Get current payment status from database"""
    payment = await db.payments.find_one({"track_id": track_id})
    return payment.get('status') if payment else None


async def test_webhook_basic():
    """Test 1: Basic webhook functionality"""
    print("\n🧪 TEST 1: Basic Webhook Functionality")
    print("-" * 50)
    
    payload = {
        "status": "Paid",
        "track_id": "basic_test_123",
        "amount": 10.0,
        "currency": "USDT",
        "telegram_id": TEST_USER_ID
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(WEBHOOK_URL, json=payload)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            
            if response.status_code == 200:
                print("✅ TEST 1 PASSED: Basic webhook functionality working")
                return True
            else:
                print("❌ TEST 1 FAILED: Webhook returned error")
                return False
                
        except Exception as e:
            print(f"❌ TEST 1 FAILED: Exception - {e}")
            return False


async def test_duplicate_webhook_protection():
    """Test 2: Duplicate Webhook Protection - MAIN TEST"""
    print("\n🧪 TEST 2: Duplicate Webhook Protection")
    print("-" * 50)
    
    # Connect to database
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    track_id = "duplicate_test_456"
    
    try:
        # Step 1: Setup test payment with 'pending' status
        await setup_test_payment(db, track_id, status="pending")
        
        # Step 2: Send first webhook (should process normally)
        payload = {
            "status": "Paid",
            "track_id": track_id,
            "amount": 10.0,
            "currency": "USDT",
            "telegram_id": TEST_USER_ID
        }
        
        print("📤 Sending FIRST webhook...")
        async with httpx.AsyncClient(timeout=30) as client_http:
            response1 = await client_http.post(WEBHOOK_URL, json=payload)
            
        print(f"First webhook - Status: {response1.status_code}, Response: {response1.json()}")
        
        # Check payment status after first webhook
        status_after_first = await get_payment_status(db, track_id)
        print(f"Payment status after first webhook: {status_after_first}")
        
        # Step 3: Send second webhook (should be detected as duplicate)
        print("\n📤 Sending SECOND webhook (duplicate)...")
        async with httpx.AsyncClient(timeout=30) as client_http:
            response2 = await client_http.post(WEBHOOK_URL, json=payload)
            
        print(f"Second webhook - Status: {response2.status_code}, Response: {response2.json()}")
        
        # Check payment status after second webhook (should remain 'paid')
        status_after_second = await get_payment_status(db, track_id)
        print(f"Payment status after second webhook: {status_after_second}")
        
        # Verify duplicate protection worked
        if (response1.status_code == 200 and 
            response2.status_code == 200 and 
            response2.json().get('message') == 'Payment already processed' and
            status_after_first == 'paid' and 
            status_after_second == 'paid'):
            print("✅ TEST 2 PASSED: Duplicate webhook protection working correctly!")
            return True
        else:
            print("❌ TEST 2 FAILED: Duplicate webhook protection not working")
            print(f"   Expected: Second response message = 'Payment already processed'")
            print(f"   Actual: Second response message = '{response2.json().get('message')}'")
            return False
            
    except Exception as e:
        print(f"❌ TEST 2 FAILED: Exception - {e}")
        return False
    finally:
        # Cleanup
        await db.payments.delete_many({"track_id": track_id})
        client.close()


async def test_webhook_with_nonexistent_payment():
    """Test 3: Webhook with non-existent payment"""
    print("\n🧪 TEST 3: Webhook with Non-existent Payment")
    print("-" * 50)
    
    payload = {
        "status": "Paid",
        "track_id": "nonexistent_789",
        "amount": 10.0,
        "currency": "USDT",
        "telegram_id": TEST_USER_ID
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(WEBHOOK_URL, json=payload)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            
            if response.status_code == 200:
                print("✅ TEST 3 PASSED: Webhook handles non-existent payment gracefully")
                return True
            else:
                print("❌ TEST 3 FAILED: Webhook failed with non-existent payment")
                return False
                
        except Exception as e:
            print(f"❌ TEST 3 FAILED: Exception - {e}")
            return False


async def run_all_tests():
    """Run all Oxapay webhook tests"""
    print("🚀 OXAPAY WEBHOOK COMPREHENSIVE TESTING")
    print("=" * 60)
    
    results = []
    
    # Test 1: Basic functionality
    results.append(await test_webhook_basic())
    
    # Test 2: Duplicate protection (MAIN TEST)
    results.append(await test_duplicate_webhook_protection())
    
    # Test 3: Non-existent payment
    results.append(await test_webhook_with_nonexistent_payment())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    test_names = [
        "Basic Webhook Functionality",
        "Duplicate Webhook Protection", 
        "Non-existent Payment Handling"
    ]
    
    passed = 0
    for i, result in enumerate(results):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"Test {i+1}: {test_names[i]} - {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed ({passed/len(results)*100:.1f}%)")
    
    if results[1]:  # Test 2 is the main focus
        print("\n🎉 MAIN OBJECTIVE ACHIEVED: Duplicate webhook protection is working!")
    else:
        print("\n⚠️ MAIN OBJECTIVE FAILED: Duplicate webhook protection needs attention!")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
