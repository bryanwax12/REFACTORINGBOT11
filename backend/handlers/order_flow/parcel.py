"""
Order Flow: Parcel Information Handlers
Handles collection of parcel dimensions and weight
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
# - order_parcel_weight (PARCEL_WEIGHT step)
# - order_parcel_length (PARCEL_LENGTH step)
# - order_parcel_width (PARCEL_WIDTH step)
# - order_parcel_height (PARCEL_HEIGHT step)
#
# Each handler validates numeric input and saves to session
#
# Future refactoring will move these handlers here with proper imports
