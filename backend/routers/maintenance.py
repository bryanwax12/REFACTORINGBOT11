"""
Maintenance Router
Эндпоинты для управления режимом обслуживания
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from handlers.admin_handlers import verify_admin_key
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("/status")
async def get_maintenance_status():
    """Get current maintenance mode status"""
    from server import db
    
    try:
        settings = await db.bot_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
        
        if not settings:
            return {
                "enabled": False,
                "message": None
            }
        
        return {
            "enabled": settings.get("enabled", False),
            "message": settings.get("message")
        }
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable", dependencies=[Depends(verify_admin_key)])
async def enable_maintenance(message: str = Body(None, embed=True)):
    """Enable maintenance mode - ADMIN ONLY"""
    from server import db, bot_instance
    from utils.telegram_utils import safe_telegram_call
    
    try:
        maintenance_message = message or "Бот временно на техническом обслуживании. Попробуйте позже."
        
        logger.info(f"🔧 Enabling maintenance mode with message: {maintenance_message[:50]}...")
        
        result = await db.bot_settings.update_one(
            {"key": "maintenance_mode"},
            {
                "$set": {
                    "enabled": True,
                    "message": maintenance_message
                }
            },
            upsert=True
        )
        
        logger.info(f"🔧 Maintenance mode ENABLED (matched: {result.matched_count}, modified: {result.modified_count}, upserted: {result.upserted_id})")
        
        # Verify it was saved
        verify = await db.bot_settings.find_one({"key": "maintenance_mode"}, {"_id": 0})
        logger.info(f"✅ Verified maintenance settings: {verify}")
        
        # Broadcast notification to all users
        logger.info(f"📋 bot_instance available: {bot_instance is not None}")
        if bot_instance:
            try:
                logger.info("📢 Broadcasting maintenance notification to all users...")
                logger.info("📊 Fetching users from database...")
                users = await db.users.find(
                    {"bot_blocked_by_user": {"$ne": True}},
                    {"_id": 0, "telegram_id": 1}
                ).to_list(10000)
                
                logger.info(f"👥 Found {len(users)} users to notify")
                notification_text = f"🔧 *Режим обслуживания*\n\n{maintenance_message}"
                logger.info(f"📝 Notification text: {notification_text[:100]}...")
                
                success_count = 0
                failed_count = 0
                
                for user in users:
                    try:
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=user['telegram_id'],
                            text=notification_text,
                            parse_mode='Markdown'
                        ))
                        success_count += 1
                    except Exception as send_error:
                        failed_count += 1
                        logger.warning(f"Failed to notify user {user['telegram_id']}: {send_error}")
                
                logger.info(f"✅ Maintenance notification sent: {success_count} success, {failed_count} failed")
            except Exception as broadcast_error:
                logger.error(f"❌ Error broadcasting maintenance notification: {broadcast_error}", exc_info=True)
        else:
            logger.warning("⚠️ bot_instance is None, cannot send notifications!")
        
        return {
            "status": "enabled",
            "message": maintenance_message
        }
    except Exception as e:
        logger.error(f"Error enabling maintenance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable", dependencies=[Depends(verify_admin_key)])
async def disable_maintenance():
    """Disable maintenance mode - ADMIN ONLY"""
    from server import db, bot_instance
    from utils.telegram_utils import safe_telegram_call
    
    try:
        await db.bot_settings.update_one(
            {"key": "maintenance_mode"},
            {
                "$set": {
                    "enabled": False,
                    "message": None
                }
            },
            upsert=True
        )
        
        logger.info("✅ Maintenance mode DISABLED")
        
        # Broadcast notification to all users
        logger.info(f"📋 bot_instance available: {bot_instance is not None}")
        if bot_instance:
            try:
                logger.info("📢 Broadcasting maintenance disabled notification to all users...")
                logger.info("📊 Fetching users from database...")
                users = await db.users.find(
                    {"bot_blocked_by_user": {"$ne": True}},
                    {"_id": 0, "telegram_id": 1}
                ).to_list(10000)
                
                logger.info(f"👥 Found {len(users)} users to notify")
                notification_text = "✅ *Бот снова работает!*\n\nТехническое обслуживание завершено. Вы можете продолжить пользоваться ботом."
                logger.info(f"📝 Notification text: {notification_text[:100]}...")
                
                success_count = 0
                failed_count = 0
                
                for user in users:
                    try:
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=user['telegram_id'],
                            text=notification_text,
                            parse_mode='Markdown'
                        ))
                        success_count += 1
                    except Exception as send_error:
                        failed_count += 1
                        logger.warning(f"Failed to notify user {user['telegram_id']}: {send_error}")
                
                logger.info(f"✅ Maintenance disabled notification sent: {success_count} success, {failed_count} failed")
            except Exception as broadcast_error:
                logger.error(f"❌ Error broadcasting maintenance disabled notification: {broadcast_error}", exc_info=True)
        else:
            logger.warning("⚠️ bot_instance is None, cannot send notifications!")
        
        return {
            "status": "disabled",
            "message": "Maintenance mode disabled"
        }
    except Exception as e:
        logger.error(f"Error disabling maintenance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
