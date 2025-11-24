"""
Order Utilities
Handles order ID generation and order-related operations
"""
import uuid
from datetime import datetime, timezone
from typing import Optional


def generate_order_id(telegram_id: Optional[int] = None, prefix: str = "ORD") -> str:
    """
    Generate unique order ID
    
    Format: {prefix}-{timestamp}-{uuid_short}
    Example: ORD-20251114-a3f8d2b4
    
    Args:
        telegram_id: Optional telegram user ID
        prefix: Order ID prefix (default: "ORD")
    
    Returns:
        Unique order ID string
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    uuid_short = str(uuid.uuid4())[:8]  # First 8 chars of UUID
    
    return f"{prefix}-{timestamp}-{uuid_short}"


def generate_pure_uuid_order_id() -> str:
    """
    Generate pure UUID-based order ID
    
    Returns:
        UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
    """
    return str(uuid.uuid4())


def format_order_id_for_display(order_id: str) -> str:
    """
    Format order ID for user-friendly display
    
    Args:
        order_id: Full order ID
    
    Returns:
        Shortened display version
    """
    if not order_id:
        return "N/A"
    
    # If UUID format, show first 8 chars
    if len(order_id) == 36 and order_id.count('-') == 4:
        return order_id[:8].upper()
    
    # If ORD-timestamp-uuid format, show prefix and last part
    parts = order_id.split('-')
    if len(parts) >= 3:
        return f"{parts[0]}-{parts[-1][:6].upper()}"
    
    return order_id[:12].upper()


def validate_order_id(order_id: str) -> bool:
    """
    Validate order ID format
    
    Args:
        order_id: Order ID to validate
    
    Returns:
        True if valid format
    """
    if not order_id or not isinstance(order_id, str):
        return False
    
    # Check if it's a UUID
    try:
        uuid.UUID(order_id)
        return True
    except ValueError:
        pass
    
    # Check if it's ORD-{timestamp}-{uuid} format
    parts = order_id.split('-')
    if len(parts) >= 3 and parts[0] == "ORD":
        return True
    
    return False
