"""User database operations"""
import logging
from typing import Optional
from .connection import get_db

logger = logging.getLogger(__name__)
db = get_db()

async def get_user(telegram_id: int) -> Optional[dict]:
    """Get user by telegram_id"""
    return await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})

async def create_user(user_data: dict) -> bool:
    """Create new user"""
    try:
        await db.users.insert_one(user_data)
        logger.info(f"Created user: {user_data['telegram_id']}")
        return True
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False

async def update_user_balance(telegram_id: int, amount: float) -> bool:
    """Update user balance"""
    try:
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$inc": {"balance": amount}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating balance: {e}")
        return False
