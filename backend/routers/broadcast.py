"""
Broadcast Router
Эндпоинты для рассылки сообщений
"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])


from pydantic import BaseModel

class BroadcastRequest(BaseModel):
    message: str
    target: str = "all"
    image_url: Optional[str] = None
    file_id: Optional[str] = None

@router.post("")
async def broadcast_message(
    request: Request,
    broadcast: BroadcastRequest
):
    """
    Broadcast message to users
    
    Args:
        broadcast: Broadcast request with message, target, image_url, file_id
    """
    message = broadcast.message
    target = broadcast.target
    image_url = broadcast.image_url
    file_id = broadcast.file_id
    from server import safe_telegram_call
    from repositories import get_user_repo
    
    # Get bot_instance from app.state
    bot_instance = getattr(request.app.state, 'bot_instance', None)
    
    try:
        if not bot_instance:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        user_repo = get_user_repo()
        
        # Get target users
        if target == "all":
            users = await user_repo.find_all(limit=10000)
        elif target == "active":
            # Users with at least one order
            from repositories import get_order_repo
            order_repo = get_order_repo()
            orders = await order_repo.find_all(limit=10000)
            active_telegram_ids = list(set([o['telegram_id'] for o in orders]))
            users = []
            for tid in active_telegram_ids:
                user = await user_repo.find_by_telegram_id(tid)
                if user:
                    users.append(user)
        elif target == "premium":
            # Users with balance > 0
            users = await user_repo.find_all(limit=10000)
            users = [u for u in users if u.get('balance', 0) > 0]
        else:
            raise HTTPException(status_code=400, detail="Invalid target. Use: all, active, or premium")
        
        if not users:
            raise HTTPException(status_code=404, detail="No users found for target audience")
        
        # Start broadcasting
        logger.info(f"📢 Starting broadcast to {len(users)} users. Target: {target}")
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                telegram_id = user['telegram_id']
                
                # Check if user blocked the bot
                if user.get('bot_blocked_by_user', False):
                    fail_count += 1
                    continue
                
                # Send with image (file_id or URL)
                if file_id:
                    # Use file_id (faster, no need to re-download)
                    await safe_telegram_call(
                        bot_instance.send_photo(
                            chat_id=telegram_id,
                            photo=file_id,
                            caption=message
                        )
                    )
                elif image_url:
                    # Use URL (will download image)
                    await safe_telegram_call(
                        bot_instance.send_photo(
                            chat_id=telegram_id,
                            photo=image_url,
                            caption=message
                        )
                    )
                else:
                    # Text only message
                    await safe_telegram_call(
                        bot_instance.send_message(
                            chat_id=telegram_id,
                            text=message
                        )
                    )
                
                success_count += 1
                
                # Rate limiting
                await asyncio.sleep(0.05)  # 50ms delay between messages
                
            except Exception as e:
                logger.error(f"Failed to send to {telegram_id}: {e}")
                fail_count += 1
        
        logger.info(f"✅ Broadcast complete. Success: {success_count}, Failed: {fail_count}")
        
        return {
            "status": "completed",
            "target": target,
            "total_users": len(users),
            "success_count": success_count,
            "fail_count": fail_count,
            "message": message[:100]  # First 100 chars
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
