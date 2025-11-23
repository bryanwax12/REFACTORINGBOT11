async def display_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE, rates: list):
    """
    Display available shipping rates to user
    
    Groups rates by carrier and shows with prices.
    Reusable for both cached and fresh rates.
    """
    pass


async def select_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle carrier selection from user
    
    Proceeds to payment or balance check.
    """
    pass


# ============================================================================
# ORDER FLOW: Helper Functions
# ============================================================================

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current order and clear session"""
    pass


async def return_to_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order from other menus"""
    pass


# ============================================================================
# CONVERSATION HANDLER SETUP
# ============================================================================

def create_order_conversation_handler():
    """
    Create and configure the order ConversationHandler
    
    Returns:
        ConversationHandler: Configured handler with all states
    
    TODO: Migrate from server.py (line ~8485)
    """
    pass


# ============================================================================
# MIGRATION NOTES
# ============================================================================

"""
MIGRATION PLAN:

Phase 1: Helper functions (100 lines)
- safe_telegram_call, mark_message_as_selected
- sanitize_*, validate_* functions
Status: TODO

Phase 2: FROM address handlers (250 lines)
- order_from_name → order_from_phone
Status: TODO

Phase 3: TO address handlers (250 lines)
- order_to_name → order_to_phone
Status: TODO

Phase 4: Parcel handlers (200 lines)
- order_parcel_weight → order_parcel_height
Status: TODO

Phase 5: Confirmation & rates (400 lines)
- show_data_confirmation
- fetch_shipping_rates
- display_shipping_rates
- select_carrier
Status: TODO

Phase 6: ConversationHandler setup (200 lines)
- States configuration
- Entry points, states, fallbacks
Status: TODO

TOTAL: ~1500 lines
When to do: When modifying order flow or adding features
"""
