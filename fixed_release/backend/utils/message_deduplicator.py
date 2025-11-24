"""
Message Deduplicator - prevents sending duplicate messages
Useful when MongoDB is slow and handlers get called multiple times
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MessageDeduplicator:
    """Prevents sending duplicate messages within a time window"""
    
    def __init__(self, window_seconds: int = 3):
        """
        Args:
            window_seconds: Time window to check for duplicates (default 3 seconds)
        """
        self._sent_messages = {}  # {(chat_id, message_hash): timestamp}
        self._window = window_seconds
        
    def should_send(self, chat_id: int, message_text: str) -> bool:
        """
        Check if message should be sent or is a duplicate
        
        Args:
            chat_id: Telegram chat ID
            message_text: Message text to check
            
        Returns:
            True if should send, False if duplicate
        """
        # Create hash from message text (simple hash)
        message_hash = hash(message_text[:100])  # First 100 chars
        key = (chat_id, message_hash)
        
        current_time = time.time()
        
        # Check if we sent this recently
        if key in self._sent_messages:
            last_sent = self._sent_messages[key]
            time_diff = current_time - last_sent
            
            if time_diff < self._window:
                logger.warning(
                    f"🚫 Duplicate message blocked for chat {chat_id} "
                    f"(sent {time_diff:.1f}s ago, within {self._window}s window)"
                )
                return False
        
        # Mark as sent
        self._sent_messages[key] = current_time
        
        # Cleanup old entries (every 100 messages)
        if len(self._sent_messages) > 100:
            self._cleanup_old_entries(current_time)
            
        return True
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove old entries to prevent memory leak"""
        cutoff = current_time - self._window * 2
        keys_to_remove = [
            key for key, timestamp in self._sent_messages.items()
            if timestamp < cutoff
        ]
        for key in keys_to_remove:
            del self._sent_messages[key]
        
        if keys_to_remove:
            logger.debug(f"🗑️ Cleaned up {len(keys_to_remove)} old message entries")


# Global instance
deduplicator = MessageDeduplicator(window_seconds=3)


def should_send_message(chat_id: int, message_text: str) -> bool:
    """
    Check if message should be sent (not a duplicate)
    
    Usage:
        if should_send_message(update.effective_chat.id, "Choose template"):
            await update.message.reply_text("Choose template", reply_markup=markup)
    """
    return deduplicator.should_send(chat_id, message_text)
