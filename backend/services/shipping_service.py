"""
Shipping Service Module
Handles shipping rate calculations and label creation via ShipStation API

This module has been refactored to use the new shipping_service_new.py
All new shipping logic should be added to shipping_service_new.py
"""
import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Import from new shipping service
from services.shipping_service_new import (
    display_shipping_rates as display_rates_new,
    validate_shipping_address,
    validate_parcel_data,
    format_order_for_shipstation
)


# ============================================================
# SHIPPING RATES CALCULATION
# ============================================================

async def calculate_shipping_rates(update, context):
    """
    Calculate shipping rates for an order
    
    This is a complex function that:
    1. Validates all order data (addresses, parcel info)
    2. Calls ShipStation API for rates
    3. Caches results for performance
    4. Formats and displays rates to user
    5. Handles errors and retries
    
    Current implementation: ~600 lines in server.py
    Future: Will be extracted to this module with subfunctions:
        - validate_order_data()
        - call_shipstation_rates_api()
        - format_rates_for_display()
        - save_rates_to_session()
    
    Args:
        update: Telegram Update object
        context: Bot context with order data
    
    Returns:
        Conversation state (SELECT_CARRIER or error state)
    """
    from server import fetch_shipping_rates
    return await fetch_shipping_rates(update, context)


# ============================================================
# LABEL CREATION AND DELIVERY
# ============================================================

async def create_shipping_label(order_id: str, telegram_id: int, message: Optional[object] = None):
    """
    Create and send shipping label for a paid order
    
    This is a complex function that:
    1. Retrieves order and rate data
    2. Creates label via ShipStation API
    3. Downloads PDF label
    4. Sends to user via Telegram
    5. Updates order status
    6. Handles errors and notifications
    
    Current implementation: ~400 lines in server.py
    Future: Will be extracted to this module with subfunctions:
        - retrieve_order_data()
        - create_shipstation_label()
        - download_label_pdf()
        - send_label_to_user()
        - update_order_status()
        - send_notifications()
    
    Args:
        order_id: Unique order identifier
        telegram_id: Telegram user ID
        message: Optional Telegram message object for replies
    
    Returns:
        bool: True if label created and sent successfully
    """
    from server import create_and_send_label
    return await create_and_send_label(order_id, telegram_id, message)


# ============================================================
# HELPER FUNCTIONS (Placeholders for future extraction)
# ============================================================

async def validate_order_data(order_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate order data before sending to ShipStation
    
    Future implementation will check:
    - Address completeness
    - Parcel dimensions validity
    - Required fields presence
    
    Returns:
        (is_valid, error_message)
    """
    # TODO: Extract validation logic from fetch_shipping_rates
    pass


async def format_rate_for_display(rate: Dict[str, Any]) -> str:
    """
    Format shipping rate for user-friendly display
    
    Future implementation will:
    - Format price
    - Add carrier info
    - Show delivery time
    - Add discount info if applicable
    
    Returns:
        Formatted rate string
    """
    # TODO: Extract formatting logic from fetch_shipping_rates
    pass


async def save_label_to_storage(label_data: bytes, order_id: str) -> str:
    """
    Save label PDF to persistent storage
    
    Future implementation will:
    - Save to filesystem or S3
    - Generate access URL
    - Track label storage
    
    Returns:
        Storage path or URL
    """
    # TODO: Extract storage logic from create_and_send_label
    pass


# ============================================================
# MODULE DOCUMENTATION
# ============================================================

"""
REFACTORING ROADMAP:

Phase 1 (CURRENT): Wrapper approach
- ✅ Module structure created
- ✅ Documentation added
- ✅ Wrapper functions implemented
- Main logic remains in server.py

Phase 2 (FUTURE): Extract validation and formatting
- Move validate_order_data() from server.py
- Move format_rate_for_display() from server.py
- Move error handling helpers

Phase 3 (FUTURE): Extract API calls
- Move ShipStation API calls
- Move rate caching logic
- Move label creation logic

Phase 4 (FUTURE): Complete extraction
- Move all shipping logic to this module
- Server.py only coordinates
- Full test coverage

BENEFITS OF PHASED APPROACH:
- Maintains stability during refactoring
- Allows testing between phases
- Reduces risk of breaking changes
- Enables gradual improvement
"""
