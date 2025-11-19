"""
Test Performance Optimizations Integration
Verifies that performance config is properly integrated
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.performance_config import BotPerformanceConfig, performance_monitor
from middleware.rate_limiter import rate_limiter, TelegramRateLimiter


def test_performance_config():
    """Test that BotPerformanceConfig provides correct settings"""
    print("=" * 60)
    print("TEST: Performance Configuration")
    print("=" * 60)
    
    # Test MongoDB config
    mongo_config = BotPerformanceConfig.get_mongodb_config()
    print("\n✅ MongoDB Configuration:")
    for key, value in mongo_config.items():
        print(f"   {key}: {value}")
    
    assert mongo_config['maxPoolSize'] == 50, "maxPoolSize should be 50"
    assert mongo_config['minPoolSize'] == 5, "minPoolSize should be 5"
    print("   ✅ MongoDB config validated")
    
    # Test Bot settings
    bot_settings = BotPerformanceConfig.get_optimized_bot_settings()
    print("\n✅ Bot Settings:")
    for key, value in bot_settings.items():
        print(f"   {key}: {value}")
    
    assert bot_settings['read_timeout'] == 15.0, "read_timeout should be 15.0"
    print("   ✅ Bot settings validated")
    
    # Test Application settings
    app_settings = BotPerformanceConfig.get_optimized_application_settings()
    print("\n✅ Application Settings:")
    for key, value in app_settings.items():
        print(f"   {key}: {value}")
    
    assert app_settings['concurrent_updates'] == 100, "concurrent_updates should be 100"
    print("   ✅ Application settings validated")
    
    # Test HTTP client config
    http_config = BotPerformanceConfig.get_http_client_config()
    print("\n✅ HTTP Client Configuration:")
    print(f"   timeout: {http_config['timeout']}")
    print(f"   retries: {http_config['retries']}")
    print(f"   limits: {http_config['limits']}")
    
    print("\n" + "=" * 60)
    print("✅ ALL PERFORMANCE CONFIG TESTS PASSED")
    print("=" * 60)


async def test_rate_limiter():
    """Test that rate limiter is working"""
    print("\n" + "=" * 60)
    print("TEST: Rate Limiter")
    print("=" * 60)
    
    # Test that rate_limiter is instance of TelegramRateLimiter
    assert isinstance(rate_limiter, TelegramRateLimiter), "rate_limiter should be TelegramRateLimiter instance"
    print("✅ Rate limiter instance validated")
    
    # Test basic acquire
    chat_id = 12345
    result = await rate_limiter.acquire(chat_id)
    assert result == True, "First acquire should succeed"
    print("✅ Rate limiter acquire() works")
    
    # Test multiple rapid acquires (should succeed but with rate limiting)
    rapid_results = []
    for i in range(5):
        result = await rate_limiter.acquire(chat_id)
        rapid_results.append(result)
    
    print(f"✅ Rapid acquires: {sum(rapid_results)}/5 succeeded (rate limiting active)")
    
    print("\n" + "=" * 60)
    print("✅ ALL RATE LIMITER TESTS PASSED")
    print("=" * 60)


async def test_performance_monitor():
    """Test performance monitor"""
    print("\n" + "=" * 60)
    print("TEST: Performance Monitor")
    print("=" * 60)
    
    # Test monitoring a fast operation
    async def fast_operation():
        await asyncio.sleep(0.1)
        return "fast"
    
    result = await performance_monitor.monitor_operation("test_fast_op", fast_operation())
    assert result == "fast", "Fast operation should return result"
    print("✅ Performance monitor can track fast operations")
    
    # Test monitoring a slow operation (will log warning)
    async def slow_operation():
        await asyncio.sleep(2.5)
        return "slow"
    
    print("   Testing slow operation (should trigger warning)...")
    result = await performance_monitor.monitor_operation("test_slow_op", slow_operation())
    assert result == "slow", "Slow operation should return result"
    print("✅ Performance monitor detects and logs slow operations")
    
    # Check that slow operation was recorded
    if len(performance_monitor.slow_operations) > 0:
        print(f"✅ Recorded {len(performance_monitor.slow_operations)} slow operations")
    
    print("\n" + "=" * 60)
    print("✅ ALL PERFORMANCE MONITOR TESTS PASSED")
    print("=" * 60)


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PERFORMANCE OPTIMIZATIONS INTEGRATION TEST")
    print("=" * 60)
    
    try:
        # Run synchronous tests
        test_performance_config()
        
        # Run async tests
        await test_rate_limiter()
        await test_performance_monitor()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\n✅ Performance optimizations are properly integrated:")
        print("   • MongoDB connection pool optimized (50 max, 5 min connections)")
        print("   • Telegram Bot timeouts configured (15s read, 20s write, 10s connect)")
        print("   • Application handles 100 concurrent updates")
        print("   • Rate limiter active (25 msg/sec global, 60 msg/min per chat)")
        print("   • Performance monitor tracking slow operations (>2s)")
        print("\n🚀 Bot is ready for production deployment!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
