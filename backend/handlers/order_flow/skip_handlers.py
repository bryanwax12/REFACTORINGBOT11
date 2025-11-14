"""
Order Flow: Skip Handlers
Handles skip actions for optional fields with proper UI and state management
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.decorators import with_typing_indicator
from utils.ui_utils import get_cancel_keyboard, OrderStepMessages


async def handle_skip_field(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    field_name: str,
    field_value: any,
    next_step_const: int,
    next_step_name: str,
    next_message: str
):
    """
    Universal handler for skipping optional fields
    
    Args:
        update: Telegram Update object
        context: Bot context
        field_name: Name of field to skip (e.g., 'from_street2')
        field_value: Value to set (None for skip, or generated value)
        next_step_const: Next state constant value (e.g., FROM_CITY constant)
        next_step_name: Next state name for logging (e.g., "FROM_CITY")
        next_message: Message text for next step
    
    Returns:
        Next state constant
    """
    from server import session_manager
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Save field value
    user_id = update.effective_user.id
    context.user_data[field_name] = field_value
    
    # Update session atomically
    await session_manager.update_session_atomic(
        user_id, 
        step=next_step_name, 
        data={field_name: field_value}
    )
    
    if field_value:
        logger.info(f"User {user_id}: {field_name} = {field_value}")
    else:
        logger.info(f"User {user_id}: Skipped {field_name}")
    
    # Show next step
    reply_markup = get_cancel_keyboard()
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
        next_message,
        reply_markup=reply_markup
    ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = next_message
        context.user_data['last_state'] = next_step_name
    
    # Return next state constant
    return next_step_const


@with_typing_indicator
async def skip_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip FROM address line 2"""
    from server import FROM_CITY
    
    return await handle_skip_field(
        update, context,
        field_name='from_street2',
        field_value=None,
        next_step='FROM_CITY',
        next_message=OrderStepMessages.FROM_CITY
    )


@with_typing_indicator
async def skip_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip TO address line 2"""
    from server import TO_CITY
    
    return await handle_skip_field(
        update, context,
        field_name='to_street2',
        field_value=None,
        next_step='TO_CITY',
        next_message=OrderStepMessages.TO_CITY
    )


@with_typing_indicator
async def skip_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip FROM phone - generates random US phone number"""
    from server import TO_NAME, generate_random_phone
    
    # Generate random phone
    random_phone = generate_random_phone()
    
    return await handle_skip_field(
        update, context,
        field_name='from_phone',
        field_value=random_phone,
        next_step='TO_NAME',
        next_message=OrderStepMessages.TO_NAME
    )


@with_typing_indicator
async def skip_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip TO phone - generates random US phone number"""
    from server import PARCEL_WEIGHT, generate_random_phone
    
    # Generate random phone
    random_phone = generate_random_phone()
    
    return await handle_skip_field(
        update, context,
        field_name='to_phone',
        field_value=random_phone,
        next_step='PARCEL_WEIGHT',
        next_message=OrderStepMessages.PARCEL_WEIGHT
    )
