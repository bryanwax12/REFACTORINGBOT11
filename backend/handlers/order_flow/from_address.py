"""
Order Flow: FROM Address Handlers
Handles collection of sender address information
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
# - order_from_name (FROM_NAME step)
# - order_from_address (FROM_ADDRESS step)
# - order_from_address2 (FROM_ADDRESS2 step)
# - order_from_city (FROM_CITY step)
# - order_from_state (FROM_STATE step)
# - order_from_zip (FROM_ZIP step)
# - order_from_phone (FROM_PHONE step)
#
# Each handler:
# 1. Validates user input with regex
# 2. Saves to session_manager
# 3. Shows next step with inline keyboard
# 4. Returns next conversation state
#
# Future refactoring will move these handlers here with proper imports
