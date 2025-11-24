"""
Utilities for parallel async operations
Helps to speed up handlers by running independent operations concurrently
"""
import asyncio
import logging
from typing import List, Any, Callable, Coroutine

logger = logging.getLogger(__name__)


async def gather_safe(*coros, return_exceptions: bool = True):
    """
    Safe asyncio.gather that logs exceptions but doesn't fail
    
    Usage:
        results = await gather_safe(
            save_to_db(data),
            send_notification(user_id),
            log_action(event)
        )
    
    Args:
        *coros: Coroutines to run in parallel
        return_exceptions: Return exceptions instead of raising (default: True)
    
    Returns:
        List of results (or exceptions if return_exceptions=True)
    """
    try:
        results = await asyncio.gather(*coros, return_exceptions=return_exceptions)
        
        # Log any exceptions that occurred
        if return_exceptions:
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Exception in parallel operation {i}: {result}", exc_info=result)
        
        return results
    except Exception as e:
        logger.error(f"Error in gather_safe: {e}", exc_info=True)
        return [e] * len(coros)


async def parallel_db_and_send(db_operation, send_operation):
    """
    Run DB operation and Telegram send in parallel
    This is the most common pattern - save to DB while sending message
    
    Example:
        db_result, message = await parallel_db_and_send(
            session_service.update_session_step(user_id, "NEXT_STEP"),
            update.message.reply_text("Next question...")
        )
    
    Returns:
        Tuple: (db_result, send_result)
    """
    results = await gather_safe(db_operation, send_operation)
    return results[0], results[1]


class ParallelRunner:
    """
    Context manager for running multiple operations in parallel
    
    Usage:
        async with ParallelRunner() as runner:
            runner.add(save_to_db(data))
            runner.add(send_notification(user_id))
            runner.add(log_action(event))
        # All operations completed here
        results = runner.results
    """
    
    def __init__(self):
        self.tasks = []
        self.results = []
    
    def add(self, coro):
        """Add a coroutine to run in parallel"""
        self.tasks.append(coro)
        return self
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.tasks:
            self.results = await gather_safe(*self.tasks)
        return False  # Don't suppress exceptions


def run_parallel(*coros):
    """
    Decorator to run multiple operations in parallel after handler
    
    Example:
        @run_parallel(
            lambda ctx: log_action(ctx.user_id),
            lambda ctx: update_stats()
        )
        async def my_handler(update, context):
            # Main handler logic
            return NEXT_STATE
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Run main handler
            result = await func(*args, **kwargs)
            
            # Run parallel operations (don't wait for them)
            context = args[1] if len(args) > 1 else kwargs.get('context')
            if context:
                tasks = [coro(context) for coro in coros]
                asyncio.create_task(gather_safe(*tasks))
            
            return result
        return wrapper
    return decorator


# Performance monitoring
_operation_times = {}


async def timed_operation(name: str, coro):
    """
    Wrapper to measure operation time
    
    Usage:
        result = await timed_operation("save_user", save_user_to_db(user))
    """
    import time
    start = time.time()
    try:
        result = await coro
        duration = (time.time() - start) * 1000
        
        if name not in _operation_times:
            _operation_times[name] = []
        _operation_times[name].append(duration)
        
        # Log slow operations
        if duration > 100:
            logger.warning(f"⚠️ Slow operation '{name}': {duration:.2f}ms")
        
        return result
    except Exception as e:
        duration = (time.time() - start) * 1000
        logger.error(f"❌ Operation '{name}' failed after {duration:.2f}ms: {e}")
        raise


def get_performance_stats():
    """Get average times for all monitored operations"""
    import statistics
    
    stats = {}
    for name, times in _operation_times.items():
        if times:
            stats[name] = {
                'avg': statistics.mean(times),
                'min': min(times),
                'max': max(times),
                'count': len(times)
            }
    return stats
