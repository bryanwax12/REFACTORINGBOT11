"""
Maintenance Mode Check Utility
Separate module to avoid circular imports
"""
import logging
from telegram import Update

logger = logging.getLogger(__name__)


async def check_maintenance_mode(update: Update) -> bool:
    """
    Check if bot is in maintenance mode and user is not admin
    
    Returns:
        True if in maintenance mode and user is not admin (should block)
        False otherwise (allow access)
    """
    try:
        from server import db, ADMIN_TELEGRAM_ID
        settings = await db.settings.find_one({"key": "maintenance_mode"})
        is_maintenance = settings.get("value", False) if settings else False
        
        # Allow admin to use bot even in maintenance mode
        if is_maintenance and str(update.effective_user.id) != ADMIN_TELEGRAM_ID:
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking maintenance mode: {e}")
        return False
