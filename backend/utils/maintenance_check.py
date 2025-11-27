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
        
        # Check bot_settings collection (used by maintenance router)
        settings = await db.bot_settings.find_one({"key": "maintenance_mode"})
        is_maintenance = settings.get("enabled", False) if settings else False
        
        user_id = str(update.effective_user.id) if update.effective_user else None
        admin_id = str(ADMIN_TELEGRAM_ID) if ADMIN_TELEGRAM_ID else None
        
        logger.debug(f"🔍 Maintenance check: enabled={is_maintenance}, user={user_id}, admin={admin_id}")
        
        # Allow admin to use bot even in maintenance mode
        if is_maintenance and user_id != admin_id:
            logger.info(f"🚫 User {user_id} blocked by maintenance mode")
            return True
        
        return False
    except Exception as e:
        logger.error(f"❌ Error checking maintenance mode: {e}", exc_info=True)
        return False
