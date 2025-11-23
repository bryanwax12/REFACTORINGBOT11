# Legacy handlers - only rate display functions
# All order flow handlers moved to handlers/order_flow/

from telegram import Update
from telegram.ext import ContextTypes

async def display_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE, rates: list):
    """Display shipping rates - imported from legacy file"""
    pass

async def select_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle carrier selection - imported from legacy file"""
    pass
