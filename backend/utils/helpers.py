"""Helper utility functions"""
import random
import logging

logger = logging.getLogger(__name__)

def generate_random_phone():
    """Generate a random valid US phone number"""
    area_code = random.randint(200, 999)
    exchange = random.randint(200, 999)
    number = random.randint(1000, 9999)
    return f"+1{area_code}{exchange}{number}"

def clear_settings_cache():
    """Clear settings cache when settings are updated"""
    from .cache import SETTINGS_CACHE
    SETTINGS_CACHE['api_mode'] = None
    SETTINGS_CACHE['api_mode_timestamp'] = None
    SETTINGS_CACHE['maintenance_mode'] = None
    SETTINGS_CACHE['maintenance_timestamp'] = None
    logger.info("Settings cache cleared")
