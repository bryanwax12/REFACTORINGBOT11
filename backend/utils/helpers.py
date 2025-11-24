"""Helper utility functions"""
import random
import logging
import re
from typing import Optional
from datetime import datetime

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


def sanitize_string(text: str, max_length: int = 200) -> str:
    """
    Sanitize user input string
    
    Args:
        text: Input text
        max_length: Maximum length
        
    Returns:
        Sanitized string
    """
    if not text:
        return ""
    
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\-.,#/()&]', '', text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()


def format_phone_number(phone: str) -> Optional[str]:
    """
    Format phone number to standard format
    
    Args:
        phone: Phone number string
        
    Returns:
        Formatted phone or None if invalid
    """
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Check if valid US number
    if len(digits) == 10:
        return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    return None


def generate_order_id(telegram_id: int) -> str:
    """
    Generate unique order ID
    
    Args:
        telegram_id: User's Telegram ID
        
    Returns:
        Order ID in format: ORD-{timestamp}-{random}
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = random.randint(1000, 9999)
    
    return f"ORD-{timestamp}-{random_part}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text with ellipsis
    
    Args:
        text: Input text
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def calculate_discount(amount: float, discount_percent: float) -> float:
    """
    Calculate discounted amount
    
    Args:
        amount: Original amount
        discount_percent: Discount percentage (0-100)
        
    Returns:
        Discounted amount
    """
    if discount_percent <= 0:
        return amount
    
    discount = amount * (discount_percent / 100)
    return max(0, amount - discount)


def format_currency(amount: float) -> str:
    """
    Format amount as USD currency
    
    Args:
        amount: Amount to format
        
    Returns:
        Formatted currency string
    """
    return f"${amount:.2f}"
