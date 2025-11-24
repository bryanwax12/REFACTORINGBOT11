"""
Input validation utilities for order flow
"""
import re
from typing import Tuple

def validate_name(name: str) -> Tuple[bool, str]:
    """
    Validate name field
    Returns: (is_valid, error_message)
    """
    name = name.strip()
    
    if not name:
        return False, "⚠️ Имя не может быть пустым."
    
    if len(name) < 2:
        return False, "⚠️ Имя должно содержать минимум 2 символа."
    
    if len(name) > 50:
        return False, "⚠️ Имя слишком длинное (максимум 50 символов)."
    
    return True, ""


def validate_address(address: str) -> Tuple[bool, str]:
    """
    Validate address field
    Returns: (is_valid, error_message)
    """
    address = address.strip()
    
    if not address:
        return False, "⚠️ Адрес не может быть пустым."
    
    if len(address) < 5:
        return False, "⚠️ Адрес должен содержать минимум 5 символов.\n\nНапример: 123 Main St"
    
    if len(address) > 100:
        return False, "⚠️ Адрес слишком длинный (максимум 100 символов)."
    
    return True, ""


def validate_city(city: str) -> Tuple[bool, str]:
    """
    Validate city field
    Returns: (is_valid, error_message)
    """
    city = city.strip()
    
    if not city:
        return False, "⚠️ Город не может быть пустым."
    
    if len(city) < 2:
        return False, "⚠️ Название города должно содержать минимум 2 символа."
    
    if len(city) > 50:
        return False, "⚠️ Название города слишком длинное (максимум 50 символов)."
    
    # Check if city contains only letters, spaces, hyphens, and periods
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s\.\-]+$', city):
        return False, "⚠️ Название города может содержать только буквы, пробелы, точки и дефисы."
    
    return True, ""


def validate_state(state: str) -> Tuple[bool, str]:
    """
    Validate US state code
    Returns: (is_valid, error_message)
    """
    state = state.strip().upper()
    
    if len(state) != 2:
        return False, "⚠️ Штат должен быть указан 2-буквенным кодом.\n\nНапример: CA, NY, TX, FL\n\nПожалуйста, введите код штата:"
    
    if not state.isalpha():
        return False, "⚠️ Код штата должен содержать только буквы.\n\nНапример: CA, NY, TX, FL"
    
    return True, ""


def validate_zip(zip_code: str) -> Tuple[bool, str]:
    """
    Validate US ZIP code
    Returns: (is_valid, error_message)
    """
    zip_code = zip_code.strip()
    
    if not zip_code.isdigit():
        return False, "⚠️ Почтовый индекс должен содержать только цифры.\n\nНапример: 94102, 10001, 90210"
    
    if len(zip_code) != 5:
        return False, "⚠️ Почтовый индекс должен содержать ровно 5 цифр.\n\nНапример: 94102, 10001, 90210"
    
    return True, ""


def validate_phone(phone: str, required: bool = False) -> Tuple[bool, str]:
    """
    Validate phone number (US format)
    Returns: (is_valid, error_message)
    """
    phone = phone.strip()
    
    # If empty and not required, it's valid
    if not phone and not required:
        return True, ""
    
    if not phone and required:
        return False, "⚠️ Телефон обязателен."
    
    # Remove common formatting characters
    phone_digits = re.sub(r'[\s\-\(\)\+]', '', phone)
    
    # Check if it's all digits after cleaning
    if not phone_digits.isdigit():
        return False, "⚠️ Телефон должен содержать только цифры.\n\nНапример: +1234567890 или 1234567890"
    
    # US phone numbers should be 10 or 11 digits (with country code)
    if len(phone_digits) < 10:
        return False, "⚠️ Телефон слишком короткий.\n\nНапример: +14155551234 или 4155551234"
    
    if len(phone_digits) > 15:
        return False, "⚠️ Телефон слишком длинный."
    
    return True, ""


def validate_weight(weight_str: str) -> Tuple[bool, float, str]:
    """
    Validate parcel weight
    Returns: (is_valid, weight_value, error_message)
    """
    weight_str = weight_str.strip()
    
    if not weight_str:
        return False, 0.0, "⚠️ Вес не может быть пустым."
    
    try:
        weight = float(weight_str)
    except ValueError:
        return False, 0.0, "⚠️ Вес должен быть числом.\n\nНапример: 1, 2.5, 10"
    
    if weight <= 0:
        return False, 0.0, "⚠️ Вес должен быть больше 0."
    
    if weight > 150:
        return False, 0.0, "⚠️ Вес не может превышать 150 фунтов.\n\nДля более тяжелых грузов свяжитесь с нами."
    
    return True, weight, ""


def validate_dimension(dimension_str: str, dimension_name: str = "Размер") -> Tuple[bool, float, str]:
    """
    Validate parcel dimension (length, width, height)
    Returns: (is_valid, dimension_value, error_message)
    """
    dimension_str = dimension_str.strip()
    
    if not dimension_str:
        return False, 0.0, f"⚠️ {dimension_name} не может быть пустым."
    
    try:
        dimension = float(dimension_str)
    except ValueError:
        return False, 0.0, f"⚠️ {dimension_name} должен быть числом.\n\nНапример: 10, 12.5, 20"
    
    if dimension <= 0:
        return False, 0.0, f"⚠️ {dimension_name} должен быть больше 0."
    
    if dimension > 108:
        return False, 0.0, f"⚠️ {dimension_name} не может превышать 108 дюймов.\n\nДля негабаритных грузов свяжитесь с нами."
    
    return True, dimension, ""
