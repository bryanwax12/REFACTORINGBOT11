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
from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
from utils.handler_decorators import with_user_session, safe_handler
from telegram.ext import ConversationHandler


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
        from server import STATE_NAMES
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = next_message
        context.user_data['last_state'] = STATE_NAMES[next_step_const]
    
    # Return next state constant
    return next_step_const


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip FROM address line 2"""
    from server import FROM_CITY
    
    return await handle_skip_field(
        update, context,
        field_name='from_street2',
        field_value=None,
        next_step_const=FROM_CITY,
        next_step_name='FROM_CITY',
        next_message=OrderStepMessages.FROM_CITY
    )


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip TO address line 2"""
    from server import TO_CITY
    
    return await handle_skip_field(
        update, context,
        field_name='to_street2',
        field_value=None,
        next_step_const=TO_CITY,
        next_step_name='TO_CITY',
        next_message=OrderStepMessages.TO_CITY
    )


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip FROM phone - generates random US phone number"""
    from server import TO_NAME, generate_random_phone
    
    # Generate random phone
    random_phone = generate_random_phone()
    
    return await handle_skip_field(
        update, context,
        field_name='from_phone',
        field_value=random_phone,
        next_step_const=TO_NAME,
        next_step_name='TO_NAME',
        next_message=OrderStepMessages.TO_NAME
    )


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip TO phone - generates random US phone number"""
    from server import PARCEL_WEIGHT, generate_random_phone
    
    # Generate random phone
    random_phone = generate_random_phone()
    
    return await handle_skip_field(
        update, context,
        field_name='to_phone',
        field_value=random_phone,
        next_step_const=PARCEL_WEIGHT,
        next_step_name='PARCEL_WEIGHT',
        next_message=OrderStepMessages.PARCEL_WEIGHT
    )



@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_parcel_dimensions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip all dimensions (L/W/H) - use standard 10x10x10 inches"""
    from handlers.order_flow.rates import fetch_shipping_rates
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    await safe_telegram_call(query.message.reply_text("✅ Используются стандартные размеры: 10x10x10 дюймов"))
    
    # Set standard dimensions
    user_id = update.effective_user.id
    context.user_data['parcel_length'] = 10.0
    context.user_data['parcel_width'] = 10.0
    context.user_data['parcel_height'] = 10.0
    
    # Load session data to ensure we have all order data (weight, addresses, etc)
    from server import session_manager
    session = await session_manager.get_session(user_id)
    if session and session.get('session_data'):
        # Merge session data into context.user_data
        session_data = session['session_data']
        for key, value in session_data.items():
            if key not in context.user_data:
                context.user_data[key] = value
    
    # Update session with dimensions
    await session_manager.update_session_atomic(
        user_id,
        step='CALCULATING_RATES',
        data={
            'parcel_length': 10.0,
            'parcel_width': 10.0,
            'parcel_height': 10.0
        }
    )
    
    # Call fetch_shipping_rates to calculate and show rates
    return await fetch_shipping_rates(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_parcel_width_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip width and height - use standard 10x10 inches"""
    from handlers.order_flow.rates import fetch_shipping_rates
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    await safe_telegram_call(query.message.reply_text("✅ Используются стандартные размеры для ширины и высоты: 10x10 дюймов"))
    
    # Set standard width and height
    user_id = update.effective_user.id
    context.user_data['parcel_width'] = 10.0
    context.user_data['parcel_height'] = 10.0
    
    # Load session data to ensure we have all order data
    from server import session_manager
    session = await session_manager.get_session(user_id)
    if session and session.get('session_data'):
        session_data = session['session_data']
        for key, value in session_data.items():
            if key not in context.user_data:
                context.user_data[key] = value
    
    # Update session with dimensions
    await session_manager.update_session_atomic(
        user_id,
        step='CALCULATING_RATES',
        data={
            'parcel_width': 10.0,
            'parcel_height': 10.0
        }
    )
    
    # Call fetch_shipping_rates to calculate and show rates
    return await fetch_shipping_rates(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_parcel_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip height only - use standard 10 inches"""
    from handlers.order_flow.rates import fetch_shipping_rates
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    await safe_telegram_call(query.message.reply_text("✅ Используется стандартная высота: 10 дюймов"))
    
    # Set standard height
    user_id = update.effective_user.id
    context.user_data['parcel_height'] = 10.0
    
    # Load session data to ensure we have all order data
    from server import session_manager
    session = await session_manager.get_session(user_id)
    if session and session.get('session_data'):
        session_data = session['session_data']
        for key, value in session_data.items():
            if key not in context.user_data:
                context.user_data[key] = value
    
    # Update session with height
    await session_manager.update_session_atomic(
        user_id,
        step='CALCULATING_RATES',
        data={'parcel_height': 10.0}
    )
    
    # Call fetch_shipping_rates to calculate and show rates
    return await fetch_shipping_rates(update, context)


async def skip_address_validation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip address validation and continue with rate fetching"""
    from handlers.common_handlers import safe_telegram_call
    from server import fetch_shipping_rates
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Set flag to skip validation
    context.user_data['skip_address_validation'] = True
    
    await safe_telegram_call(query.message.reply_text("⚠️ Пропускаю валидацию адреса...\n⏳ Получаю доступные курьерские службы и тарифы..."))
    
    # Call fetch_shipping_rates which will now skip validation
    return await fetch_shipping_rates(update, context)

