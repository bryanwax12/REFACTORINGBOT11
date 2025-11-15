"""
Retry Utilities
Centralized retry logic for handling transient errors
"""
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import httpx
from pymongo.errors import (
    ConnectionFailure,
    NetworkTimeout,
    ServerSelectionTimeoutError
)

logger = logging.getLogger(__name__)


# ============================================================
# RETRY DECORATORS FOR DIFFERENT SCENARIOS
# ============================================================

def retry_on_api_error(max_attempts=3, min_wait=1, max_wait=10):
    """
    Retry decorator for external API calls
    
    Handles:
    - httpx network errors
    - Timeouts
    - 5xx server errors
    
    Usage:
        @retry_on_api_error(max_attempts=3)
        async def call_external_api():
            ...
    """
    return retry(
        retry=retry_if_exception_type((
            httpx.RequestError,
            httpx.TimeoutException,
            httpx.HTTPStatusError
        )),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )


def retry_on_db_error(max_attempts=3, min_wait=1, max_wait=5):
    """
    Retry decorator for MongoDB operations
    
    Handles:
    - Connection failures
    - Network timeouts
    - Server selection timeouts
    
    Usage:
        @retry_on_db_error(max_attempts=3)
        async def query_database():
            ...
    """
    return retry(
        retry=retry_if_exception_type((
            ConnectionFailure,
            NetworkTimeout,
            ServerSelectionTimeoutError
        )),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )


def retry_on_telegram_error(max_attempts=3, min_wait=2, max_wait=10):
    """
    Retry decorator for Telegram API calls
    
    Handles:
    - Rate limit errors (RetryAfter)
    - Network errors
    - Timeouts
    
    Usage:
        @retry_on_telegram_error(max_attempts=3)
        async def send_telegram_message():
            ...
    """
    from telegram.error import NetworkError, TimedOut, RetryAfter
    
    return retry(
        retry=retry_if_exception_type((
            NetworkError,
            TimedOut,
            RetryAfter
        )),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )


# ============================================================
# MANUAL RETRY HELPERS
# ============================================================

async def retry_async_operation(
    operation,
    max_attempts=3,
    operation_name="operation",
    *args,
    **kwargs
):
    """
    Manual retry wrapper for async operations
    
    Args:
        operation: Async function to retry
        max_attempts: Maximum retry attempts
        operation_name: Name for logging
        *args, **kwargs: Arguments for operation
    
    Returns:
        Result of operation or None on failure
    
    Example:
        result = await retry_async_operation(
            fetch_rates,
            max_attempts=3,
            operation_name="fetch_rates",
            order_data=data
        )
    """
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"🔄 Attempt {attempt}/{max_attempts}: {operation_name}")
            result = await operation(*args, **kwargs)
            logger.info(f"✅ Success on attempt {attempt}: {operation_name}")
            return result
            
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️ Attempt {attempt}/{max_attempts} failed: {operation_name} - {str(e)}")
            
            if attempt < max_attempts:
                wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                logger.info(f"⏳ Waiting {wait_time}s before retry...")
                import asyncio
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ All {max_attempts} attempts failed: {operation_name}")
    
    return None


# ============================================================
# ERROR CONTEXT MANAGER
# ============================================================

class ErrorHandler:
    """
    Context manager for handling errors with logging and fallback
    
    Usage:
        async with ErrorHandler("create_order", fallback_value=None):
            order = await create_order(data)
    """
    
    def __init__(self, operation_name, fallback_value=None, raise_on_error=False):
        self.operation_name = operation_name
        self.fallback_value = fallback_value
        self.raise_on_error = raise_on_error
    
    async def __aenter__(self):
        logger.info(f"🔵 Starting: {self.operation_name}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            logger.info(f"✅ Completed: {self.operation_name}")
            return True
        
        # Log error with context
        logger.error(
            f"❌ Error in {self.operation_name}: {exc_type.__name__}: {exc_val}",
            exc_info=True
        )
        
        if self.raise_on_error:
            return False  # Re-raise exception
        
        # Suppress exception and use fallback
        logger.info(f"🔄 Using fallback value for {self.operation_name}")
        return True  # Suppress exception


# ============================================================
# CIRCUIT BREAKER (ADVANCED)
# ============================================================

class CircuitBreaker:
    """
    Circuit breaker pattern for external services
    
    Prevents cascading failures by "opening" circuit after too many failures
    
    States:
    - CLOSED: Normal operation
    - OPEN: Rejecting calls (fast-fail)
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(self, failure_threshold=5, timeout=60, name="service"):
        self.failure_threshold = failure_threshold
        self.timeout = timeout  # Seconds before trying again
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def is_available(self):
        """Check if circuit allows calls"""
        import time
        
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # Check if timeout expired
            if time.time() - self.last_failure_time > self.timeout:
                logger.info(f"🟡 Circuit HALF_OPEN for {self.name} (testing)")
                self.state = "HALF_OPEN"
                return True
            
            logger.warning(f"🔴 Circuit OPEN for {self.name} (fast-fail)")
            return False
        
        if self.state == "HALF_OPEN":
            return True
        
        return False
    
    def record_success(self):
        """Record successful call"""
        if self.state == "HALF_OPEN":
            logger.info(f"✅ Circuit CLOSED for {self.name} (recovered)")
            self.state = "CLOSED"
        
        self.failure_count = 0
    
    def record_failure(self):
        """Record failed call"""
        import time
        
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            logger.error(f"🔴 Circuit OPEN for {self.name} (too many failures: {self.failure_count})")
            self.state = "OPEN"


# ============================================================
# GLOBAL CIRCUIT BREAKERS
# ============================================================

# Create circuit breakers for external services
SHIPSTATION_CIRCUIT = CircuitBreaker(failure_threshold=5, timeout=60, name="ShipStation")
OXAPAY_CIRCUIT = CircuitBreaker(failure_threshold=5, timeout=60, name="Oxapay")


# ============================================================
# USAGE EXAMPLES
# ============================================================

"""
Example 1: Decorator for API calls
-----------------------------------
from utils.retry_utils import retry_on_api_error

@retry_on_api_error(max_attempts=3)
async def fetch_rates_from_shipstation(data):
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
    return response.json()


Example 2: Manual retry
------------------------
from utils.retry_utils import retry_async_operation

result = await retry_async_operation(
    create_label,
    max_attempts=3,
    operation_name="create_label",
    order_id=order_id
)


Example 3: Error context manager
---------------------------------
from utils.retry_utils import ErrorHandler

async with ErrorHandler("process_payment", fallback_value=False):
    success = await process_payment(order)


Example 4: Circuit breaker
---------------------------
from utils.retry_utils import SHIPSTATION_CIRCUIT

if not SHIPSTATION_CIRCUIT.is_available():
    return {"error": "ShipStation temporarily unavailable"}

try:
    result = await call_shipstation_api()
    SHIPSTATION_CIRCUIT.record_success()
except Exception as e:
    SHIPSTATION_CIRCUIT.record_failure()
    raise
"""
