"""
Shipping Service Module
Handles all shipping-related operations including rate calculations and label creation
"""
import logging
import httpx
from typing import Optional, Dict, List, Any, Tuple
from telegram import Update
from telegram.ext import ContextTypes
import telegram.error
from utils.retry_utils import retry_on_api_error

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
    
    # Get user balance
    telegram_id = update.effective_user.id if update.effective_user else None
    if not telegram_id:
        raise ValueError("Cannot get user ID from update")
    user = await find_user_by_telegram_id_func(telegram_id)
    user_balance = user.get('balance', 0.0) if user else 0.0
    
    # Format message and keyboard using UI utils (CPU-intensive operations)
    # ✅ Run in thread to avoid blocking event loop
    import asyncio
    message, reply_markup = await asyncio.gather(
        asyncio.to_thread(ShippingRatesUI.format_rates_message, rates, user_balance),
        asyncio.to_thread(ShippingRatesUI.build_rates_keyboard, rates)
    )
    
    # Save state
    
    # Send message (use effective_message to support both callbacks and regular messages)
    message_obj = update.effective_message
    bot_msg = await safe_telegram_call_func(
        message_obj.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
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
        weight = float(parcel_data.get('weight') or parcel_data.get('parcel_weight', 0))
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

## Core Functions:
1. Rate Calculation & Display:
   - display_shipping_rates() - Show rates to user
   - validate_order_data_for_rates() - Validate before API call
   - build_shipstation_rates_request() - Build API request
   - fetch_rates_from_shipstation() - Make API call
   - filter_and_sort_rates() - Process API response
   - save_rates_to_cache_and_session() - Cache results

2. Label Creation & Delivery:
   - build_shipstation_label_request() - Build label request
   - download_label_pdf() - Download PDF from URL
   - send_label_to_user() - Send via Telegram

3. Validation:
   - validate_shipping_address() - Address validation
   - validate_parcel_data() - Parcel info validation

4. Utilities:
   - format_order_for_shipstation() - Format order data

## Design Pattern:
All functions use dependency injection - they receive external dependencies
(db, functions) as parameters, making them easy to test and reuse.

## Benefits:
- Single responsibility: All shipping logic in one place
- Testability: Easy to unit test with mocks
- Reusability: Functions can be used across handlers
- Maintainability: Changes to shipping logic isolated here
- Modularity: Large functions broken into smaller pieces
- Cache-friendly: Rate caching built-in
"""




# ============================================================
# FETCH SHIPPING RATES - HELPER FUNCTIONS
# ============================================================

async def validate_order_data_for_rates(order_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate order data before fetching rates
    
    Args:
        order_data: Context user_data with order info
    
    Returns:
        (is_valid, missing_fields_list)
    """
    # Support both 'from_street' and 'from_address' naming conventions
    required_fields = [
        'from_name', 'from_city', 'from_state', 'from_zip',
        'to_name', 'to_city', 'to_state', 'to_zip',
        'parcel_weight'
    ]
    
    # Check for from_street OR from_address
    if not (order_data.get('from_street') or order_data.get('from_address')):
        required_fields.append('from_street')
    
    # Check for to_street OR to_address
    if not (order_data.get('to_street') or order_data.get('to_address')):
        required_fields.append('to_street')
    
    missing_fields = [
        field for field in required_fields
        if not order_data.get(field) or order_data.get(field) == 'None' or order_data.get(field) == ''
    ]
    
    return (len(missing_fields) == 0, missing_fields)


def build_shipstation_rates_request(order_data: Dict[str, Any], carrier_ids: List[str]) -> Dict[str, Any]:
    """
    Build ShipStation V2 rate request payload
    
    Args:
        order_data: Context user_data with order info
        carrier_ids: List of carrier IDs to request rates from
    
    Returns:
        ShipStation API request dictionary
    """
    return {
        'rate_options': {
            'carrier_ids': carrier_ids
        },
        'shipment': {
            'ship_to': {
                'name': order_data['to_name'],
                'phone': order_data.get('to_phone') or '+15551234567',
                'address_line1': order_data.get('to_street') or order_data.get('to_address', ''),
                'address_line2': order_data.get('to_street2', ''),
                'city_locality': order_data['to_city'],
                'state_province': order_data['to_state'],
                'postal_code': order_data['to_zip'],
                'country_code': 'US',
                'address_residential_indicator': 'unknown'
            },
            'ship_from': {
                'name': order_data['from_name'],
                'phone': order_data.get('from_phone') or '+15551234567',
                'address_line1': order_data.get('from_street') or order_data.get('from_address', ''),
                'address_line2': order_data.get('from_street2', ''),
                'city_locality': order_data['from_city'],
                'state_province': order_data['from_state'],
                'postal_code': order_data['from_zip'],
                'country_code': 'US'
            },
            'packages': [{
                'weight': {
                    'value': float(order_data.get('weight') or order_data.get('parcel_weight', 1.0)),
                    'unit': 'pound'
                },
                'dimensions': {
                    'length': float(order_data.get('parcel_length') or order_data.get('length', 10)),
                    'width': float(order_data.get('parcel_width') or order_data.get('width', 10)),
                    'height': float(order_data.get('parcel_height') or order_data.get('height', 10)),
                    'unit': 'inch'
                }
            }]
        }
    }


def get_allowed_services_config() -> Dict[str, List[str]]:
    """
    Get configuration for allowed shipping services per carrier
    
    Returns:
        Dictionary mapping carrier codes to allowed service codes
    """
    return {
        'ups': [
            'ups_ground',
            'ups_3_day_select',
            'ups_2nd_day_air',
            'ups_next_day_air',
            'ups_next_day_air_saver'
        ],
        'fedex_walleted': [
            'fedex_ground',
            'fedex_economy',  # FedEx Express Saver - 3-day
            'fedex_2day',
            'fedex_standard_overnight',
            'fedex_priority_overnight'
        ],
        'usps': [
            'usps_ground_advantage',
            'usps_priority_mail',
            'usps_priority_mail_express'
        ],
        'stamps_com': [
            'usps_ground_advantage',
            'usps_priority_mail',
            'usps_priority_mail_express',
            'usps_first_class_mail',
            'usps_media_mail'
        ]
    }


def apply_service_filter(
    rates: List[Dict],
    allowed_services: Optional[Dict[str, List[str]]] = None
) -> List[Dict]:
    """
    Filter rates to only allowed services per carrier
    
    Args:
        rates: List of rate dictionaries from ShipStation
        allowed_services: Optional dict of allowed services per carrier
                         If None, uses default configuration
    
    Returns:
        Filtered rates list
    """
    if allowed_services is None:
        allowed_services = get_allowed_services_config()
    
    filtered_rates = []
    
    for rate in rates:
        carrier_code = rate.get('carrier_code', '').lower()
        service_code = rate.get('service_code', '').lower()
        
        if carrier_code in allowed_services:
            if service_code in allowed_services[carrier_code]:
                filtered_rates.append(rate)
        else:
            # Keep rates from unlisted carriers
            filtered_rates.append(rate)
    
    return filtered_rates


def balance_and_deduplicate_rates(
    rates: List[Dict],
    max_per_carrier: int = 5
) -> List[Dict[str, Any]]:
    """
    Balance rates across carriers and deduplicate by service type
    
    Takes top N rates from each carrier, deduplicates by service,
    and formats for display.
    
    Args:
        rates: Raw rates from ShipStation
        max_per_carrier: Maximum rates to show per carrier
    
    Returns:
        Balanced and formatted rates list
    """
    # Group rates by carrier
    rates_by_carrier = {}
    for rate in rates:
        carrier = rate.get('carrier_friendly_name', 'Unknown')
        if carrier not in rates_by_carrier:
            rates_by_carrier[carrier] = []
        rates_by_carrier[carrier].append(rate)
    
    # Process each carrier's rates
    balanced_rates = []
    
    for carrier, carrier_rates in rates_by_carrier.items():
        # Sort by price (ascending)
        sorted_rates = sorted(
            carrier_rates,
            key=lambda r: float(r.get('shipping_amount', {}).get('amount', 0))
        )
        
        # Deduplicate by service_type - keep only cheapest for each service
        seen_services = {}
        deduplicated_rates = []
        
        for rate in sorted_rates:
            service_type = rate.get('service_type', 'Unknown')
            if service_type not in seen_services:
                seen_services[service_type] = True
                deduplicated_rates.append(rate)
        
        # Take top N rates per carrier
        top_rates = deduplicated_rates[:max_per_carrier]
        
        # Format rates
        for rate in top_rates:
            # Use original carrier name from API as is
            original_carrier = rate.get('carrier_friendly_name', 'Unknown')
            
            formatted_rate = {
                'carrier': original_carrier,  # Use original carrier name as is
                'carrier_friendly_name': original_carrier,  # Keep same value
                'carrier_code': rate.get('carrier_code'),
                'service': rate.get('service_type', 'Standard'),
                'service_code': rate.get('service_code'),
                'amount': float(rate.get('shipping_amount', {}).get('amount', 0)),
                'days': rate.get('delivery_days'),
                'carrier_delivery_days': rate.get('carrier_delivery_days'),
                'guaranteed_service': rate.get('guaranteed_service', False),
                'rate_id': rate.get('rate_id')
            }
            balanced_rates.append(formatted_rate)
    
    # Final sort by price across all carriers
    balanced_rates.sort(key=lambda x: x['amount'])
    
    return balanced_rates


@retry_on_api_error(max_attempts=2, min_wait=1, max_wait=5)
async def fetch_rates_from_shipstation(
    rate_request: Dict[str, Any],
    headers: Dict[str, str],
    api_url: str,
    timeout: int = 30
) -> Tuple[bool, Optional[List[Dict]], Optional[str]]:
    """
    Make API call to ShipStation to fetch rates
    
    Args:
        rate_request: Rate request payload
        headers: API headers with auth
        api_url: ShipStation API URL
        timeout: Request timeout in seconds
    
    Returns:
        (success, rates_list, error_message)
    """
    try:
        # Create timeout config (connect, read, write, pool)
        timeout_config = httpx.Timeout(timeout, connect=10.0)
        
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(
                api_url,
                json=rate_request,
                headers=headers
            )
        
        if response.status_code == 200:
            data = response.json()
            
            # Log full response for debugging
            logger.info(f"📦 ShipStation rates response: {data}")
            
            rates = data.get('rate_response', {}).get('rates', [])
            
            if not rates:
                # Check if there are any errors in the response
                errors = data.get('rate_response', {}).get('errors', [])
                if errors:
                    error_details = "; ".join([f"{e.get('message', 'Unknown error')}" for e in errors])
                    logger.error(f"ShipStation returned errors: {error_details}")
                    return False, None, f"ShipStation errors: {error_details}"
                
                logger.warning(f"No rates in response. Full response: {data}")
                return False, None, "No rates returned from ShipStation"
            
            return True, rates, None
            
        else:
            # Parse error response
            try:
                error_data = response.json()
                errors = error_data.get('errors', [])
                
                if errors:
                    # Extract user-friendly error messages
                    error_messages = []
                    for error in errors:
                        msg = error.get('message', 'Unknown error')
                        field = error.get('field_name', '')
                        if field:
                            error_messages.append(f"{field}: {msg}")
                        else:
                            error_messages.append(msg)
                    
                    error_msg = "; ".join(error_messages)
                    logger.error(f"ShipStation API validation errors: {error_msg}")
                    return False, None, error_msg
                else:
                    error_msg = f"ShipStation API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return False, None, error_msg
            except:
                error_msg = f"ShipStation API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return False, None, error_msg
            
    except httpx.TimeoutException as e:
        logger.error(f"ShipStation rates timeout: {e}", exc_info=True)
        return False, None, "Request timeout - ShipStation API took too long to respond"
    except httpx.HTTPStatusError as e:
        logger.error(f"ShipStation rates HTTP error {e.response.status_code}: {e}", exc_info=True)
        return False, None, f"ShipStation API error: {e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"ShipStation rates request error: {e}", exc_info=True)
        return False, None, f"Network error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error fetching rates: {e}", exc_info=True)
        return False, None, f"Unexpected error: {str(e)}"


def filter_and_sort_rates(
    rates: List[Dict],
    excluded_carriers: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Filter, format and sort shipping rates
    
    Args:
        rates: Raw rates from ShipStation
        excluded_carriers: List of carrier codes to exclude
    
    Returns:
        Formatted and sorted rates list
    """
    if excluded_carriers is None:
        excluded_carriers = []
    
    formatted_rates = []
    
    for rate in rates:
        # Skip excluded carriers
        carrier_code = rate.get('carrier_code', '').lower()
        if carrier_code in excluded_carriers:
            continue
        
        # Extract rate info
        formatted_rate = {
            'carrier': rate.get('carrier_friendly_name', rate.get('carrier_code', 'Unknown')),
            'carrier_code': rate.get('carrier_code'),
            'service': rate.get('service_type', 'Standard'),
            'service_code': rate.get('service_code'),
            'amount': float(rate.get('shipping_amount', {}).get('amount', 0)),
            'days': rate.get('delivery_days'),
            'carrier_delivery_days': rate.get('carrier_delivery_days'),
            'guaranteed_service': rate.get('guaranteed_service', False),
            'rate_id': rate.get('rate_id')
        }
        
        formatted_rates.append(formatted_rate)
    
    # Sort by price (lowest first)
    formatted_rates.sort(key=lambda x: x['amount'])
    
    return formatted_rates


async def save_rates_to_cache_and_session(
    rates: List[Dict],
    order_data: Dict[str, Any],
    user_id: int,
    context,
    shipstation_cache,
    session_manager
) -> None:
    """
    Save rates to cache and session
    
    Args:
        rates: Formatted rates list
        order_data: Order data for cache key
        user_id: Telegram user ID
        context: Telegram context
        shipstation_cache: Cache instance
        session_manager: Session manager instance
    """
    from datetime import datetime, timezone
    
    # Save to cache
    shipstation_cache.set(
        from_zip=order_data['from_zip'],
        to_zip=order_data['to_zip'],
        weight=order_data.get('weight') or order_data.get('parcel_weight', 1.0),
        length=order_data.get('parcel_length') or order_data.get('length', 10),
        width=order_data.get('parcel_width') or order_data.get('width', 10),
        height=order_data.get('parcel_height') or order_data.get('height', 10),
        rates=rates
    )
    
    # Save to session
    await session_manager.update_session_atomic(user_id, data={
        'rates': rates,
        'cached': False,
        'fetch_timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    # Store in context
    context.user_data['rates'] = rates


# ============================================================
# CREATE AND SEND LABEL - HELPER FUNCTIONS
# ============================================================

def build_shipstation_label_request(
    order: Dict[str, Any],
    selected_rate: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build ShipStation label creation request
    
    Args:
        order: Order data from database
        selected_rate: Selected shipping rate
    
    Returns:
        ShipStation API request dictionary
    """
    
    return {
        'shipment': {
            'service_code': selected_rate.get('service_code'),
            'carrier_id': selected_rate.get('carrier_id'),
            'ship_to': {
                'name': order.get('to_name'),
                'phone': order.get('to_phone', '+15551234567'),
                'address_line1': order.get('to_street'),
                'address_line2': order.get('to_street2', ''),
                'city_locality': order.get('to_city'),
                'state_province': order.get('to_state'),
                'postal_code': order.get('to_zip'),
                'country_code': 'US'
            },
            'ship_from': {
                'name': order.get('from_name'),
                'phone': order.get('from_phone', '+15551234567'),
                'address_line1': order.get('from_street'),
                'address_line2': order.get('from_street2', ''),
                'city_locality': order.get('from_city'),
                'state_province': order.get('from_state'),
                'postal_code': order.get('from_zip'),
                'country_code': 'US'
            },
            'packages': [{
                'weight': {
                    'value': float(order.get('weight', 1)),
                    'unit': 'pound'
                },
                'dimensions': {
                    'length': float(order.get('length', 10)),
                    'width': float(order.get('width', 10)),
                    'height': float(order.get('height', 10)),
                    'unit': 'inch'
                }
            }]
        },
        'label_format': 'pdf',
        'label_download_type': 'url'
    }


async def download_label_pdf(label_url: str, timeout: int = 30) -> Tuple[bool, Optional[bytes], Optional[str]]:
    """
    Download label PDF from URL
    
    Args:
        label_url: URL to download PDF from
        timeout: Request timeout
    
    Returns:
        (success, pdf_bytes, error_message)
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(label_url)
        
        if response.status_code == 200:
            return True, response.content, None
        else:
            return False, None, f"Failed to download label: HTTP {response.status_code}"
            
    except httpx.TimeoutException:
        return False, None, "Timeout downloading label"
    except httpx.RequestError as e:
        return False, None, f"Network error: {str(e)}"
    except Exception as e:
        return False, None, f"Error downloading label: {str(e)}"


async def send_label_to_user(
    bot_instance,
    telegram_id: int,
    pdf_bytes: bytes,
    order_id: str,
    tracking_number: str,
    carrier: str,
    safe_telegram_call_func
) -> Tuple[bool, Optional[str]]:
    """
    Send label PDF to user via Telegram
    
    Args:
        bot_instance: Telegram bot instance
        telegram_id: User's telegram ID
        pdf_bytes: PDF file content
        order_id: Order ID
        tracking_number: Tracking number
        carrier: Carrier name
        safe_telegram_call_func: Safe telegram call wrapper
    
    Returns:
        (success, error_message)
    """
    import io
    
    try:
        # Create file-like object
        pdf_file = io.BytesIO(pdf_bytes)
        # Use only tracking number as filename
        pdf_file.name = f"{tracking_number}.pdf"
        
        # Caption message
        caption = f"""✅ Shipping Label

Carrier: {carrier}
Tracking: {tracking_number}"""
        
        # Send document
        await safe_telegram_call_func(
            bot_instance.send_document(
                chat_id=telegram_id,
                document=pdf_file,
                caption=caption
            )
        )
        
        return True, None
        
    except Exception as e:
        return False, f"Error sending label: {str(e)}"
