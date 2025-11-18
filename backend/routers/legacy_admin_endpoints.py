"""
Legacy Admin Endpoints for Frontend Compatibility
These endpoints don't have /admin prefix for backward compatibility
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from handlers.admin_handlers import verify_admin_key
import logging

logger = logging.getLogger(__name__)

# Create legacy router WITHOUT /admin prefix
legacy_admin_router = APIRouter(
    prefix="/api",
    tags=["legacy-admin"]
)


# ============================================================
# LEGACY USER MANAGEMENT ENDPOINTS (without /admin prefix)
# ============================================================

@legacy_admin_router.get("/users/{telegram_id}/details")
async def get_user_details_legacy(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """
    Get user details (legacy endpoint for frontend)
    Frontend calls: /api/users/{telegram_id}/details
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
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@legacy_admin_router.post("/users/{telegram_id}/balance/add")
async def add_balance_legacy(
    request: Request,
    telegram_id: int,
    amount: float = Query(..., gt=0),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Add balance to user (legacy endpoint for frontend)
    Frontend calls: /api/users/{telegram_id}/balance/add
    """
    from server import db
    from services.admin.user_admin_service import user_admin_service
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    logger.info(f"[ADD_BALANCE] Endpoint called for telegram_id={telegram_id}, amount={amount}")
    logger.info(f"[ADD_BALANCE] bot_instance from app.state: {'AVAILABLE' if bot_instance else 'NONE'}")
    
    try:
        success, new_balance, error = await user_admin_service.update_user_balance(
            db,
            telegram_id,
            amount,
            operation="add"
        )
        
        logger.info(f"[ADD_BALANCE] update_user_balance result: success={success}, new_balance={new_balance}")
        
        if success:
            # Send beautiful notification to user
            logger.info(f"[ADD_BALANCE] Attempting to send balance notification to {telegram_id}, bot_instance={'AVAILABLE' if bot_instance else 'NONE'}")
            if bot_instance:
                try:
                    message = (
                        "💰 *БАЛАНС ПОПОЛНЕН*\n\n"
                        f"✨ Администратор добавил:\n"
                        f"💵 *+${amount:.2f}*\n\n"
                        f"💳 Текущий баланс: *${new_balance:.2f}*\n\n"
                        f"🎉 Спасибо!"
                    )
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode='Markdown'
                    ))
                    logger.info(f"✅ Balance notification sent to user {telegram_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to send balance notification: {e}")
            else:
                logger.warning(f"⚠️ bot_instance is None, cannot send notification to {telegram_id}")
            
            return {
                "success": True,
                "new_balance": new_balance,
                "message": f"Added ${amount} to balance"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@legacy_admin_router.post("/users/{telegram_id}/balance/deduct")
async def deduct_balance_legacy(
    request: Request,
    telegram_id: int,
    amount: float = Query(..., gt=0),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Deduct balance from user (legacy endpoint for frontend)
    Frontend calls: /api/users/{telegram_id}/balance/deduct
    """
    from server import db
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0, "balance": 1})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_balance = user.get("balance", 0)
        new_balance = max(0, current_balance - amount)
        
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"balance": new_balance}}
        )
        
        # Send beautiful notification to user
        logger.info(f"💬 [DEDUCT_BALANCE] Attempting to send notification, bot_instance={'AVAILABLE' if bot_instance else 'NONE'}")
        if bot_instance:
            try:
                message = (
                    "⚠️ *БАЛАНС ИЗМЕНЕН*\n\n"
                    f"📉 Администратор снял:\n"
                    f"💸 *-${amount:.2f}*\n\n"
                    f"💳 Текущий баланс: *${new_balance:.2f}*\n\n"
                    f"❓ Вопросы? Свяжитесь с поддержкой."
                )
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode='Markdown'
                ))
                logger.info(f"✅ Balance deduction notification sent to user {telegram_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send balance deduction notification: {e}")
        else:
            logger.warning(f"⚠️ bot_instance is None for deduction")
        
        logger.info(f"Admin deducted ${amount} from user {telegram_id}. New balance: ${new_balance}")
        
        return {
            "success": True,
            "new_balance": new_balance,
            "message": f"Deducted ${amount} from balance"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deducting balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@legacy_admin_router.post("/users/{telegram_id}/block")
async def block_user_legacy(
    request: Request,
    telegram_id: int,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Block user (legacy endpoint for frontend)
    Frontend calls: /api/users/{telegram_id}/block
    """
    from server import db
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": True}}
        )
        
        if result.modified_count > 0:
            logger.info(f"💬 [BLOCK_USER] Attempting to send notification, bot_instance={'AVAILABLE' if bot_instance else 'NONE'}")
            if bot_instance:
                try:
                    message = (
                        "⛔️ *АККАУНТ ЗАБЛОКИРОВАН*\n\n"
                        "🚫 Ваш доступ к боту ограничен администратором.\n\n"
                        "📞 Для разблокировки обратитесь в поддержку."
                    )
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode='Markdown'
                    ))
                    logger.info(f"✅ Block notification sent to user {telegram_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to send block notification: {e}")
            else:
                logger.warning(f"⚠️ bot_instance is None for block")
            
            return {"success": True, "message": "User blocked successfully"}
        else:
            return {"success": False, "message": "User already blocked"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@legacy_admin_router.post("/users/{telegram_id}/unblock")
async def unblock_user_legacy(
    request: Request,
    telegram_id: int,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Unblock user (legacy endpoint for frontend)
    Frontend calls: /api/users/{telegram_id}/unblock
    """
    from server import db
    from handlers.common_handlers import safe_telegram_call
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": False}}
        )
        
        if result.modified_count > 0:
            logger.info(f"💬 [UNBLOCK_USER] Attempting to send notification, bot_instance={'AVAILABLE' if bot_instance else 'NONE'}")
            if bot_instance:
                try:
                    message = (
                        "✅ *АККАУНТ РАЗБЛОКИРОВАН*\n\n"
                        "🎉 Ваш доступ к боту восстановлен!\n\n"
                        "✨ Теперь вы можете пользоваться всеми функциями.\n\n"
                        "💫 Добро пожаловать обратно!"
                    )
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode='Markdown'
                    ))
                    logger.info(f"✅ Unblock notification sent to user {telegram_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to send unblock notification: {e}")
            else:
                logger.warning(f"⚠️ bot_instance is None for unblock")
            
            return {"success": True, "message": "User unblocked successfully"}
        else:
            return {"success": False, "message": "User already unblocked"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@legacy_admin_router.post("/users/{telegram_id}/invite-channel")
async def invite_to_channel_legacy(
    request: Request,
    telegram_id: int,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Send channel invite to user (legacy endpoint for frontend)
    Frontend calls: /api/users/{telegram_id}/invite-channel
    """
    from server import db
    from handlers.common_handlers import safe_telegram_call
    from datetime import datetime, timezone
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if bot_instance:
            try:
                channel_link = "https://t.me/+your_channel_invite_link"
                message = (
                    "🎁 *СПЕЦИАЛЬНОЕ ПРИГЛАШЕНИЕ*\n\n"
                    "🌟 Присоединяйтесь к нашему VIP-каналу!\n\n"
                    "🎯 *Что вы получите:*\n"
                    "🔥 Эксклюзивные предложения\n"
                    "📢 Новости первыми\n"
                    "💡 Полезные советы\n"
                    "🎁 Специальные бонусы\n\n"
                    f"👉 [Присоединиться]({channel_link})\n\n"
                    "⚡️ Не упустите возможность!"
                )
                
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode='Markdown'
                ))
                
                # Update database
                await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {
                        "$set": {
                            "channel_invite_sent": True,
                            "channel_invite_sent_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                return {"success": True, "message": "Invitation sent successfully"}
            
            except Exception as e:
                logger.error(f"Failed to send channel invite: {e}")
                return {"success": False, "message": str(e)}
        else:
            return {"success": False, "message": "Bot not initialized"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending channel invite: {e}")
        raise HTTPException(status_code=500, detail=str(e))
