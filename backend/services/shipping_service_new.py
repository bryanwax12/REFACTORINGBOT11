"""
Shipping Service Module
Handles all shipping-related operations including rate calculations and label creation
"""
import logging
from typing import Optional, Dict, List, Any, Tuple
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# ============================================================
# DISPLAY SHIPPING RATES
# ============================================================

async def display_shipping_rates(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    rates: list,
    find_user_by_telegram_id_func,
    safe_telegram_call_func,
    STATE_NAMES: dict,
    SELECT_CARRIER: int
) -> int:
    """
    Display shipping rates to user (reusable for both cached and fresh rates)
    
    Args:
        update: Telegram update
        context: Telegram context
        rates: List of rate dictionaries
        find_user_by_telegram_id_func: Function to find user
        safe_telegram_call_func: Function for safe telegram calls
        STATE_NAMES: State names mapping
        SELECT_CARRIER: Select carrier state constant
    
    Returns:
        int: SELECT_CARRIER state
    """
    from utils.ui_utils import ShippingRatesUI
    
    query = update.callback_query
    
    # Get user balance
    telegram_id = query.from_user.id
    user = await find_user_by_telegram_id_func(telegram_id)
    user_balance = user.get('balance', 0.0) if user else 0.0
    
    # Format message and keyboard using UI utils
    message = ShippingRatesUI.format_rates_message(rates, user_balance)
    reply_markup = ShippingRatesUI.build_rates_keyboard(rates)
    
    # Save state
    context.user_data['last_state'] = STATE_NAMES[SELECT_CARRIER]
    
    # Send message
    bot_msg = await safe_telegram_call_func(
        query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
    )
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
    
    return SELECT_CARRIER


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def validate_shipping_address(address_data: Dict[str, Any], prefix: str) -> Tuple[bool, Optional[str]]:
    """
    Validate shipping address data
    
    Args:
        address_data: Context user_data dict
        prefix: 'from' or 'to'
    
    Returns:
        (is_valid, error_message or None)
    """
    required_fields = ['name', 'street', 'city', 'state', 'zip']
    
    for field in required_fields:
        key = f'{prefix}_{field}'
        if not address_data.get(key):
            return False, f"Missing required field: {key}"
    
    return True, None


def validate_parcel_data(parcel_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate parcel data
    
    Args:
        parcel_data: Context user_data dict with parcel info
    
    Returns:
        (is_valid, error_message or None)
    """
    if not parcel_data.get('weight'):
        return False, "Missing parcel weight"
    
    try:
        weight = float(parcel_data['weight'])
        if weight <= 0:
            return False, "Parcel weight must be positive"
        if weight > 150:  # 150 lbs limit
            return False, "Parcel weight exceeds maximum (150 lbs)"
    except (ValueError, TypeError):
        return False, "Invalid parcel weight format"
    
    return True, None


async def format_order_for_shipstation(
    order_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format order data for ShipStation API
    
    Args:
        order_data: Raw order data from context
    
    Returns:
        Formatted order data for ShipStation
    """
    return {
        'carrierCode': order_data.get('carrier_code'),
        'serviceCode': order_data.get('service_code'),
        'packageCode': 'package',
        'confirmation': 'none',
        'shipDate': order_data.get('ship_date'),
        'weight': {
            'value': float(order_data.get('weight', 0)),
            'units': 'pounds'
        },
        'dimensions': {
            'length': float(order_data.get('length', 10)),
            'width': float(order_data.get('width', 10)),
            'height': float(order_data.get('height', 10)),
            'units': 'inches'
        },
        'shipFrom': {
            'name': order_data.get('from_name'),
            'street1': order_data.get('from_street'),
            'street2': order_data.get('from_street2', ''),
            'city': order_data.get('from_city'),
            'state': order_data.get('from_state'),
            'postalCode': order_data.get('from_zip'),
            'country': 'US',
            'phone': order_data.get('from_phone', '')
        },
        'shipTo': {
            'name': order_data.get('to_name'),
            'street1': order_data.get('to_street'),
            'street2': order_data.get('to_street2', ''),
            'city': order_data.get('to_city'),
            'state': order_data.get('to_state'),
            'postalCode': order_data.get('to_zip'),
            'country': 'US',
            'phone': order_data.get('to_phone', '')
        }
    }


# ============================================================
# MODULE DOCUMENTATION
# ============================================================

"""
SHIPPING SERVICE ARCHITECTURE:

This module centralizes all shipping-related operations:
1. Rate calculation and display
2. Label creation and delivery
3. ShipStation API integration
4. Order validation
5. Address formatting

BENEFITS:
- Single responsibility: All shipping logic in one place
- Testability: Easy to unit test
- Reusability: Functions can be used across handlers
- Maintainability: Changes to shipping logic isolated here
"""
