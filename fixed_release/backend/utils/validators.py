"""
Input Validation Utilities
Centralized validation functions for order data
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


# ============================================================
# NAME VALIDATION
# ============================================================

def validate_name(name: str) -> Tuple[bool, str]:
    """
    Validate person name (Latin characters only)
    
    Rules:
    - Min 2 characters, max 50
    - Only Latin letters, spaces, dots, hyphens, apostrophes
    - No Cyrillic or other non-Latin characters
    
    Returns:
        (is_valid, error_message)
    """
    name = name.strip()
    
    # Check for Cyrillic
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in name):
        return False, "❌ Используйте только английские буквы (латиницу). Пример: John Smith"
    
    # Check length
    if len(name) < 2:
        return False, "❌ Имя слишком короткое. Введите полное имя (минимум 2 символа)"
    
    if len(name) > 50:
        return False, "❌ Имя слишком длинное. Максимум 50 символов"
    
    # Check characters (only Latin letters, spaces, dots, hyphens, apostrophes)
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in name):
        return False, "❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки"
    
    return True, ""


# ============================================================
# ADDRESS VALIDATION
# ============================================================

def validate_address(address: str, field_name: str = "Адрес") -> Tuple[bool, str]:
    """
    Validate street address
    
    Rules:
    - Min 3 characters, max 100
    - Only Latin letters, numbers, spaces, and common punctuation
    - No Cyrillic
    
    Returns:
        (is_valid, error_message)
    """
    address = address.strip()
    
    # Check for Cyrillic
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address):
        return False, f"❌ {field_name}: Используйте только английские буквы (латиницу)"
    
    # Check length
    if len(address) < 3:
        return False, f"❌ {field_name} слишком короткий (минимум 3 символа)"
    
    if len(address) > 100:
        return False, f"❌ {field_name} слишком длинный (максимум 100 символов)"
    
    # Check characters (Latin, digits, spaces, common punctuation)
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-#&/")
    if not all(c in allowed_chars for c in address):
        return False, f"❌ {field_name}: Используйте только английские буквы и цифры"
    
    return True, ""


# ============================================================
# CITY VALIDATION
# ============================================================

def validate_city(city: str) -> Tuple[bool, str]:
    """
    Validate city name
    
    Rules:
    - Min 2 characters, max 50
    - Only Latin letters, spaces, hyphens, apostrophes
    - No Cyrillic or numbers
    
    Returns:
        (is_valid, error_message)
    """
    city = city.strip()
    
    # Check for Cyrillic
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in city):
        return False, "❌ Используйте только английские буквы (латиницу). Пример: New York"
    
    # Check length
    if len(city) < 2:
        return False, "❌ Название города слишком короткое"
    
    if len(city) > 50:
        return False, "❌ Название города слишком длинное (максимум 50 символов)"
    
    # Only Latin letters, spaces, hyphens, apostrophes (no numbers)
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in "-'")) for c in city):
        return False, "❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы"
    
    return True, ""


# ============================================================
# STATE VALIDATION
# ============================================================

def validate_state(state: str) -> Tuple[bool, str]:
    """
    Validate US state code
    
    Rules:
    - Exactly 2 uppercase letters
    - Must be valid US state code
    
    Returns:
        (is_valid, error_message)
    """
    state = state.strip().upper()
    
    # List of valid US state codes
    valid_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'DC', 'PR', 'VI', 'GU', 'AS', 'MP'
    }
    
    if len(state) != 2:
        return False, "❌ Введите 2-буквенный код штата (например: CA, NY, TX)"
    
    if not state.isalpha():
        return False, "❌ Код штата должен содержать только буквы"
    
    if state not in valid_states:
        return False, f"❌ Неверный код штата: {state}\nПример: CA, NY, TX, FL"
    
    return True, ""


# ============================================================
# ZIP CODE VALIDATION
# ============================================================

def validate_zip(zip_code: str) -> Tuple[bool, str]:
    """
    Validate US ZIP code
    
    Rules:
    - 5 digits (12345)
    - OR 5+4 digits (12345-6789)
    
    Returns:
        (is_valid, error_message)
    """
    zip_code = zip_code.strip()
    
    # Pattern: 5 digits or 5+4 digits
    pattern = r'^\d{5}(-\d{4})?$'
    
    if not re.match(pattern, zip_code):
        return False, "❌ Неверный формат ZIP. Введите 5 цифр (например: 12345)"
    
    return True, ""


# ============================================================
# PHONE NUMBER VALIDATION
# ============================================================

def validate_phone(phone: str) -> Tuple[bool, str, str]:
    """
    Validate and format phone number
    
    Rules:
    - 10 or 11 digits
    - Formats to +1XXXXXXXXXX
    
    Returns:
        (is_valid, error_message, formatted_phone)
    """
    phone = phone.strip()
    
    # Check if phone starts with valid characters
    if not phone or (phone[0] not in '0123456789+'):
        return False, "❌ Неверный формат. Телефон должен начинаться с + или цифры", ""
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check length (10 or 11 digits)
    if len(digits_only) < 10 or len(digits_only) > 11:
        return False, "❌ Неверный формат. Введите 10 цифр (например: 1234567890)", ""
    
    # Format phone number
    if len(digits_only) == 11 and digits_only[0] == '1':
        formatted = f"+{digits_only}"
    elif len(digits_only) == 10:
        formatted = f"+1{digits_only}"
    else:
        formatted = f"+{digits_only}"
    
    return True, "", formatted


# ============================================================
# PARCEL DIMENSIONS VALIDATION
# ============================================================

def validate_weight(weight_str: str) -> Tuple[bool, str, float]:
    """
    Validate parcel weight
    
    Rules:
    - Positive number
    - Max 150 lbs
    - Min 0.1 lbs
    
    Returns:
        (is_valid, error_message, weight_float)
    """
    try:
        weight = float(weight_str.strip())
        
        if weight <= 0:
            return False, "❌ Вес должен быть больше 0", 0.0
        
        if weight < 0.1:
            return False, "❌ Минимальный вес: 0.1 фунта", 0.0
        
        if weight > 150:
            return False, "❌ Максимальный вес: 150 фунтов", 0.0
        
        return True, "", weight
        
    except ValueError:
        return False, "❌ Введите число (например: 5 или 5.5)", 0.0


def validate_dimension(dimension_str: str, dimension_name: str) -> Tuple[bool, str, float]:
    """
    Validate parcel dimension (length, width, height)
    
    Rules:
    - Positive number
    - Max 108 inches
    - Min 0.1 inches
    
    Returns:
        (is_valid, error_message, dimension_float)
    """
    try:
        dimension = float(dimension_str.strip())
        
        if dimension <= 0:
            return False, f"❌ {dimension_name} должен быть больше 0", 0.0
        
        if dimension < 0.1:
            return False, "❌ Минимум: 0.1 дюйма", 0.0
        
        if dimension > 108:
            return False, "❌ Максимум: 108 дюймов (9 футов)", 0.0
        
        return True, "", dimension
        
    except ValueError:
        return False, "❌ Введите число (например: 10 или 10.5)", 0.0
