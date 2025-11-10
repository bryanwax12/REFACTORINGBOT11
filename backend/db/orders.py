"""Order database operations"""
import logging
from typing import Optional
from .connection import get_db

logger = logging.getLogger(__name__)
db = get_db()

async def get_order(order_id: str) -> Optional[dict]:
    """Get order by order_id"""
    return await db.orders.find_one({"id": order_id}, {"_id": 0})

async def create_order(order_data: dict) -> bool:
    """Create new order"""
    try:
        await db.orders.insert_one(order_data)
        logger.info(f"Created order: {order_data['id']}")
        return True
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return False

async def update_order_status(order_id: str, status: str) -> bool:
    """Update order status"""
    try:
        result = await db.orders.update_one(
            {"id": order_id},
            {"$set": {"payment_status": status}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        return False
