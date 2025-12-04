"""
Order Flow: Skip Handlers
Handles skip actions for optional fields with proper UI and state management
"""
import asyncio
import logging
from telegram import Update, ForceReply
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Import shared utilities
from handlers.common_handlers import safe_telegram_call, mark_message_as_selected
from utils.ui_utils import get_cancel_keyboard, OrderStepMessages
from utils.handler_decorators import with_user_session, safe_handler
from telegram.ext import ConversationHandler


@safe_handler(fallback_state=ConversationHandler.END)
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
    # ✅ 2025 FIX: Get OLD prompt text BEFORE updating context

    old_prompt_text = context.user_data.get('last_bot_message_text', '')

    asyncio.create_task(safe_background_task(mark_message_as_selected(update, context, prompt_text=old_prompt_text)))
    
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
    
    # Show next step (no cancel button)
    # Save state IMMEDIATELY (before background task)
    context.user_data['last_bot_message_text'] = next_message
    
    # Send message without ForceReply
    bot_msg = await safe_telegram_call(update.effective_message.reply_text(next_message))
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    
    # Return next state constant
    return next_step_const


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip FROM address line 2"""
    from server import FROM_CITY
    from utils.ui_utils import TemplateEditMessages
    
    # Check if editing - use different message
    editing = context.user_data.get('editing_template_from') or context.user_data.get('editing_from_address')
    next_message = TemplateEditMessages.FROM_CITY if editing else OrderStepMessages.FROM_CITY
    
    return await handle_skip_field(
        update, context,
        field_name='from_address2',
        field_value=None,
        next_step_const=FROM_CITY,
        next_step_name='FROM_CITY',
        next_message=next_message
    )


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip TO address line 2"""
    from server import TO_CITY
    from utils.ui_utils import TemplateEditMessages
    
    # Check if editing - use different message
    editing = context.user_data.get('editing_template_to') or context.user_data.get('editing_to_address')
    next_message = TemplateEditMessages.TO_CITY if editing else OrderStepMessages.TO_CITY
    
    return await handle_skip_field(
        update, context,
        field_name='to_address2',
        field_value=None,
        next_step_const=TO_CITY,
        next_step_name='TO_CITY',
        next_message=next_message
    )


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip FROM phone - generates random US phone number"""
    from server import TO_NAME, generate_random_phone, db
    from telegram.ext import ConversationHandler
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import logging
    logger = logging.getLogger(__name__)
    
    # Generate random phone
    random_phone = generate_random_phone()
    context.user_data['from_phone'] = random_phone
    
    # CRITICAL: Check if we're editing template FROM address OR editing order FROM address
    user_id = update.effective_user.id
    session = await db.user_sessions.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0, "editing_template_from": 1, "editing_template_id": 1}
    )
    
    editing_template_from_db = session.get('editing_template_from', False) if session else False
    editing_template_id_db = session.get('editing_template_id') if session else None
    editing_from_address = context.user_data.get('editing_from_address', False)
    
    logger.info(f"⏭️ SKIP FROM PHONE: editing_template_from={editing_template_from_db}, template_id={editing_template_id_db}, editing_from_address={editing_from_address}")
    
    if editing_template_from_db and editing_template_id_db:
        logger.info(f"✅ Template FROM address edit complete (via skip), saving to template_id={editing_template_id_db}")
        
        # Update template in DB
        await db.templates.update_one(
            {"id": editing_template_id_db},
            {"$set": {
                "from_name": context.user_data.get('from_name', ''),
                "from_street1": context.user_data.get('from_address', ''),
                "from_street2": context.user_data.get('from_address2', ''),
                "from_city": context.user_data.get('from_city', ''),
                "from_state": context.user_data.get('from_state', ''),
                "from_zip": context.user_data.get('from_zip', ''),
                "from_phone": random_phone
            }}
        )
        
        # Clear flags from DB session
        await db.user_sessions.update_one(
            {"user_id": user_id, "is_active": True},
            {"$unset": {
                "editing_template_from": "",
                "editing_template_id": ""
            }}
        )
        
        # Show success message
        keyboard = [
            [InlineKeyboardButton("👁️ Просмотреть шаблон", callback_data=f'template_view_{editing_template_id_db}')],
            [InlineKeyboardButton("📋 К списку шаблонов", callback_data='my_templates')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        asyncio.create_task(query.answer())  # 🚀 Non-blocking
        
        # 🚀 PERFORMANCE: Send message in background
        asyncio.create_task(update.effective_message.reply_text(
            "✅ Адрес отправителя в шаблоне обновлён!",
            reply_markup=reply_markup
        ))
        
        return ConversationHandler.END
    
    # Check if we're editing FROM address in order creation flow
    if editing_from_address:
        logger.info("✅ Order FROM address edit complete (via skip), returning to confirmation")
        
        # Clear editing flag
        context.user_data.pop('editing_from_address', None)
        
        # Return to confirmation screen
        from handlers.order_flow.confirmation import show_data_confirmation
        query = update.callback_query
        asyncio.create_task(query.answer())  # 🚀 Non-blocking
        return await show_data_confirmation(update, context)
    
    # Normal flow
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
    from server import PARCEL_WEIGHT, generate_random_phone, db
    from telegram.ext import ConversationHandler
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import logging
    logger = logging.getLogger(__name__)
    
    # Generate random phone
    random_phone = generate_random_phone()
    context.user_data['to_phone'] = random_phone
    
    # CRITICAL: Check if we're editing template TO address OR editing order TO address
    user_id = update.effective_user.id
    session = await db.user_sessions.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0, "editing_template_to": 1, "editing_template_id": 1}
    )
    
    editing_template_to_db = session.get('editing_template_to', False) if session else False
    editing_template_id_db = session.get('editing_template_id') if session else None
    editing_to_address = context.user_data.get('editing_to_address', False)
    
    logger.info(f"⏭️ SKIP TO PHONE: editing_template_to={editing_template_to_db}, template_id={editing_template_id_db}, editing_to_address={editing_to_address}")
    
    if editing_template_to_db and editing_template_id_db:
        logger.info(f"✅ Template TO address edit complete (via skip), saving to template_id={editing_template_id_db}")
        
        # Update template in DB
        await db.templates.update_one(
            {"id": editing_template_id_db},
            {"$set": {
                "to_name": context.user_data.get('to_name', ''),
                "to_street1": context.user_data.get('to_address', ''),
                "to_street2": context.user_data.get('to_address2', ''),
                "to_city": context.user_data.get('to_city', ''),
                "to_state": context.user_data.get('to_state', ''),
                "to_zip": context.user_data.get('to_zip', ''),
                "to_phone": random_phone
            }}
        )
        
        # Clear flags from DB session
        await db.user_sessions.update_one(
            {"user_id": user_id, "is_active": True},
            {"$unset": {
                "editing_template_to": "",
                "editing_template_id": ""
            }}
        )
        
        # Show success message
        keyboard = [
            [InlineKeyboardButton("👁️ Просмотреть шаблон", callback_data=f'template_view_{editing_template_id_db}')],
            [InlineKeyboardButton("📋 К списку шаблонов", callback_data='my_templates')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query = update.callback_query
        asyncio.create_task(query.answer())  # 🚀 Non-blocking
        
        # 🚀 PERFORMANCE: Send message in background
        asyncio.create_task(update.effective_message.reply_text(
            "✅ Адрес получателя в шаблоне обновлён!",
            reply_markup=reply_markup
        ))
        
        return ConversationHandler.END
    
    # Check if we're editing TO address in order creation flow
    if editing_to_address:
        logger.info("✅ Order TO address edit complete (via skip), returning to confirmation")
        
        # Clear editing flag
        context.user_data.pop('editing_to_address', None)
        
        # Return to confirmation screen
        from handlers.order_flow.confirmation import show_data_confirmation
        query = update.callback_query
        asyncio.create_task(query.answer())  # 🚀 Non-blocking
        return await show_data_confirmation(update, context)
    
    # Normal flow
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
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Edit message to remove buttons and show confirmation
    await safe_telegram_call(query.message.edit_text(
        "✅ Используются стандартные размеры: 10x10x10 дюймов",
        reply_markup=None  # Remove keyboard
    ))
    
    # Set standard dimensions
    user_id = update.effective_user.id
    context.user_data['parcel_length'] = 10.0
    context.user_data['parcel_width'] = 10.0
    context.user_data['parcel_height'] = 10.0
    
    # Load session data to ensure we have all order data (weight, addresses, etc)
    from server import session_manager, db
    import logging
    logger = logging.getLogger(__name__)
    
    # Try to get session first
    session = await session_manager.get_session(user_id)
    if session and session.get('session_data'):
        session_data = session['session_data']
        logger.info(f"Session data keys: {list(session_data.keys())}")
        
        for key, value in session_data.items():
            if key not in context.user_data:
                context.user_data[key] = value
    else:
        # If no session, try to get data directly from DB (last order draft)
        logger.warning("No session found, trying to load from orders collection")
        order_draft = await db.orders.find_one(
            {"telegram_id": user_id, "payment_status": {"$in": ["pending", "draft"]}},
            {"_id": 0},
            sort=[("created_at", -1)]
        )
        if order_draft:
            logger.info(f"Found order draft with keys: {list(order_draft.keys())}")
            for key, value in order_draft.items():
                if key not in context.user_data and value is not None:
                    context.user_data[key] = value
    
    # Map parcel_weight to weight for fetch_shipping_rates
    if 'parcel_weight' in context.user_data and 'weight' not in context.user_data:
        context.user_data['weight'] = context.user_data['parcel_weight']
        logger.info(f"Mapped parcel_weight to weight: {context.user_data['weight']}")
    
    # Map parcel dimensions to short names
    if 'parcel_length' in context.user_data and 'length' not in context.user_data:
        context.user_data['length'] = context.user_data['parcel_length']
    if 'parcel_width' in context.user_data and 'width' not in context.user_data:
        context.user_data['width'] = context.user_data['parcel_width']
    if 'parcel_height' in context.user_data and 'height' not in context.user_data:
        context.user_data['height'] = context.user_data['parcel_height']
    
    logger.info(f"Context.user_data has 'weight': {'weight' in context.user_data}, value: {context.user_data.get('weight', 'MISSING')}")
    
    # Update session with dimensions
    await session_manager.update_session_atomic(
        user_id,
        step='CONFIRM_DATA',
        data={
            'parcel_length': 10.0,
            'parcel_width': 10.0,
            'parcel_height': 10.0
        }
    )
    
    # Show data confirmation screen before fetching rates
    from handlers.order_flow.confirmation import show_data_confirmation
    return await show_data_confirmation(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_parcel_width_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip width and height - use standard 10x10 inches"""
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Edit message to remove buttons and show confirmation
    await safe_telegram_call(query.message.edit_text(
        "✅ Используются стандартные размеры для ширины и высоты: 10x10 дюймов",
        reply_markup=None  # Remove keyboard
    ))
    
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
        
        # Map parcel_weight to weight for fetch_shipping_rates
        if 'parcel_weight' in context.user_data and 'weight' not in context.user_data:
            context.user_data['weight'] = context.user_data['parcel_weight']
        
        # Map parcel dimensions to short names
        if 'parcel_length' in context.user_data and 'length' not in context.user_data:
            context.user_data['length'] = context.user_data['parcel_length']
        if 'parcel_width' in context.user_data and 'width' not in context.user_data:
            context.user_data['width'] = context.user_data['parcel_width']
        if 'parcel_height' in context.user_data and 'height' not in context.user_data:
            context.user_data['height'] = context.user_data['parcel_height']
    
    # Update session with dimensions
    await session_manager.update_session_atomic(
        user_id,
        step='CONFIRM_DATA',
        data={
            'parcel_width': 10.0,
            'parcel_height': 10.0
        }
    )
    
    # Show data confirmation screen before fetching rates
    from handlers.order_flow.confirmation import show_data_confirmation
    return await show_data_confirmation(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
@with_user_session(create_user=False, require_session=True)
async def skip_parcel_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip height only - use standard 10 inches"""
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Edit message to remove buttons and show confirmation
    await safe_telegram_call(query.message.edit_text(
        "✅ Используется стандартная высота: 10 дюймов",
        reply_markup=None  # Remove keyboard
    ))
    
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
        
        # Map parcel_weight to weight for fetch_shipping_rates
        if 'parcel_weight' in context.user_data and 'weight' not in context.user_data:
            context.user_data['weight'] = context.user_data['parcel_weight']
        
        # Map parcel dimensions to short names
        if 'parcel_length' in context.user_data and 'length' not in context.user_data:
            context.user_data['length'] = context.user_data['parcel_length']
        if 'parcel_width' in context.user_data and 'width' not in context.user_data:
            context.user_data['width'] = context.user_data['parcel_width']
        if 'parcel_height' in context.user_data and 'height' not in context.user_data:
            context.user_data['height'] = context.user_data['parcel_height']
    
    # Update session with height
    await session_manager.update_session_atomic(
        user_id,
        step='CONFIRM_DATA',
        data={'parcel_height': 10.0}
    )
    
    # Show data confirmation screen before fetching rates
    from handlers.order_flow.confirmation import show_data_confirmation
    return await show_data_confirmation(update, context)


@safe_handler(fallback_state=ConversationHandler.END)
async def skip_address_validation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip address validation and continue with rate fetching"""
    from handlers.common_handlers import safe_telegram_call
    from server import fetch_shipping_rates
    
    query = update.callback_query
    asyncio.create_task(safe_telegram_call(query.answer()))
    
    # Set flag to skip validation
    context.user_data['skip_address_validation'] = True
    
    # 🚀 PERFORMANCE: Show message in background - don't block state return
    asyncio.create_task(safe_telegram_call(update.effective_message.reply_text("⚠️ Пропускаю валидацию адреса...\n⏳ Получаю доступные курьерские службы и тарифы...")))
    
    # Call fetch_shipping_rates which will now skip validation
    return await fetch_shipping_rates(update, context)

