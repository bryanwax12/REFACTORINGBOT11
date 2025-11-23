"""
Order handlers - General order management functions
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_create_label_request(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str):
    """Handle request to create/recreate shipping label for existing paid order"""
    from handlers.common_handlers import safe_telegram_call
    from server import create_and_send_label
    
    query = update.callback_query
    telegram_id = query.from_user.id
    
    # Get order details using Repository Pattern
    from repositories import get_repositories
    repos = get_repositories()
    order = await repos.orders.find_by_id(order_id)
    
    # Check if order belongs to user
    if not order or order.get('telegram_id') != telegram_id:
        await safe_telegram_call(query.message.reply_text("❌ Заказ не найден."))
        return
    
    if order['payment_status'] != 'paid':
        await safe_telegram_call(query.message.reply_text("❌ Заказ не оплачен. Создание лейбла невозможно."))
        return
    
    # Show confirmation message
    if order['shipping_status'] == 'label_created':
        await safe_telegram_call(query.message.reply_text(f"""⏳ Пересоздаю shipping label для заказа #{order_id[:8]}...

Это может занять несколько секунд."""))
    else:
        await safe_telegram_call(query.message.reply_text(f"""⏳ Создаю shipping label для заказа #{order_id[:8]}...

Это может занять несколько секунд."""))
    
    # Try to create label
    label_created = await create_and_send_label(order_id, telegram_id, query.message)
    
    if label_created:
        # Update order payment status to paid (if it was failed before)
        await repos.orders.update_by_id(order_id, {"payment_status": "paid"})
        
        keyboard = [[
            InlineKeyboardButton("🔙 Главное меню", callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            "✅ Shipping label успешно создан!",
            reply_markup=reply_markup
        ))
    else:
        keyboard = [[
            InlineKeyboardButton("🔙 Главное меню", callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            "❌ Не удалось создать shipping label. Пожалуйста, свяжитесь с администратором.",
            reply_markup=reply_markup
        ))


# ==================== ORDER FLOW REFACTORING TODO ====================

"""
Order Handlers
Main order creation flow (13 steps) for Telegram bot

This module contains all handlers for the order creation conversation flow.
Due to complexity (~1500 lines), handlers are grouped by phase:
1. FROM address (6 steps): name, street, city, state, zip, phone
2. TO address (6 steps): name, street, city, state, zip, phone  
3. Parcel details (4 steps): weight, length, width, height
4. Confirmation & rates: data review, fetch rates, select carrier

TODO: Gradually migrate handlers from server.py as features are added/modified
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Conversation states (imported from server.py)
# These define the flow steps
FROM_NAME = 0
FROM_ADDRESS = 1
FROM_ADDRESS2 = 2
FROM_CITY = 3
FROM_STATE = 4
FROM_ZIP = 5
FROM_PHONE = 6
TO_NAME = 7
TO_ADDRESS = 8
TO_ADDRESS2 = 9
TO_CITY = 10
TO_STATE = 11
TO_ZIP = 12
TO_PHONE = 13
PARCEL_WEIGHT = 14
PARCEL_LENGTH = 15
PARCEL_WIDTH = 16
PARCEL_HEIGHT = 17
CONFIRM_DATA = 18
SELECT_CARRIER = 19
PAYMENT_METHOD = 20
TEMPLATE_RENAME = 21
TEMPLATE_LOADED = 22


# ============================================================================
# ORDER FLOW: Entry Point
# ============================================================================

async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start new order flow
    
    Entry point for order creation conversation.
    Initializes session and starts FROM address collection.
    
    TODO: Migrate from server.py (line ~1318)
    """
    pass


# ============================================================================
# ORDER FLOW: FROM Address (Steps 1-6)
# ============================================================================

async def show_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show order data summary for confirmation
    
    Displays all collected data and asks user to confirm or edit.
    """
    pass


async def fetch_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fetch shipping rates from ShipStation API
    
    Makes API call to get available carriers and prices.
    Shows progress indicator to user.
    Caches results for 60 minutes.
    """
    pass


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
