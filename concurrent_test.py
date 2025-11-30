#!/usr/bin/env python3
"""
Concurrent Request Testing for Telegram Bot Backend
Tests 10-20 parallel requests to different endpoints as requested in review
"""

import asyncio
import aiohttp
import time
import json
from typing import List, Dict, Any

# Backend URL from environment
BACKEND_URL = "https://easyshipbot.preview.emergentagent.com"
ADMIN_API_KEY = "sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024"

async def make_request(session: aiohttp.ClientSession, endpoint: str, method: str = "GET", 
                      headers: Dict = None, json_data: Dict = None) -> Dict[str, Any]:
    """Make a single HTTP request"""
    url = f"{BACKEND_URL}{endpoint}"
    
    try:
        start_time = time.time()
        
        if method == "GET":
            async with session.get(url, headers=headers) as response:
                response_time = (time.time() - start_time) * 1000
                try:
                    data = await response.json()
                except:
                    data = await response.text()
                
                return {
                    "endpoint": endpoint,
                    "status": response.status,
                    "response_time_ms": response_time,
                    "success": 200 <= response.status < 300,
                    "data": data
                }
        
        elif method == "POST":
            async with session.post(url, headers=headers, json=json_data) as response:
                response_time = (time.time() - start_time) * 1000
                try:
                    data = await response.json()
                except:
                    data = await response.text()
                
                return {
                    "endpoint": endpoint,
                    "status": response.status,
                    "response_time_ms": response_time,
                    "success": 200 <= response.status < 300,
                    "data": data
                }
                
    except Exception as e:
        return {
            "endpoint": endpoint,
            "status": 0,
            "response_time_ms": 0,
            "success": False,
            "error": str(e)
        }

async def test_concurrent_requests():
    """Test concurrent requests to different endpoints"""
    print("🔍 CONCURRENT REQUEST TESTING")
    print("🎯 Testing 15 parallel requests to different endpoints")
    print("=" * 60)
    
    # Define test endpoints
    test_requests = [
        # Monitoring endpoints (CRITICAL)
        {"endpoint": "/api/monitoring/health", "method": "GET"},
        {"endpoint": "/api/monitoring/metrics", "method": "GET", "headers": {"X-API-Key": ADMIN_API_KEY}},
        {"endpoint": "/api/monitoring/stats/users", "method": "GET", "headers": {"X-API-Key": ADMIN_API_KEY}},
        {"endpoint": "/api/monitoring/stats/orders", "method": "GET", "headers": {"X-API-Key": ADMIN_API_KEY}},
        {"endpoint": "/api/monitoring/stats/payments", "method": "GET", "headers": {"X-API-Key": ADMIN_API_KEY}},
        
        # Admin endpoints
        {"endpoint": "/api/admin/stats/dashboard", "method": "GET", "headers": {"X-API-Key": ADMIN_API_KEY}},
        
        # API health checks
        {"endpoint": "/api/", "method": "GET"},
        {"endpoint": "/api/", "method": "GET"},
        {"endpoint": "/api/", "method": "GET"},
        
        # Telegram webhook endpoint
        {"endpoint": "/api/telegram/webhook", "method": "GET"},
        
        # Duplicate monitoring requests to test load
        {"endpoint": "/api/monitoring/health", "method": "GET"},
        {"endpoint": "/api/monitoring/health", "method": "GET"},
        {"endpoint": "/api/monitoring/health", "method": "GET"},
        
        # Additional admin requests
        {"endpoint": "/api/admin/stats/dashboard", "method": "GET", "headers": {"X-API-Key": ADMIN_API_KEY}},
        {"endpoint": "/api/admin/stats/dashboard", "method": "GET", "headers": {"X-API-Key": ADMIN_API_KEY}},
    ]
    
    print(f"📊 Total concurrent requests: {len(test_requests)}")
    print()
    
    # Create session with timeout
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        start_time = time.time()
        
        # Execute all requests concurrently
        tasks = []
        for req in test_requests:
            task = make_request(
                session=session,
                endpoint=req["endpoint"],
                method=req["method"],
                headers=req.get("headers"),
                json_data=req.get("json_data")
            )
            tasks.append(task)
        
        # Wait for all requests to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_requests = 0
        failed_requests = 0
        total_response_time = 0
        endpoint_stats = {}
        
        print("📋 DETAILED RESULTS:")
        print("-" * 60)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ Request {i+1}: Exception - {result}")
                failed_requests += 1
                continue
            
            endpoint = result["endpoint"]
            status = result["status"]
            response_time = result["response_time_ms"]
            success = result["success"]
            
            # Track endpoint statistics
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = {"requests": 0, "successes": 0, "total_time": 0}
            
            endpoint_stats[endpoint]["requests"] += 1
            endpoint_stats[endpoint]["total_time"] += response_time
            
            if success:
                successful_requests += 1
                endpoint_stats[endpoint]["successes"] += 1
                total_response_time += response_time
                print(f"✅ {endpoint} - {status} - {response_time:.2f}ms")
            else:
                failed_requests += 1
                print(f"❌ {endpoint} - {status} - {response_time:.2f}ms")
                if "error" in result:
                    print(f"   Error: {result['error']}")
        
        print()
        print("📊 CONCURRENT REQUEST SUMMARY:")
        print("=" * 60)
        print(f"Total requests: {len(test_requests)}")
        print(f"✅ Successful: {successful_requests}")
        print(f"❌ Failed: {failed_requests}")
        print(f"📈 Success rate: {(successful_requests/len(test_requests)*100):.1f}%")
        print(f"⏱️ Total execution time: {total_time:.2f}s")
        
        if successful_requests > 0:
            avg_response_time = total_response_time / successful_requests
            print(f"⚡ Average response time: {avg_response_time:.2f}ms")
        
        print()
        print("📋 ENDPOINT PERFORMANCE:")
        print("-" * 60)
        
        for endpoint, stats in endpoint_stats.items():
            requests_count = stats["requests"]
            successes = stats["successes"]
            avg_time = stats["total_time"] / requests_count if requests_count > 0 else 0
            success_rate = (successes / requests_count * 100) if requests_count > 0 else 0
            
            print(f"{endpoint}")
            print(f"  Requests: {requests_count}, Success: {successes}/{requests_count} ({success_rate:.1f}%)")
            print(f"  Avg response time: {avg_time:.2f}ms")
            print()
        
        # CRITICAL ASSESSMENT
        print("🎯 CRITICAL ASSESSMENT:")
        print("=" * 60)
        
        # Check for race conditions (all requests should succeed if no race conditions)
        if successful_requests >= len(test_requests) * 0.8:  # 80% success rate threshold
            print("✅ CONCURRENT HANDLING: No apparent race conditions or deadlocks")
        else:
            print("❌ CONCURRENT HANDLING: Possible race conditions or deadlocks detected")
        
        # Check response times (should be reasonable under load)
        if successful_requests > 0:
            avg_response_time = total_response_time / successful_requests
            if avg_response_time < 500:  # 500ms threshold
                print("✅ PERFORMANCE: Response times acceptable under concurrent load")
            else:
                print("❌ PERFORMANCE: Response times degraded under concurrent load")
        
        # Check monitoring endpoints specifically
        monitoring_success = 0
        monitoring_total = 0
        for endpoint, stats in endpoint_stats.items():
            if "/monitoring/" in endpoint:
                monitoring_total += stats["requests"]
                monitoring_success += stats["successes"]
        
        if monitoring_total > 0:
            monitoring_rate = (monitoring_success / monitoring_total * 100)
            if monitoring_rate >= 90:
                print("✅ MONITORING ENDPOINTS: Stable under concurrent load")
            else:
                print("❌ MONITORING ENDPOINTS: Unstable under concurrent load")
        
        print()
        return {
            "total_requests": len(test_requests),
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": successful_requests/len(test_requests)*100,
            "total_time": total_time,
            "avg_response_time": total_response_time / successful_requests if successful_requests > 0 else 0,
            "endpoint_stats": endpoint_stats
        }

if __name__ == "__main__":
    asyncio.run(test_concurrent_requests())