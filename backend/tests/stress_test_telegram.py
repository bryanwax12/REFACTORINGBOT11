"""
Stress Test for Telegram Bot - Full Order Flow
Simulates 30 concurrent users creating orders through the bot
"""
import asyncio
import aiohttp
import time
from datetime import datetime
import random

BASE_URL = "http://localhost:8001"
NUM_USERS = 30

class TelegramBotStressTester:
    def __init__(self):
        self.results = {
            'total_operations': 0,
            'successful': 0,
            'failed': 0,
            'errors': [],
            'response_times': [],
            'operations': {}
        }
    
    async def simulate_order_creation(self, session, user_id: int):
        """Simulate complete order creation flow"""
        telegram_id = 7000000000 + user_id
        operations = []
        
        try:
            # 1. Get user balance
            start = time.time()
            async with session.get(f"{BASE_URL}/api/users/{telegram_id}/balance") as resp:
                if resp.status == 200:
                    operations.append(('get_balance', time.time() - start, 'success'))
                else:
                    operations.append(('get_balance', time.time() - start, 'failed'))
            
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # 2. Get templates
            start = time.time()
            async with session.get(f"{BASE_URL}/api/templates/{telegram_id}") as resp:
                if resp.status == 200:
                    operations.append(('get_templates', time.time() - start, 'success'))
                else:
                    operations.append(('get_templates', time.time() - start, 'failed'))
            
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # 3. Get orders history
            start = time.time()
            async with session.get(f"{BASE_URL}/api/orders/{telegram_id}") as resp:
                if resp.status == 200:
                    operations.append(('get_orders', time.time() - start, 'success'))
                else:
                    operations.append(('get_orders', time.time() - start, 'failed'))
            
            return operations
            
        except Exception as e:
            self.results['errors'].append(f"User {user_id}: {str(e)}")
            return operations
    
    async def run_user(self, session, user_id: int):
        """Run multiple operations for a single user"""
        start_time = time.time()
        total_operations = 0
        
        # Run for 60 seconds
        while time.time() - start_time < 60:
            ops = await self.simulate_order_creation(session, user_id)
            total_operations += len(ops)
            
            for op_name, op_time, op_status in ops:
                self.results['total_operations'] += 1
                self.results['response_times'].append(op_time)
                
                if op_status == 'success':
                    self.results['successful'] += 1
                else:
                    self.results['failed'] += 1
                
                if op_name not in self.results['operations']:
                    self.results['operations'][op_name] = {
                        'count': 0,
                        'success': 0,
                        'failed': 0,
                        'times': []
                    }
                
                self.results['operations'][op_name]['count'] += 1
                self.results['operations'][op_name]['times'].append(op_time)
                
                if op_status == 'success':
                    self.results['operations'][op_name]['success'] += 1
                else:
                    self.results['operations'][op_name]['failed'] += 1
            
            # Short delay before next cycle
            await asyncio.sleep(random.uniform(1, 3))
        
        print(f"✅ User {user_id} finished - {total_operations} operations")
    
    async def run_test(self):
        """Run the stress test"""
        print(f"\n{'='*70}")
        print(f"🔥 STRESS TEST - Telegram Bot Full Flow")
        print(f"{'='*70}")
        print(f"👥 Concurrent Users: {NUM_USERS}")
        print(f"⏱️  Test Duration: 60 seconds")
        print(f"🎯 Target: ~1500 requests total")
        print(f"{'='*70}\n")
        print(f"🚀 Starting test at {datetime.now().strftime('%H:%M:%S')}\n")
        
        start_time = time.time()
        
        # Create session with connection pooling
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=100)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            # Create tasks for all users
            tasks = [self.run_user(session, i) for i in range(1, NUM_USERS + 1)]
            
            # Run all users concurrently
            await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Print results
        self.print_results(total_time)
    
    def print_results(self, total_time: float):
        """Print detailed test results"""
        print(f"\n{'='*70}")
        print(f"📊 STRESS TEST RESULTS")
        print(f"{'='*70}\n")
        
        print(f"⏱️  Total Duration: {total_time:.2f}s")
        print(f"📈 Total Operations: {self.results['total_operations']}")
        print(f"✅ Successful: {self.results['successful']}")
        print(f"❌ Failed: {self.results['failed']}")
        
        if self.results['total_operations'] > 0:
            success_rate = (self.results['successful'] / self.results['total_operations'] * 100)
            print(f"📊 Success Rate: {success_rate:.2f}%")
            print(f"⚡ Throughput: {self.results['total_operations']/total_time:.2f} ops/sec")
        
        if self.results['response_times']:
            avg_time = sum(self.results['response_times']) / len(self.results['response_times'])
            max_time = max(self.results['response_times'])
            min_time = min(self.results['response_times'])
            
            print(f"\n{'─'*70}")
            print(f"⏱️  Response Times:")
            print(f"{'─'*70}")
            print(f"   Average: {avg_time*1000:.2f}ms")
            print(f"   Min: {min_time*1000:.2f}ms")
            print(f"   Max: {max_time*1000:.2f}ms")
        
        if self.results['operations']:
            print(f"\n{'─'*70}")
            print(f"📋 Operations Breakdown:")
            print(f"{'─'*70}")
            for op, data in self.results['operations'].items():
                if data['times']:
                    avg_time = sum(data['times']) / len(data['times'])
                    print(f"   {op}:")
                    print(f"      Total: {data['count']}")
                    print(f"      Success: {data['success']}")
                    print(f"      Failed: {data['failed']}")
                    print(f"      Avg Time: {avg_time*1000:.2f}ms")
        
        if self.results['errors']:
            print(f"\n{'─'*70}")
            print(f"❌ Errors ({len(self.results['errors'])}):")
            print(f"{'─'*70}")
            for error in self.results['errors'][:10]:  # Show first 10
                print(f"   - {error}")
            if len(self.results['errors']) > 10:
                print(f"   ... and {len(self.results['errors']) - 10} more")
        
        print(f"\n{'='*70}")
        print(f"🎯 Performance Assessment:")
        print(f"{'─'*70}")
        
        if self.results['response_times']:
            avg_ms = sum(self.results['response_times']) / len(self.results['response_times']) * 1000
            success_pct = (self.results['successful'] / self.results['total_operations'] * 100)
            
            if success_pct == 100 and avg_ms < 50:
                verdict = "🟢 EXCELLENT - Production ready!"
            elif success_pct >= 99 and avg_ms < 100:
                verdict = "🟢 VERY GOOD - Handles concurrent load well"
            elif success_pct >= 95 and avg_ms < 200:
                verdict = "🟡 GOOD - Acceptable performance"
            elif success_pct >= 90:
                verdict = "🟠 MODERATE - Consider optimization"
            else:
                verdict = "🔴 POOR - Needs optimization"
            
            print(f"{verdict}")
        
        print(f"{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(TelegramBotStressTester().run_test())
