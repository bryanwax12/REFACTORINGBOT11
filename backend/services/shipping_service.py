"""
Shipping Service
Handles shipping rate calculations and label creation via ShipStation API
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Note: These are wrapper functions that delegate to the main implementations in server.py
# Full refactoring of fetch_shipping_rates and create_and_send_label will be done in future iterations
# as they are complex functions with many dependencies (~600 and ~400 lines respectively)

async def calculate_shipping_rates(update, context):
    """
    Calculate shipping rates for an order
    
    Wrapper for fetch_shipping_rates in server.py
    This will be fully refactored in a future iteration
    
    Args:
        update: Telegram Update object
        context: Bot context
    
    Returns:
        Conversation state
    """
    # Import from server to avoid circular dependency
    from server import fetch_shipping_rates
    return await fetch_shipping_rates(update, context)


async def create_shipping_label(order_id: str, telegram_id: int, message: Optional[object] = None):
    """
    Create and send shipping label for a paid order
    
    Wrapper for create_and_send_label in server.py
    This will be fully refactored in a future iteration
    
    Args:
        order_id: Order ID
        telegram_id: Telegram user ID
        message: Optional Telegram message object
    
    Returns:
        bool: True if label created successfully
    """
    # Import from server to avoid circular dependency
    from server import create_and_send_label
    return await create_and_send_label(order_id, telegram_id, message)


# Future refactoring tasks:
# TODO: Extract rate calculation logic from fetch_shipping_rates into this module
# TODO: Extract label creation logic from create_and_send_label into this module
# TODO: Create separate functions for:
#   - ShipStation API calls
#   - Rate formatting and filtering
#   - Label generation and storage
#   - User notifications
