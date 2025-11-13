"""
Order Flow: TO Address Handlers
Handles collection of recipient address information
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# These handlers will be imported from server.py initially
# Full refactoring will happen in future iteration

# Note: Due to the complexity and interdependencies of order flow handlers,
# this module currently serves as a placeholder for future refactoring.
# 
# The order flow in server.py includes:
# - order_to_name (TO_NAME step)
# - order_to_address (TO_ADDRESS step)
# - order_to_address2 (TO_ADDRESS2 step)
# - order_to_city (TO_CITY step)
# - order_to_state (TO_STATE step)
# - order_to_zip (TO_ZIP step)
# - order_to_phone (TO_PHONE step)
#
# Each handler follows the same pattern as FROM address handlers
#
# Future refactoring will move these handlers here with proper imports
