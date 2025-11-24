"""
Load Testing Script for Telegram Shipping Bot
Simulates 30 concurrent users performing various operations
"""
import asyncio
import random
import time
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

# Test configuration
NUM_USERS = 30
TEST_DURATION = 60  # seconds
OPERATIONS = [
    'create_order',
    'view_templates',
    'get_balance',
    'view_orders'
]

class LoadTester:
    def __init__(self):
        self.mongo_url = os.getenv('MONGO_URL')
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client['telegram_shipping_bot']
        self.results = {
            'total_requests': 0,
            'successful': 0,
            'failed': 0,
            'avg_response_time': 0,
            'max_response_time': 0,
            'min_response_time': float('inf'),
            'operations': {}
        }
        self.response_times = []
        
    async def simulate_user(self, user_id: int):
        """Simulate a single user performing random operations"""
        operations_performed = 0
        start_time = time.time()
        
        while time.time() - start_time < TEST_DURATION:
            operation = random.choice(OPERATIONS)
            
            try:
                op_start = time.time()
                
                if operation == 'create_order':
                    await self.test_create_order(user_id)
                elif operation == 'view_templates':
                    await self.test_view_templates(user_id)
                elif operation == 'get_balance':
                    await self.test_get_balance(user_id)
                elif operation == 'view_orders':
                    await self.test_view_orders(user_id)
                
                op_time = time.time() - op_start
                
                # Record results
                self.results['total_requests'] += 1
                self.results['successful'] += 1
                self.response_times.append(op_time)
                
                if operation not in self.results['operations']:
                    self.results['operations'][operation] = {'count': 0, 'avg_time': 0, 'times': []}
                
                self.results['operations'][operation]['count'] += 1
                self.results['operations'][operation]['times'].append(op_time)
                
                operations_performed += 1
                
                # Random delay between operations (0.5-2 seconds)
                await asyncio.sleep(random.uniform(0.5, 2))
                
            except Exception as e:
                self.results['failed'] += 1
                print(f"❌ User {user_id} operation {operation} failed: {e}")
        
        print(f"✅ User {user_id} completed {operations_performed} operations")
    
    async def test_create_order(self, user_id: int):
        """Simulate order creation"""
        {
            'user_id': user_id,
            'telegram_id': user_id + 7000000000,
            'order_id': f'TEST-{user_id}-{int(time.time())}',
            'status': 'pending',
            'created_at': datetime.utcnow()
        }
        # Don't actually insert to avoid DB pollution
        # Just simulate DB operation time
        await asyncio.sleep(0.01)
    
    async def test_view_templates(self, user_id: int):
        """Simulate viewing templates"""
        await self.db.templates.find(
            {'user_id': user_id + 7000000000}
        ).limit(10).to_list(10)
    
    async def test_get_balance(self, user_id: int):
        """Simulate getting user balance"""
        await self.db.users.find_one(
            {'telegram_id': user_id + 7000000000},
            {'_id': 0, 'balance': 1}
        )
    
    async def test_view_orders(self, user_id: int):
        """Simulate viewing orders"""
        await self.db.orders.find(
            {'telegram_id': user_id + 7000000000}
        ).limit(10).to_list(10)
    
    async def run_load_test(self):
        """Run load test with multiple concurrent users"""
        print(f"\n{'='*60}")
        print("🚀 Starting Load Test")
        print(f"{'='*60}")
        print(f"👥 Users: {NUM_USERS}")
        print(f"⏱️  Duration: {TEST_DURATION}s")
        print(f"🎯 Operations: {', '.join(OPERATIONS)}")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        
        # Create tasks for all users
        tasks = [
            self.simulate_user(user_id)
            for user_id in range(1, NUM_USERS + 1)
        ]
        
        # Run all tasks concurrently
        await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        if self.response_times:
            self.results['avg_response_time'] = sum(self.response_times) / len(self.response_times)
            self.results['max_response_time'] = max(self.response_times)
            self.results['min_response_time'] = min(self.response_times)
            
            # Calculate operation-specific averages
            for op, data in self.results['operations'].items():
                if data['times']:
                    data['avg_time'] = sum(data['times']) / len(data['times'])
        
        # Print results
        self.print_results(total_time)
    
    def print_results(self, total_time: float):
        """Print load test results"""
        print(f"\n{'='*60}")
        print("📊 Load Test Results")
        print(f"{'='*60}\n")
        
        print(f"⏱️  Total Duration: {total_time:.2f}s")
        print(f"📈 Total Requests: {self.results['total_requests']}")
        print(f"✅ Successful: {self.results['successful']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"📊 Success Rate: {(self.results['successful']/self.results['total_requests']*100):.2f}%")
        print(f"⚡ Requests/sec: {self.results['total_requests']/total_time:.2f}")
        
        print(f"\n{'─'*60}")
        print("⏱️  Response Times:")
        print(f"{'─'*60}")
        print(f"   Average: {self.results['avg_response_time']*1000:.2f}ms")
        print(f"   Min: {self.results['min_response_time']*1000:.2f}ms")
        print(f"   Max: {self.results['max_response_time']*1000:.2f}ms")
        
        print(f"\n{'─'*60}")
        print("📋 Operations Breakdown:")
        print(f"{'─'*60}")
        for op, data in self.results['operations'].items():
            print(f"   {op}:")
            print(f"      Count: {data['count']}")
            print(f"      Avg Time: {data['avg_time']*1000:.2f}ms")
        
        print(f"\n{'='*60}")
        
        # Performance assessment
        avg_time_ms = self.results['avg_response_time'] * 1000
        success_rate = (self.results['successful']/self.results['total_requests']*100)
        
        print("\n🎯 Performance Assessment:")
        print(f"{'─'*60}")
        
        if success_rate == 100 and avg_time_ms < 100:
            print("✅ EXCELLENT - System handles load perfectly!")
        elif success_rate >= 99 and avg_time_ms < 200:
            print("✅ GOOD - System performs well under load")
        elif success_rate >= 95 and avg_time_ms < 500:
            print("⚠️  ACCEPTABLE - Some performance degradation")
        else:
            print("❌ POOR - System struggles under load")
        
        print(f"{'='*60}\n")

async def main():
    tester = LoadTester()
    try:
        await tester.run_load_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    finally:
        tester.client.close()

if __name__ == "__main__":
    asyncio.run(main())
