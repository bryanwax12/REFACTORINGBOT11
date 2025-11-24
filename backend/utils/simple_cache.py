"""
Simple in-memory cache for frequently accessed data
Reduces MongoDB queries and speeds up bot responses
"""
import time
import logging
from typing import Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class SimpleCache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        
    def get(self, key: str, ttl: int = 60) -> Optional[Any]:
        """
        Get value from cache if not expired
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
            
        Returns:
            Cached value or None if expired/not found
        """
        if key not in self._cache:
            return None
            
        timestamp = self._timestamps.get(key, 0)
        if time.time() - timestamp > ttl:
            # Expired
            del self._cache[key]
            del self._timestamps[key]
            return None
            
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        """Set value in cache"""
        self._cache[key] = value
        self._timestamps[key] = time.time()
        
    def delete(self, key: str):
        """Delete value from cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]
            
    def clear(self):
        """Clear all cache"""
        self._cache.clear()
        self._timestamps.clear()
        
    def size(self) -> int:
        """Get cache size"""
        return len(self._cache)


# Global cache instance
cache = SimpleCache()


def cached(ttl: int = 60, key_prefix: str = ""):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        
    Usage:
        @cached(ttl=120, key_prefix="user")
        async def get_user(telegram_id):
            return await db.users.find_one({"telegram_id": telegram_id})
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key, ttl)
            if cached_value is not None:
                logger.debug(f"💨 Cache HIT: {cache_key[:50]}...")
                return cached_value
            
            # Cache miss - call function
            logger.debug(f"❌ Cache MISS: {cache_key[:50]}...")
            result = await func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                cache.set(cache_key, result)
                
            return result
            
        return wrapper
    return decorator


# Cache statistics
def get_cache_stats() -> dict:
    """Get cache statistics"""
    return {
        "size": cache.size(),
        "keys": len(cache._cache)
    }


def clear_user_cache(telegram_id: int):
    """Clear cache for specific user"""
    # Clear all keys containing this telegram_id
    keys_to_delete = [k for k in cache._cache.keys() if str(telegram_id) in k]
    for key in keys_to_delete:
        cache.delete(key)
    logger.info(f"🗑️ Cleared cache for user {telegram_id} ({len(keys_to_delete)} keys)")
