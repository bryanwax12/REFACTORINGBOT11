"""
Input debouncing mechanism to prevent duplicate processing
when user types very fast
"""
import time
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Store last processed message time per user+handler
_last_processed = {}

def debounce_input(min_interval: float = 0.3, show_reminder: bool = True):
    """
    Decorator to prevent processing duplicate inputs when user types very fast
    
    Args:
        min_interval: Minimum time (seconds) between processing messages from same user
                     Default: 0.3 seconds (300ms)
        show_reminder: Show friendly reminder to user if they type too fast
    
    How it works:
    - First message: Processes immediately
    - Subsequent messages within min_interval: Ignored with optional reminder
    - After min_interval: Processes normally
    
    This prevents race conditions when user sends multiple messages in <300ms
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            if not update.effective_user:
                return await func(update, context, *args, **kwargs)
            
            user_id = update.effective_user.id
            handler_name = func.__name__
            key = f"{user_id}_{handler_name}"
            
            current_time = time.time()
            last_time = _last_processed.get(key, 0)
            time_since_last = current_time - last_time
            
            # Track fast input count
            fast_input_key = f"{key}_fast_count"
            if time_since_last < min_interval:
                fast_count = context.user_data.get(fast_input_key, 0) + 1
                context.user_data[fast_input_key] = fast_count
                
                logger.info(
                    f"🚫 Debounce: Ignoring fast input from user {user_id} "
                    f"in {handler_name} (interval: {time_since_last:.3f}s < {min_interval}s, count: {fast_count})"
                )
                
                # Show friendly reminder after 3 fast inputs
                if show_reminder and fast_count >= 3:
                    try:
                        await update.message.reply_text(
                            "⏱ Пожалуйста, вводите данные медленнее.\n"
                            "Ваше предыдущее сообщение ещё обрабатывается...",
                            quote=False
                        )
                        context.user_data[fast_input_key] = 0  # Reset after showing reminder
                    except Exception as e:
                        logger.warning(f"Failed to send fast input reminder: {e}")
                
                # Return current state without processing
                return context.user_data.get('last_conversation_state')
            else:
                # Reset fast input counter if user slowed down
                context.user_data[fast_input_key] = 0
            
            # Update last processed time
            _last_processed[key] = current_time
            
            # Process the message
            result = await func(update, context, *args, **kwargs)
            
            # Store the returned state for potential duplicate messages
            if result is not None:
                context.user_data['last_conversation_state'] = result
            
            return result
        
        return wrapper
    return decorator


def clear_debounce_for_user(user_id: int, handler_name: str = None):
    """
    Clear debounce state for a user
    
    Args:
        user_id: Telegram user ID
        handler_name: Optional specific handler to clear. If None, clears all handlers for user
    """
    if handler_name:
        key = f"{user_id}_{handler_name}"
        _last_processed.pop(key, None)
        logger.info(f"🧹 Cleared debounce for user {user_id}, handler {handler_name}")
    else:
        # Clear all handlers for this user
        keys_to_remove = [k for k in _last_processed.keys() if k.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            _last_processed.pop(key, None)
        logger.info(f"🧹 Cleared all debounce states for user {user_id}")


def get_debounce_stats() -> dict:
    """Get current debounce statistics"""
    return {
        'active_debounces': len(_last_processed),
        'entries': list(_last_processed.keys())
    }
