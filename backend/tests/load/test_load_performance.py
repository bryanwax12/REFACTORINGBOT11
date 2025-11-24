"""
Load Testing Script
Tests application performance under various load scenarios
"""
import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict
from datetime import datetime
import os


class LoadTester:
    """Load testing utility"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results = []
    
    async def make_request(self, session: aiohttp.ClientSession, endpoint: str, method: str = "GET") -> Dict:
        """Make a single request and measure response time"""
        start_time = time.time()
        try:
            async with session.request(method, f"{self.base_url}{endpoint}") as response:
                await response.text()
                elapsed = (time.time() - start_time) * 1000  # Convert to ms
                return {
                    "endpoint": endpoint,
                    "status": response.status,
                    "time_ms": elapsed,
                    "success": response.status == 200
                }
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                "endpoint": endpoint,
                "status": 0,
                "time_ms": elapsed,
                "success": False,
                "error": str(e)
            }
    
    async def run_concurrent_requests(self, endpoint: str, num_requests: int) -> List[Dict]:
        """Run multiple concurrent requests to an endpoint"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.make_request(session, endpoint) for _ in range(num_requests)]
            results = await asyncio.gather(*tasks)
            return results
    
    async def run_sequential_requests(self, endpoint: str, num_requests: int) -> List[Dict]:
        """Run sequential requests to an endpoint"""
        results = []
        async with aiohttp.ClientSession() as session:
            for _ in range(num_requests):
                result = await self.make_request(session, endpoint)
                results.append(result)
        return results
    
    def analyze_results(self, results: List[Dict]) -> Dict:
        """Analyze test results and generate statistics"""
        times = [r["time_ms"] for r in results if r["success"]]
        successes = sum(1 for r in results if r["success"])
        failures = len(results) - successes
        
        if not times:
            return {
                "error": "No successful requests",
                "total_requests": len(results),
                "failures": failures
            }
        
        return {
            "total_requests": len(results),
            "successful": successes,
            "failed": failures,
            "success_rate": (successes / len(results)) * 100,
            "response_times": {
                "min_ms": min(times),
                "max_ms": max(times),
                "mean_ms": statistics.mean(times),
                "median_ms": statistics.median(times),
                "p95_ms": statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times),
                "p99_ms": statistics.quantiles(times, n=100)[98] if len(times) > 100 else max(times)
            }
        }
    
    async def test_endpoint_load(self, endpoint: str, concurrent: int = 10, total: int = 100):
        """Test an endpoint with specified load"""
        print(f"\n🔄 Testing: {endpoint}")
        print(f"   Concurrent: {concurrent}, Total: {total}")
        
        # Run in batches
        all_results = []
        batch_size = concurrent
        num_batches = total // batch_size
        
        for i in range(num_batches):
            print(f"   Batch {i+1}/{num_batches}...", end="")
            batch_results = await self.run_concurrent_requests(endpoint, batch_size)
            all_results.extend(batch_results)
            print(" ✅")
        
        # Analyze results
        stats = self.analyze_results(all_results)
        
        print(f"\n📊 Results for {endpoint}:")
        print(f"   Success Rate: {stats['success_rate']:.1f}%")
        print(f"   Mean Response: {stats['response_times']['mean_ms']:.1f}ms")
        print(f"   Median: {stats['response_times']['median_ms']:.1f}ms")
        print(f"   P95: {stats['response_times']['p95_ms']:.1f}ms")
        print(f"   P99: {stats['response_times']['p99_ms']:.1f}ms")
        
        return stats


async def run_load_tests():
    """Run comprehensive load tests"""
    # Get backend URL from environment
    backend_url = os.environ.get('BACKEND_URL', 'http://localhost:8001')
    
    tester = LoadTester(backend_url)
    
    print("="*60)
    print("🚀 LOAD TESTING STARTED")
    print(f"   Target: {backend_url}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    test_scenarios = [
        # Scenario 1: Light load on health endpoint
        {
            "name": "Health Check - Light Load",
            "endpoint": "/api/monitoring/health",
            "concurrent": 5,
            "total": 50
        },
        # Scenario 2: Medium load on metrics
        {
            "name": "Metrics - Medium Load",
            "endpoint": "/api/monitoring/metrics",
            "concurrent": 10,
            "total": 100
        },
        # Scenario 3: Heavy load on health
        {
            "name": "Health Check - Heavy Load",
            "endpoint": "/api/monitoring/health",
            "concurrent": 20,
            "total": 200
        },
        # Scenario 4: Stats endpoints
        {
            "name": "User Stats - Normal Load",
            "endpoint": "/api/monitoring/stats/users",
            "concurrent": 10,
            "total": 50
        },
        {
            "name": "Order Stats - Normal Load",
            "endpoint": "/api/monitoring/stats/orders",
            "concurrent": 10,
            "total": 50
        }
    ]
    
    all_results = {}
    
    for scenario in test_scenarios:
        print(f"\n{'='*60}")
        print(f"📋 Scenario: {scenario['name']}")
        print(f"{'='*60}")
        
        results = await tester.test_endpoint_load(
            scenario['endpoint'],
            concurrent=scenario['concurrent'],
            total=scenario['total']
        )
        
        all_results[scenario['name']] = results
        
        # Brief pause between scenarios
        await asyncio.sleep(1)
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 LOAD TEST SUMMARY")
    print(f"{'='*60}")
    
    for name, stats in all_results.items():
        status = "✅ PASS" if stats['success_rate'] >= 95 else "⚠️ WARNING"
        print(f"\n{status} {name}")
        print(f"   Success: {stats['success_rate']:.1f}%")
        print(f"   Mean: {stats['response_times']['mean_ms']:.1f}ms")
        print(f"   P95: {stats['response_times']['p95_ms']:.1f}ms")
    
    print(f"\n{'='*60}")
    print("✅ LOAD TESTING COMPLETED")
    print(f"{'='*60}\n")
    
    return all_results


# Quick test function
async def quick_test():
    """Quick load test for debugging"""
    backend_url = os.environ.get('BACKEND_URL', 'http://localhost:8001')
    tester = LoadTester(backend_url)
    
    print("🔍 Quick Load Test")
    await tester.test_endpoint_load("/api/monitoring/health", concurrent=5, total=20)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        asyncio.run(quick_test())
    else:
        asyncio.run(run_load_tests())
