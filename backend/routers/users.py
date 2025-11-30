"""
Users Router
Эндпоинты для управления пользователями
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


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
        
        success = await user_repo.block_user(telegram_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to block user")
        
        logger.info(f"🚫 User {telegram_id} blocked. Reason: {reason or 'No reason'}")
        
        # Send notification to user
        try:
            from server import bot_instance
            from handlers.common_handlers import safe_telegram_call
            
            if bot_instance:
                block_message = (
                    "🚫 *Ваш аккаунт заблокирован*\n\n"
                    "Доступ к боту ограничен.\n"
                )
                if reason:
                    block_message += f"Причина: {reason}\n\n"
                block_message += "Для получения дополнительной информации свяжитесь с администратором."
                
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=telegram_id,
                    text=block_message,
                    parse_mode='Markdown'
                ))
                logger.info(f"✅ Block notification sent to user {telegram_id}")
        except Exception as notify_error:
            logger.warning(f"Failed to send block notification: {notify_error}")
        
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
        
        # Send notification to user
        try:
            from server import bot_instance
            from handlers.common_handlers import safe_telegram_call
            
            if bot_instance:
                unblock_message = (
                    "✅ *Ваш аккаунт разблокирован*\n\n"
                    "Доступ к боту восстановлен.\n"
                    "Вы можете продолжить использовать бот."
                )
                
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=telegram_id,
                    text=unblock_message,
                    parse_mode='Markdown'
                ))
                logger.info(f"✅ Unblock notification sent to user {telegram_id}")
        except Exception as notify_error:
            logger.warning(f"Failed to send unblock notification: {notify_error}")
        
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
    from server import bot_instance
    from handlers.common_handlers import safe_telegram_call
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        success = await user_repo.update_balance(telegram_id, amount, operation="add")
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add balance")
        
        new_balance = user.get('balance', 0) + amount
        
        logger.info(f"💰 [USERS_ROUTER] Added ${amount} to user {telegram_id}. New balance: ${new_balance}")
        logger.info(f"📋 [USERS_ROUTER] bot_instance available: {bot_instance is not None}")
        
        # Send notification to user
        if bot_instance:
            try:
                message = (
                    "💰 *БАЛАНС ПОПОЛНЕН*\n\n"
                    f"✨ Администратор добавил:\n"
                    f"💵 *+${amount:.2f}*\n\n"
                    f"💳 Текущий баланс: *${new_balance:.2f}*\n\n"
                    f"🎉 Спасибо!"
                )
                
                # Add "Continue Order" button
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 Продолжить заказ", callback_data="continue_order")]
                ])
                
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                ))
                logger.info(f"✅ [USERS_ROUTER] Balance notification sent to user {telegram_id}")
            except Exception as e:
                logger.error(f"❌ [USERS_ROUTER] Failed to send balance notification: {e}", exc_info=True)
        else:
            logger.warning(f"⚠️ [USERS_ROUTER] bot_instance is None, cannot send notification")
        
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
        
        success = await user_repo.update_balance(telegram_id, amount, operation="subtract")
        
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
        
        await user_repo.update_user_field(telegram_id, "discount", discount)
        
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


@router.post("/check-all-channel-status")
async def check_all_channel_status():
    """Check channel membership status for all users"""
    from repositories import get_user_repo
    from server import bot_instance
    from telegram.error import TelegramError
    import os
    
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot instance not available")
    
    try:
        channel_id = os.getenv('CHANNEL_ID')
        if not channel_id:
            raise HTTPException(status_code=400, detail="CHANNEL_ID not configured")
        
        from server import db
        users = await db.users.find({}, {"_id": 0, "telegram_id": 1}).to_list(10000)
        
        checked_count = 0
        member_count = 0
        
        for user in users:
            telegram_id = user['telegram_id']
            
            try:
                # Check channel membership
                member = await bot_instance.get_chat_member(chat_id=channel_id, user_id=telegram_id)
                is_member = member.status in ['member', 'administrator', 'creator']
                
                # Update user record
                from server import db
                await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {
                        "is_channel_member": is_member,
                        "channel_status_checked_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                if is_member:
                    member_count += 1
                checked_count += 1
                
            except TelegramError as e:
                logger.warning(f"Failed to check channel status for user {telegram_id}: {e}")
                continue
        
        logger.info(f"✅ Checked channel status for {checked_count} users. Members: {member_count}")
        
        return {
            "success": True,
            "checked_count": checked_count,
            "member_count": member_count
        }
    except Exception as e:
        logger.error(f"Error checking all channel status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-all-bot-access")
async def check_all_bot_access():
    """Check bot accessibility for all users"""
    from repositories import get_user_repo
    from server import bot_instance
    from telegram.error import TelegramError, Forbidden
    import asyncio
    from datetime import datetime
    
    if not bot_instance:
        raise HTTPException(status_code=503, detail="Bot instance not available")
    
    try:
        from server import db
        users = await db.users.find({}, {"_id": 0, "telegram_id": 1}).to_list(10000)
        
        checked_count = 0
        accessible_count = 0
        blocked_count = 0
        
        for user in users:
            telegram_id = user['telegram_id']
            
            try:
                # Try to send a test action (get chat info)
                await bot_instance.get_chat(chat_id=telegram_id)
                
                # Bot is accessible
                from server import db
                await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {
                        "bot_blocked_by_user": False,
                        "bot_access_checked_at": datetime.utcnow().isoformat()
                    }}
                )
                accessible_count += 1
                checked_count += 1
                
            except Forbidden:
                # User blocked the bot
                from server import db
                await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {
                        "bot_blocked_by_user": True,
                        "bot_blocked_at": datetime.utcnow().isoformat(),
                        "bot_access_checked_at": datetime.utcnow().isoformat()
                    }}
                )
                blocked_count += 1
                checked_count += 1
                
            except TelegramError as e:
                logger.warning(f"Failed to check bot access for user {telegram_id}: {e}")
                continue
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.05)
        
        logger.info(f"✅ Checked bot access for {checked_count} users. Accessible: {accessible_count}, Blocked: {blocked_count}")
        
        return {
            "success": True,
            "checked_count": checked_count,
            "accessible_count": accessible_count,
            "blocked_count": blocked_count
        }
    except Exception as e:
        logger.error(f"Error checking all bot access: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard")
async def get_users_leaderboard(limit: int = 10):
    """Get users leaderboard by orders count"""
    from repositories import get_user_repo, get_order_repo
    
    try:
        from server import db
        users = await db.users.find({}, {"_id": 0, "telegram_id": 1}).to_list(1000)
        
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
    from server import bot_instance, CHANNEL_ID, db
    from datetime import datetime, timezone
    
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
            
            # Update database with channel status
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {
                    "$set": {
                        "is_channel_member": is_member,
                        "channel_status_checked_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            logger.info(f"✅ Updated channel status for {telegram_id}: is_member={is_member}")
            
            return {
                "required": True,
                "is_member": is_member,
                "status": member.status
            }
        except Exception as e:
            logger.warning(f"Cannot check channel status for {telegram_id}: {e}")
            # Update DB that user is NOT a member (could be left or bot has no access)
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {
                    "$set": {
                        "is_channel_member": False,
                        "channel_status_checked_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            return {
                "required": True,
                "is_member": False,
                "error": str(e)
            }
    except Exception as e:
        logger.error(f"Error checking channel status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
