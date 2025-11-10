"""Caching utilities"""
import logging
from time import time

logger = logging.getLogger(__name__)

# Simple in-memory cache for frequently accessed settings
SETTINGS_CACHE = {
    'api_mode': None,
    'api_mode_timestamp': None,
    'maintenance_mode': None,
    'maintenance_timestamp': None
}
CACHE_TTL = 60  # Cache TTL in seconds

async def get_api_mode_cached(db):
    """Get API mode with caching to reduce DB queries"""
    current_time = time()
    
    # Check if cache is valid
    if (SETTINGS_CACHE['api_mode'] is not None and 
        SETTINGS_CACHE['api_mode_timestamp'] is not None and
        current_time - SETTINGS_CACHE['api_mode_timestamp'] < CACHE_TTL):
        return SETTINGS_CACHE['api_mode']
    
    # Cache miss or expired - fetch from DB
    try:
        setting = await db.settings.find_one({"key": "api_mode"})
        api_mode = setting.get("value", "production") if setting else "production"
        
        # Update cache
        SETTINGS_CACHE['api_mode'] = api_mode
        SETTINGS_CACHE['api_mode_timestamp'] = current_time
        
        return api_mode
    except Exception as e:
        logger.error(f"Error fetching api_mode: {e}")
        return SETTINGS_CACHE['api_mode'] or "production"
