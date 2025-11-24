"""
Rate Limiter Middleware for Telegram Bot
Prevents API rate limiting and potential bans
"""
import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TelegramRateLimiter:
    """
    Smart rate limiter for Telegram Bot API
    Prevents hitting rate limits while maximizing throughput
    """
    
    def __init__(self):
        # Per-chat rate limiting
        self.chat_message_times: Dict[int, deque] = defaultdict(lambda: deque(maxlen=30))
        self.global_message_times = deque(maxlen=100)
        
        # Rate limits (slightly below Telegram limits for safety)
        self.MESSAGES_PER_SECOND = 25      # Telegram limit: 30/sec
        self.MESSAGES_PER_MINUTE = 1500    # Safe margin
        self.MESSAGES_PER_CHAT_MINUTE = 60 # Per-chat limit
        
        # Semaphores for concurrent control
        self.global_semaphore = asyncio.Semaphore(50)
        self.chat_semaphores: Dict[int, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(5)
        )
    
    async def acquire(self, chat_id: Optional[int] = None) -> bool:
        """
        Acquire permission to send message
        Returns True if allowed, False if rate limited
        """
        async with self.global_semaphore:
            current_time = time.time()
            
            # Global rate check
            if not self._check_global_rate(current_time):
                logger.warning("Global rate limit reached, delaying...")
                await asyncio.sleep(0.1)  # Brief delay
                return False
            
            # Chat-specific rate check
            if chat_id and not self._check_chat_rate(chat_id, current_time):
                logger.warning(f"Chat {chat_id} rate limit reached, delaying...")
                await asyncio.sleep(0.05)  # Very brief delay
                return False
            
            # Record message time
            self.global_message_times.append(current_time)
            if chat_id:
                self.chat_message_times[chat_id].append(current_time)
            
            return True
    
    def _check_global_rate(self, current_time: float) -> bool:
        """Check global rate limits"""
        # Remove old entries
        while (self.global_message_times and 
               current_time - self.global_message_times[0] > 60):
            self.global_message_times.popleft()
        
        # Check per-second limit (last 1 second)
        recent_messages = sum(
            1 for t in self.global_message_times 
            if current_time - t <= 1.0
        )
        if recent_messages >= self.MESSAGES_PER_SECOND:
            return False
        
        # Check per-minute limit
        if len(self.global_message_times) >= self.MESSAGES_PER_MINUTE:
            return False
        
        return True
    
    def _check_chat_rate(self, chat_id: int, current_time: float) -> bool:
        """Check per-chat rate limits"""
        chat_times = self.chat_message_times[chat_id]
        
        # Remove old entries
        while chat_times and current_time - chat_times[0] > 60:
            chat_times.popleft()
        
        # Check per-chat per-minute limit
        if len(chat_times) >= self.MESSAGES_PER_CHAT_MINUTE:
            return False
        
        return True
    
    async def safe_send_message(self, send_func, chat_id: int, *args, **kwargs):
        """
        Safely send message with rate limiting
        """
        max_retries = 3
        base_delay = 0.1
        
        for attempt in range(max_retries):
            if await self.acquire(chat_id):
                try:
                    return await send_func(*args, **kwargs)
                except Exception as e:
                    if 'Too Many Requests' in str(e):
                        # Telegram rate limit hit - wait longer
                        wait_time = base_delay * (2 ** attempt)
                        logger.warning(f"Telegram rate limit hit, waiting {wait_time:.2f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Other error - re-raise
                        raise
            else:
                # Rate limiter blocked - short wait
                await asyncio.sleep(base_delay * (attempt + 1))
        
        raise Exception(f"Failed to send message after {max_retries} attempts (rate limited)")


# Global rate limiter instance
rate_limiter = TelegramRateLimiter()


# Decorator for automatic rate limiting
def rate_limited(func):
    """
    Decorator to automatically apply rate limiting to functions
    """
    async def wrapper(*args, **kwargs):
        # Try to extract chat_id from args/kwargs
        chat_id = None
        if args and hasattr(args[0], 'chat_id'):
            chat_id = args[0].chat_id
        elif 'chat_id' in kwargs:
            chat_id = kwargs['chat_id']
        
        return await rate_limiter.safe_send_message(func, chat_id, *args, **kwargs)
    
    return wrapper
