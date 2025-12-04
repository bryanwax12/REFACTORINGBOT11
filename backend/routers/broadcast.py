"""
Broadcast Router
Эндпоинты для рассылки сообщений
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from handlers.admin_handlers import verify_admin_key
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

@router.post("", dependencies=[Depends(verify_admin_key)])
async def broadcast_message(
    request: Request,
    broadcast: BroadcastRequest
):
    """
    Broadcast message to users - ADMIN ONLY
    
    Args:
        broadcast: Broadcast request with message, target, image_url, file_id
    """
    message = broadcast.message
    target = broadcast.target
    image_url = broadcast.image_url
    file_id = broadcast.file_id
    
    logger.info(f"📨 Broadcast request: image_url={image_url}, file_id={file_id}")
    
    # Fix image_url if it's relative path
    if image_url and not image_url.startswith('http'):
        # Get base URL from request - force HTTPS for external access
        base_url = str(request.base_url).rstrip('/')
        # Replace http:// with https:// for external URLs
        if base_url.startswith('http://') and 'emergentagent.com' in base_url:
            base_url = base_url.replace('http://', 'https://')
        
        if image_url.startswith('/'):
            image_url = f"{base_url}{image_url}"
        else:
            image_url = f"{base_url}/{image_url}"
        logger.info(f"🔧 Fixed image_url to: {image_url}")
    
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
            users = await user_repo.find_many({}, limit=10000)
        elif target == "active":
            # Users with at least one order
            from repositories import get_order_repo
            order_repo = get_order_repo()
            orders = await order_repo.find_many({}, limit=10000)
            active_telegram_ids = list(set([o['telegram_id'] for o in orders]))
            users = []
            for tid in active_telegram_ids:
                user = await user_repo.find_by_telegram_id(tid)
                if user:
                    users.append(user)
        elif target == "premium":
            # Users with balance > 0
            users = await user_repo.find_many({}, limit=10000)
            users = [u for u in users if u.get('balance', 0) > 0]
        else:
            raise HTTPException(status_code=400, detail="Invalid target. Use: all, active, or premium")
        
        if not users:
            raise HTTPException(status_code=404, detail="No users found for target audience")
        
        # Start broadcasting - OPTIMIZED: Parallel sending with batching
        logger.info(f"📢 Starting parallel broadcast to {len(users)} users. Target: {target}")
        
        # ⚡ Performance: Send in parallel batches to avoid rate limits
        BATCH_SIZE = 20  # Send 20 messages at once
        
        async def send_to_user(user):
            """Send message to a single user"""
            try:
                telegram_id = user['telegram_id']
                username = user.get('username', 'unknown')
                
                # Check if user blocked the bot
                if user.get('bot_blocked_by_user', False):
                    logger.debug(f"Skipping blocked user {username} ({telegram_id})")
                    return False, "blocked"
                
                # Send with image (file_id or URL)
                try:
                    result = None
                    
                    if file_id:
                        result = await bot_instance.send_photo(
                            chat_id=telegram_id,
                            photo=file_id,
                            caption=message
                        )
                    elif image_url:
                        result = await bot_instance.send_photo(
                            chat_id=telegram_id,
                            photo=image_url,
                            caption=message
                        )
                    else:
                        result = await bot_instance.send_message(
                            chat_id=telegram_id,
                            text=message
                        )
                    
                    if result:
                        logger.info(f"✅ Sent to {username} ({telegram_id})")
                        return True, None
                    else:
                        return False, "no_result"
                        
                except Exception as e:
                    send_error = str(e)
                    logger.error(f"❌ Error sending to {username} ({telegram_id}): {send_error}")
                    
                    # If chat not found or user blocked - mark in DB
                    if "chat not found" in send_error.lower() or "bot was blocked" in send_error.lower() or "user is deactivated" in send_error.lower():
                        try:
                            await user_repo.update_one(
                                {"telegram_id": telegram_id},
                                {"$set": {"bot_blocked_by_user": True}}
                            )
                        except Exception:
                            pass  # Ignore DB update errors during broadcast
                    
                    return False, send_error
                    
            except Exception as e:
                logger.error(f"❌ General error for user {user.get('telegram_id')}: {e}")
                return False, str(e)
        
        # Process in batches
        success_count = 0
        fail_count = 0
        
        for i in range(0, len(users), BATCH_SIZE):
            batch = users[i:i + BATCH_SIZE]
            logger.info(f"📤 Processing batch {i//BATCH_SIZE + 1}/{(len(users)-1)//BATCH_SIZE + 1} ({len(batch)} users)")
            
            # ⚡ Send all messages in batch PARALLELLY
            results = await asyncio.gather(*[send_to_user(user) for user in batch], return_exceptions=True)
            
            # Count results
            for result in results:
                if isinstance(result, tuple):
                    success, error = result
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    # Exception occurred
                    fail_count += 1
            
            # Small delay between batches to avoid Telegram rate limits
            if i + BATCH_SIZE < len(users):
                await asyncio.sleep(1)  # 1 second between batches
        
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
