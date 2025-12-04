"""
State Validation Utilities
Provides functions to validate conversation states
"""
import logging

logger = logging.getLogger(__name__)


def validate_state(state, valid_states: list, context: str = "unknown") -> bool:
    """
    Validates that state is valid for the conversation flow
    
    Args:
        state: State constant to validate (e.g., FROM_NAME, TO_CITY)
        valid_states: List of valid state constants
        context: Context string for logging (e.g., "return_to_order")
    
    Returns:
        bool: True if state is valid, False otherwise
    
    Example:
        from server import ORDER_FLOW_STATES, FROM_NAME
        
        if validate_state(saved_state, ORDER_FLOW_STATES, "return_to_order"):
            return saved_state
        else:
            return FROM_NAME
    """
    # Check if state is None
    if state is None:
        logger.error(f"❌ State validation failed in {context}: State is None")
        return False
    
    # Check if state is in valid_states list
    if state not in valid_states:
        logger.error(
            f"❌ State validation failed in {context}: "
            f"State {state} is not in valid states list"
        )
        return False
    
    # State is valid
    logger.debug(f"✅ State {state} is valid in {context}")
    return True


def log_state_transition(
    user_id: int,
    from_state,
    to_state,
    handler_name: str,
    additional_info: dict = None
):
    """
    Logs state transitions for debugging conversation flow issues
    
    Args:
        user_id: Telegram user ID
        from_state: Current/previous state constant
        to_state: Next state constant
        handler_name: Name of handler performing transition
        additional_info: Optional dict with additional context
    
    Example:
        log_state_transition(
            user_id=12345,
            from_state=FROM_CITY,
            to_state=FROM_STATE,
            handler_name="order_from_city",
            additional_info={"city": "New York"}
        )
    """
    from_state_name = _get_state_name(from_state)
    to_state_name = _get_state_name(to_state)
    
    log_msg = (
        f"🔄 State transition: User {user_id} | "
        f"Handler: {handler_name} | "
        f"From: {from_state_name} → To: {to_state_name}"
    )
    
    if additional_info:
        info_str = ", ".join([f"{k}={v}" for k, v in additional_info.items()])
        log_msg += f" | Info: {info_str}"
    
    logger.info(log_msg)


def _get_state_name(state) -> str:
    """
    Helper to get human-readable state name
    
    Args:
        state: State constant
    
    Returns:
        str: State name or "UNKNOWN" if not found
    """
    try:
        from server import STATE_NAMES
        return STATE_NAMES.get(state, f"UNKNOWN({state})")
    except Exception:
        return f"STATE({state})"


def validate_and_log_transition(
    user_id: int,
    saved_state,
    valid_states: list,
    handler_name: str,
    fallback_state
):
    """
    Combined validation and logging for state transitions
    
    Args:
        user_id: Telegram user ID
        saved_state: State to validate
        valid_states: List of valid states
        handler_name: Name of handler
        fallback_state: State to return if validation fails
    
    Returns:
        Validated state or fallback_state
    
    Example:
        return validate_and_log_transition(
            user_id=user_id,
            saved_state=saved_state,
            valid_states=ORDER_FLOW_STATES,
            handler_name="return_to_order",
            fallback_state=FROM_NAME
        )
    """
    if validate_state(saved_state, valid_states, handler_name):
        log_state_transition(
            user_id=user_id,
            from_state="CANCELLED",
            to_state=saved_state,
            handler_name=handler_name,
            additional_info={"status": "valid_state_restored"}
        )
        return saved_state
    else:
        logger.warning(
            f"⚠️ Invalid state {saved_state} for user {user_id} in {handler_name}, "
            f"falling back to {_get_state_name(fallback_state)}"
        )
        log_state_transition(
            user_id=user_id,
            from_state="CANCELLED",
            to_state=fallback_state,
            handler_name=handler_name,
            additional_info={"status": "fallback_used", "invalid_state": saved_state}
        )
        return fallback_state
