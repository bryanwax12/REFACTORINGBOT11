"""
Admin Users Router
Handles user management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from handlers.admin_handlers import verify_admin_key
import logging
import pymongo.errors
import telegram.error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["admin-users"])


# Request models
class BalanceUpdate(BaseModel):
    amount: float
    operation: str = "add"  # add or set


class DiscountUpdate(BaseModel):
    discount: float


@router.get("")
async def get_users(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    blocked_only: bool = False,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get all users with pagination
    
    Query Parameters:
    - limit: Maximum users to return (1-1000)
    - skip: Number of users to skip
    - blocked_only: Filter blocked users only
    """
    from server import db
    from services.admin.user_admin_service import user_admin_service
    
    try:
        users = await user_admin_service.get_all_users(
            db,
            limit=limit,
            skip=skip,
            blocked_only=blocked_only
        )
        
        return {
            "users": users,
            "count": len(users),
            "limit": limit,
            "skip": skip
        }
    
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error getting users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Unexpected error getting users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{telegram_id}")
async def get_user(
    telegram_id: int,
    authenticated: bool = Depends(lambda: True)
):
    """
    Get specific user with statistics
    """
    from server import db
    from services.admin.user_admin_service import user_admin_service
    
    try:
        stats = await user_admin_service.get_user_stats(db, telegram_id)
        
        if "error" in stats:
            raise HTTPException(status_code=404, detail=stats["error"])
        
        return stats
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error getting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except telegram.error.TelegramError as e:
        logger.error(f"Telegram error getting user: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Notification service error")
    except Exception as e:
        logger.error(f"Unexpected error getting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/block")
async def block_user(
    request: Request,
    telegram_id: int,
    send_notification: bool = True,
    authenticated: bool = Depends(lambda: True)
):
    """
    Block a user from using the bot
    
    Query Parameters:
    - send_notification: Whether to notify user via Telegram
    """
    from server import db, bot_instance
    from services.admin.user_admin_service import user_admin_service
    
    logger.info(f"🚫 [ADMIN_USERS BLOCK] telegram_id={telegram_id}, bot_instance={bot_instance is not None}")
    
    try:
        # Check if user exists
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Block user
        success, message = await user_admin_service.block_user(
            db,
            telegram_id,
            bot_instance,
            send_notification=send_notification
        )
        
        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "message": message}
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error blocking user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except telegram.error.TelegramError as e:
        logger.error(f"Telegram error blocking user: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Notification service error")
    except Exception as e:
        logger.error(f"Unexpected error blocking user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/unblock")
async def unblock_user(
    request: Request,
    telegram_id: int,
    send_notification: bool = True,
    authenticated: bool = Depends(lambda: True)
):
    """
    Unblock a user to allow bot usage
    
    Query Parameters:
    - send_notification: Whether to notify user via Telegram
    """
    from server import db, bot_instance
    from services.admin.user_admin_service import user_admin_service
    
    logger.info(f"✅ [ADMIN_USERS UNBLOCK] telegram_id={telegram_id}, bot_instance={bot_instance is not None}")
    
    try:
        # Check if user exists
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Unblock user
        success, message = await user_admin_service.unblock_user(
            db,
            telegram_id,
            bot_instance,
            send_notification=send_notification
        )
        
        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "message": message}
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error unblocking user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except telegram.error.TelegramError as e:
        logger.error(f"Telegram error unblocking user: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Notification service error")
    except Exception as e:
        logger.error(f"Unexpected error unblocking user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{telegram_id}/balance")
async def update_balance(
    telegram_id: int,
    update: BalanceUpdate,
    authenticated: bool = Depends(lambda: True)
):
    """
    Update user balance
    
    Request Body:
    - amount: Amount to add or set
    - operation: "add" to add amount, "set" to set absolute value
    """
    from server import db
    from services.admin.user_admin_service import user_admin_service
    
    try:
        success, new_balance, error = await user_admin_service.update_user_balance(
            db,
            telegram_id,
            update.amount,
            update.operation
        )
        
        if success:
            return {
                "success": True,
                "new_balance": new_balance,
                "operation": update.operation,
                "amount": update.amount
            }
        else:
            raise HTTPException(status_code=400, detail=error)
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error updating balance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except telegram.error.TelegramError as e:
        logger.error(f"Telegram error updating balance: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Notification service error")
    except Exception as e:
        logger.error(f"Unexpected error updating balance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{telegram_id}/discount")
async def update_discount(
    telegram_id: int,
    update: DiscountUpdate,
    authenticated: bool = Depends(lambda: True)
):
    """
    Update user discount percentage
    
    Request Body:
    - discount: Discount percentage (0-100)
    """
    from server import db
    from services.admin.user_admin_service import user_admin_service
    
    try:
        success, message = await user_admin_service.update_user_discount(
            db,
            telegram_id,
            update.discount
        )
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except pymongo.errors.PyMongoError as e:
        logger.error(f"Database error updating discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
    except telegram.error.TelegramError as e:
        logger.error(f"Telegram error updating discount: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Notification service error")
    except Exception as e:
        logger.error(f"Unexpected error updating discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
