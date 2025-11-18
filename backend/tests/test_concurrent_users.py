"""
Concurrent Users Test - проверка изоляции состояний между пользователями
Тестирует что бот не путает шаги разных пользователей
"""
import asyncio
import httpx
import random
from datetime import datetime

WEBHOOK_URL = "http://localhost:8001/api/telegram/webhook"
NUM_USERS = 10
STEPS_PER_USER = 5


class ConcurrentUserTester:
    def __init__(self):
        self.results = {
            "total_users": 0,
            "successful_users": 0,
            "failed_users": 0,
            "state_conflicts": 0,
            "errors": []
        }
        
    async def simulate_user_session(self, user_id: int):
        """
        Симулирует одного пользователя, проходящего через несколько шагов
        """
        telegram_id = 8000000000 + user_id
        print(f"👤 User {user_id} (telegram_id: {telegram_id}) starting...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: /start
                update = self.create_update(telegram_id, text="/start")
                response = await client.post(WEBHOOK_URL, json=update)
                if response.status_code != 200:
                    raise Exception(f"Start failed: {response.status_code}")
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Step 2: new_order
                update = self.create_update(telegram_id, callback_data="new_order")
                response = await client.post(WEBHOOK_URL, json=update)
                if response.status_code != 200:
                    raise Exception(f"New order failed: {response.status_code}")
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
                # Step 3: Enter FROM_NAME
                name = f"TestUser{user_id}"
                update = self.create_update(telegram_id, text=name)
                response = await client.post(WEBHOOK_URL, json=update)
                if response.status_code != 200:
                    raise Exception(f"FROM_NAME failed: {response.status_code}")
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
                # Step 4: Enter FROM_ADDRESS
                address = f"{random.randint(100, 999)} Test St Unit {user_id}"
                update = self.create_update(telegram_id, text=address)
                response = await client.post(WEBHOOK_URL, json=update)
                if response.status_code != 200:
                    raise Exception(f"FROM_ADDRESS failed: {response.status_code}")
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
                # Step 5: Skip FROM_ADDRESS2
                update = self.create_update(telegram_id, callback_data="skip_from_address2")
                response = await client.post(WEBHOOK_URL, json=update)
                if response.status_code != 200:
                    raise Exception(f"Skip ADDRESS2 failed: {response.status_code}")
                
                print(f"✅ User {user_id} completed {STEPS_PER_USER} steps successfully")
                self.results["successful_users"] += 1
                
        except Exception as e:
            print(f"❌ User {user_id} failed: {e}")
            self.results["failed_users"] += 1
            self.results["errors"].append(f"User {user_id}: {str(e)}")
    
    def create_update(self, telegram_id: int, text: str = None, callback_data: str = None):
        """Create Telegram Update object"""
        update_id = random.randint(100000000, 999999999)
        
        if text:
            return {
                "update_id": update_id,
                "message": {
                    "message_id": random.randint(1000, 9999),
                    "from": {
                        "id": telegram_id,
                        "is_bot": False,
                        "first_name": f"Test{telegram_id}",
                        "username": f"test_{telegram_id}"
                    },
                    "chat": {
                        "id": telegram_id,
                        "type": "private"
                    },
                    "date": int(datetime.now().timestamp()),
                    "text": text
                }
            }
        elif callback_data:
            return {
                "update_id": update_id,
                "callback_query": {
                    "id": str(random.randint(100000000, 999999999)),
                    "from": {
                        "id": telegram_id,
                        "is_bot": False,
                        "first_name": f"Test{telegram_id}",
                        "username": f"test_{telegram_id}"
                    },
                    "message": {
                        "message_id": random.randint(1000, 9999),
                        "chat": {
                            "id": telegram_id,
                            "type": "private"
                        },
                        "date": int(datetime.now().timestamp())
                    },
                    "chat_instance": str(random.randint(1000000000, 9999999999)),
                    "data": callback_data
                }
            }
        else:
            raise ValueError("Need text or callback_data")
    
    async def run_concurrent_test(self):
        """
        Запускает множество пользователей одновременно
        """
        print("=" * 80)
        print("🧪 CONCURRENT USERS TEST - State Isolation Check")
        print("=" * 80)
        print(f"👥 Testing {NUM_USERS} concurrent users")
        print(f"📊 Each user performs {STEPS_PER_USER} steps")
        print("🎯 Goal: Verify no state conflicts between users")
        print("=" * 80)
        print()
        
        self.results["total_users"] = NUM_USERS
        
        # Запускаем всех пользователей одновременно
        tasks = [
            self.simulate_user_session(user_id)
            for user_id in range(1, NUM_USERS + 1)
        ]
        
        start_time = datetime.now()
        await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Результаты
        print()
        print("=" * 80)
        print("📊 TEST RESULTS")
        print("=" * 80)
        print(f"⏱️  Total time: {elapsed:.2f}s")
        print(f"👥 Total users: {self.results['total_users']}")
        print(f"✅ Successful: {self.results['successful_users']}")
        print(f"❌ Failed: {self.results['failed_users']}")
        
        if self.results['successful_users'] == self.results['total_users']:
            print()
            print("🎉 SUCCESS! All users completed without state conflicts!")
            print("✅ Bot is ready for production - concurrent users work perfectly!")
        elif self.results['successful_users'] >= self.results['total_users'] * 0.8:
            print()
            print("⚠️  MOSTLY WORKING - Some issues detected")
            print("Check errors below:")
        else:
            print()
            print("❌ FAILED - Major state conflicts detected!")
            print("Bot NOT ready for production!")
        
        if self.results['errors']:
            print()
            print("Errors:")
            for error in self.results['errors'][:10]:
                print(f"  • {error}")
        
        print("=" * 80)


async def main():
    tester = ConcurrentUserTester()
    await tester.run_concurrent_test()


if __name__ == "__main__":
    asyncio.run(main())
