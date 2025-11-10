"""Payment database operations"""
import logging
from typing import Optional
from .connection import get_db

logger = logging.getLogger(__name__)
db = get_db()

async def get_payment(invoice_id: str) -> Optional[dict]:
    """Get payment by invoice_id"""
    return await db.payments.find_one({"invoice_id": invoice_id}, {"_id": 0})

async def create_payment(payment_data: dict) -> bool:
    """Create new payment"""
    try:
        await db.payments.insert_one(payment_data)
        logger.info(f"Created payment: {payment_data['invoice_id']}")
        return True
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return False

async def update_payment_status(invoice_id: str, status: str) -> bool:
    """Update payment status"""
    try:
        result = await db.payments.update_one(
            {"invoice_id": invoice_id},
            {"$set": {"status": status}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating payment status: {e}")
        return False
