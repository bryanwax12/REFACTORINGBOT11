"""
Users Router
Эндпоинты для управления пользователями
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{telegram_id}/details")
async def get_user_details(telegram_id: int):
    """Get detailed user information"""
    from repositories import get_user_repo, get_order_repo
    from server import db
    
    try:
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user stats
        order_repo = get_order_repo()
        total_orders = await order_repo.count_by_telegram_id(telegram_id)
        
        # Get balance history
        balance_history = await db.balance_history.find(
            {"telegram_id": telegram_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(10).to_list(10)
        
        # Get recent orders
        recent_orders = await order_repo.find_by_telegram_id(telegram_id, limit=5)
        
        return {
            "user": user,
            "stats": {
                "total_orders": total_orders,
                "balance": user.get('balance', 0)
            },
            "balance_history": balance_history,
            "recent_orders": recent_orders
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/block")
async def block_user(telegram_id: int, reason: Optional[str] = None):
    """Block a user"""
    from repositories import get_user_repo
    
    try:
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        success = await user_repo.block_user(telegram_id, reason)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to block user")
        
        logger.info(f"🚫 User {telegram_id} blocked. Reason: {reason or 'No reason'}")
        
        return {
            "status": "blocked",
            "telegram_id": telegram_id,
            "reason": reason
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/unblock")
async def unblock_user(telegram_id: int):
    """Unblock a user"""
    from repositories import get_user_repo
    
    try:
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        success = await user_repo.unblock_user(telegram_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to unblock user")
        
        logger.info(f"✅ User {telegram_id} unblocked")
        
        return {
            "status": "unblocked",
            "telegram_id": telegram_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/balance/add")
async def add_user_balance(telegram_id: int, amount: float, description: str = "Manual add"):
    """Add balance to user account"""
    from repositories import get_user_repo
    
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        success = await user_repo.update_balance(telegram_id, amount, description)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add balance")
        
        new_balance = user.get('balance', 0) + amount
        
        logger.info(f"💰 Added ${amount} to user {telegram_id}. New balance: ${new_balance}")
        
        return {
            "status": "success",
            "telegram_id": telegram_id,
            "amount_added": amount,
            "new_balance": new_balance,
            "description": description
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/balance/deduct")
async def deduct_user_balance(telegram_id: int, amount: float, description: str = "Manual deduct"):
    """Deduct balance from user account"""
    from repositories import get_user_repo
    
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_balance = user.get('balance', 0)
        if current_balance < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Current: ${current_balance}, Required: ${amount}"
            )
        
        success = await user_repo.update_balance(telegram_id, -amount, description)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to deduct balance")
        
        new_balance = current_balance - amount
        
        logger.info(f"💸 Deducted ${amount} from user {telegram_id}. New balance: ${new_balance}")
        
        return {
            "status": "success",
            "telegram_id": telegram_id,
            "amount_deducted": amount,
            "new_balance": new_balance,
            "description": description
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deducting balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/discount")
async def set_user_discount(telegram_id: int, discount: float):
    """Set discount percentage for user"""
    from repositories import get_user_repo
    
    try:
        if discount < 0 or discount > 100:
            raise HTTPException(status_code=400, detail="Discount must be between 0 and 100")
        
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        await user_repo.update(
            telegram_id,
            {"discount": discount}
        )
        
        logger.info(f"🎁 Set {discount}% discount for user {telegram_id}")
        
        return {
            "status": "success",
            "telegram_id": telegram_id,
            "discount": discount
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting discount: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard")
async def get_users_leaderboard(limit: int = 10):
    """Get users leaderboard by orders count"""
    from repositories import get_user_repo, get_order_repo
    
    try:
        user_repo = get_user_repo()
        users = await user_repo.find_all(limit=1000)
        
        # Calculate orders for each user
        order_repo = get_order_repo()
        leaderboard = []
        
        for user in users:
            orders_count = await order_repo.count_by_telegram_id(user['telegram_id'])
            
            if orders_count > 0:
                leaderboard.append({
                    "telegram_id": user['telegram_id'],
                    "username": user.get('username', 'Unknown'),
                    "first_name": user.get('first_name', 'Unknown'),
                    "orders_count": orders_count,
                    "balance": user.get('balance', 0)
                })
        
        # Sort by orders count
        leaderboard.sort(key=lambda x: x['orders_count'], reverse=True)
        
        return leaderboard[:limit]
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{telegram_id}/check-bot-access")
async def check_user_bot_access(telegram_id: int):
    """Check if user can access the bot"""
    from server import bot_instance
    
    try:
        if not bot_instance:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        
        # Try to get user info
        try:
            chat = await bot_instance.get_chat(telegram_id)
            
            return {
                "has_access": True,
                "telegram_id": telegram_id,
                "username": chat.username,
                "first_name": chat.first_name
            }
        except Exception as e:
            logger.warning(f"Cannot access user {telegram_id}: {e}")
            return {
                "has_access": False,
                "telegram_id": telegram_id,
                "error": str(e)
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking bot access: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{telegram_id}/channel-status")
async def get_user_channel_status(telegram_id: int):
    """Check if user is member of required channel"""
    from server import bot_instance, CHANNEL_ID
    
    try:
        if not bot_instance or not CHANNEL_ID:
            return {
                "required": False,
                "is_member": True,
                "message": "Channel membership not required"
            }
        
        try:
            member = await bot_instance.get_chat_member(CHANNEL_ID, telegram_id)
            is_member = member.status in ['member', 'administrator', 'creator']
            
            return {
                "required": True,
                "is_member": is_member,
                "status": member.status
            }
        except Exception as e:
            logger.warning(f"Cannot check channel status for {telegram_id}: {e}")
            return {
                "required": True,
                "is_member": False,
                "error": str(e)
            }
    except Exception as e:
        logger.error(f"Error checking channel status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
