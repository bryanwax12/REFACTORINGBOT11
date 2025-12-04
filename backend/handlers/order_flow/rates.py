"""
Order Flow: Shipping Rates Handlers
Handles fetching and displaying shipping rates
"""
import logging
import os
import time
from datetime import datetime, timezone
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram.error
import httpx

from handlers.common_handlers import safe_telegram_call
from handlers.admin_handlers import notify_admin_error
from services.api_services import get_shipstation_carrier_ids
from services.shipping_service import display_shipping_rates
from utils.session_utils import save_to_session

logger = logging.getLogger(__name__)

# Import state constants
from server import CONFIRM_DATA

# Get ShipStation API key from environment
SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY_TEST') or os.environ.get('SHIPSTATION_API_KEY_PROD')  # ⚠️ TEST MODE ENABLED

async def fetch_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch shipping rates from ShipStation with caching"""
    logger.info("🚀 fetch_shipping_rates called")
    
    # Handle both callback queries and direct message calls
    query = update.callback_query
    message = update.effective_message
    
    # Import cache
    from services.shipstation_cache import shipstation_cache
    
    data = context.user_data
    logger.info(f"📋 User data keys: {list(data.keys())}")
    
    # Check cache first (before showing progress message)
    cached_rates = shipstation_cache.get(
        from_zip=data['from_zip'],
        to_zip=data['to_zip'],
        weight=data['parcel_weight'],
        length=data.get('parcel_length', 10),
        width=data.get('parcel_width', 10),
        height=data.get('parcel_height', 10)
    )
    
    if cached_rates:
        # Cache HIT - используем закэшированные тарифы
        logger.info(f"✅ Using cached rates for {data['from_zip']} → {data['to_zip']}")
        
        # Immediately show rates (no API call needed)
        from utils.ui_utils import ShippingRatesUI
        await safe_telegram_call(query.answer(ShippingRatesUI.cache_hit_message()))
        
        # Prepare rate data
        context.user_data['rates'] = cached_rates
        
        # Save to session
        user_id = update.effective_user.id
        await save_to_session(user_id, "CARRIER_SELECTION", {
            'rates': cached_rates,
            'cached': True,
            'cache_timestamp': datetime.now(timezone.utc).isoformat()
        }, context)
        
        # Display rates (reuse display logic)
        from repositories import get_user_repo
        from server import STATE_NAMES, SELECT_CARRIER
        
        user_repo = get_user_repo()
        return await display_shipping_rates(
            update, 
            context, 
            cached_rates,
            find_user_by_telegram_id_func=user_repo.find_by_telegram_id,
            safe_telegram_call_func=safe_telegram_call,
            STATE_NAMES=STATE_NAMES,
            SELECT_CARRIER=SELECT_CARRIER
        )
    
    # Cache MISS - need to fetch from API
    # Send initial progress message
    from utils.ui_utils import ShippingRatesUI
    progress_msg = await safe_telegram_call(message.reply_text(ShippingRatesUI.progress_message(0)))
    
    try:
        import asyncio
        
        # Validate order data using service
        from services.shipping_service import validate_order_data_for_rates
        is_valid, missing_fields = await validate_order_data_for_rates(data)
        
        if not is_valid:
            logger.error(f"Missing or invalid required fields: {missing_fields}")
            logger.error(f"Current user_data: {data}")
            
            # Log error to session for debugging
            user_id = update.effective_user.id
            from server import session_manager
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'Missing required fields: {", ".join(missing_fields)}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            from utils.ui_utils import get_edit_data_keyboard
            reply_markup = get_edit_data_keyboard()
            await safe_telegram_call(message.reply_text(
                f"❌ Отсутствуют обязательные данные: {', '.join(missing_fields)}\n\nПожалуйста, заполните все поля.",
                reply_markup=reply_markup
            ))
            return CONFIRM_DATA
        
        # Get carrier IDs
        logger.info("📦 About to fetch carrier IDs from ShipStation...")
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        carrier_ids = await get_shipstation_carrier_ids()
        logger.info(f"📦 Received carrier IDs: {len(carrier_ids) if carrier_ids else 0}")
        logger.info(f"📦 Carrier IDs dict: {carrier_ids}")
        if not carrier_ids:
            from utils.ui_utils import get_edit_addresses_keyboard
            reply_markup = get_edit_addresses_keyboard()
            await safe_telegram_call(message.reply_text(
            "❌ Ошибка: не удалось загрузить список курьеров.\n\nПожалуйста, попробуйте позже.",
            reply_markup=reply_markup,
        ))
            return CONFIRM_DATA
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Build rate request using service
        from services.shipping_service import build_shipstation_rates_request
        # Convert carrier_ids dict to list of IDs
        carrier_ids_list = list(carrier_ids.values())
        logger.info(f"📦 Carrier IDs list for API: {carrier_ids_list}")
        rate_request = build_shipstation_rates_request(data, carrier_ids_list)
        
        # Log the request for debugging
        logger.info(f"ShipStation rate request: {rate_request}")
        
        # Get rates from ShipStation with progress updates
        async def update_progress():
            """Update progress with increasing intervals to reduce API calls"""
            start_time = datetime.now(timezone.utc)
            # Progressive intervals: 1, 2, 3, 5, 10 seconds
            intervals = [1, 2, 3, 5, 10, 15, 20, 30]
            for interval in intervals:
                await asyncio.sleep(interval)
                elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds())
                try:
                    await safe_telegram_call(progress_msg.edit_text(
                        ShippingRatesUI.progress_message(elapsed)
                    ))
                except telegram.error.BadRequest:
                    break  # Message was deleted or can't be edited
        
        # Start progress update task
        progress_task = asyncio.create_task(update_progress())
        
        # Fetch rates from ShipStation using service
        from services.shipping_service import fetch_rates_from_shipstation
        
        api_start_time = time.perf_counter()
        success, all_rates, error_msg = await fetch_rates_from_shipstation(
            rate_request=rate_request,
            headers=headers,
            api_url='https://api.shipstation.com/v2/rates',
            timeout=30
        )
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        logger.info(f"⚡ ShipStation /rates API took {api_duration_ms:.2f}ms")
        
        if not success and "timeout" in error_msg.lower():
            # Handle timeout error
            logger.error(f"ShipStation rate request failed: {error_msg}")
            
            # Log error to session
            user_id = update.effective_user.id
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'ShipStation API error: {error_msg}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Stop progress task
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            # Delete progress message
            try:
                await safe_telegram_call(progress_msg.delete())
            except telegram.error.BadRequest:
                pass  # Already deleted
            
            from utils.ui_utils import get_retry_edit_cancel_keyboard
            reply_markup = get_retry_edit_cancel_keyboard()
            
            await safe_telegram_call(message.reply_text(
                "❌ Превышено время ожидания ответа от сервиса доставки.\n\nПопробуйте еще раз или проверьте правильность адресов.",
                reply_markup=reply_markup
            ))
            return CONFIRM_DATA
        
        if not success:
            # Handle other API errors
            logger.error(f"ShipStation rate request failed: {error_msg}")
            
            # Log error to session
            from server import session_manager
            user_id = update.effective_user.id
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'ShipStation API error: {error_msg}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Delete progress message
            try:
                await safe_telegram_call(progress_msg.delete())
            except telegram.error.BadRequest:
                pass  # Already deleted
            
            from utils.ui_utils import get_edit_addresses_keyboard, ShippingRatesUI
            reply_markup = get_edit_addresses_keyboard()
            
            # Parse error message for user-friendly display
            user_message = "❌ Не удалось получить тарифы доставки.\n\n"
            
            # Check for common validation errors
            if "state_province" in error_msg.lower():
                user_message += "⚠️ Штат должен быть указан 2-буквенным кодом (например: CA, NY, TX)\n\n"
            if "postal_code" in error_msg.lower():
                user_message += "⚠️ Почтовый индекс должен быть в правильном формате (например: 90001)\n\n"
            if "address" in error_msg.lower() and "invalid" in error_msg.lower():
                user_message += "⚠️ Проверьте правильность адреса\n\n"
            
            user_message += "Пожалуйста, проверьте корректность всех данных и попробуйте снова."
            
            await safe_telegram_call(message.reply_text(
                user_message,
                reply_markup=reply_markup,
            ))
            
            # Stop progress task
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            return CONFIRM_DATA
        
        # Stop progress updates on success
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass
        
        # Log all rates received from API for debugging
        logger.info(f"📦 Received {len(all_rates)} rates from ShipStation API")
        for idx, rate in enumerate(all_rates[:10]):  # Log first 10
            carrier = rate.get('carrier_friendly_name', rate.get('carrier', 'Unknown'))
            service = rate.get('service_type', rate.get('service', 'Unknown'))
            logger.info(f"   Rate {idx+1}: {carrier} - {service}")
        
        # Filter and format rates using service
        
        # First apply basic exclusion
        excluded_carriers = ['globalpost']
        filtered_rates = [
            rate for rate in all_rates
            if rate.get('carrier_code', '').lower() not in excluded_carriers
        ]
        all_rates = filtered_rates
        
        # Apply service filter using service
        from services.shipping_service import apply_service_filter
        all_rates = apply_service_filter(all_rates)
        
        if not all_rates or len(all_rates) == 0:
            # Delete progress message
            try:
                await safe_telegram_call(progress_msg.delete())
            except telegram.error.BadRequest:
                pass  # Already deleted
            
            from utils.ui_utils import get_edit_addresses_keyboard, ShippingRatesUI
            reply_markup = get_edit_addresses_keyboard()
            
            await safe_telegram_call(message.reply_text(
            ShippingRatesUI.no_rates_found(),
            reply_markup=reply_markup,
        ))
            return CONFIRM_DATA  # Stay to handle callback
        
        # Log carriers
        carriers = set([r.get('carrier_friendly_name', 'Unknown') for r in all_rates])
        logger.info(f"Got {len(all_rates)} rates from carriers: {carriers}")
        
        # Balance and deduplicate rates using service
        from services.shipping_service import balance_and_deduplicate_rates
        context.user_data['rates'] = balance_and_deduplicate_rates(all_rates, max_per_carrier=5)[:15]
        
        # Add $10 markup to all rates (hidden from user - shown as part of shipping cost)
        LABEL_MARKUP = 10.0
        for rate in context.user_data['rates']:
            # Get original amount from shipping_amount dict or amount field
            if 'shipping_amount' in rate and isinstance(rate['shipping_amount'], dict):
                original_amount = rate['shipping_amount'].get('amount', 0.0)
            elif 'amount' in rate:
                original_amount = rate['amount']
            else:
                original_amount = 0.0
            
            # Store original amount for reference
            rate['original_amount'] = original_amount
            
            # Add markup to displayed amount
            if 'shipping_amount' in rate and isinstance(rate['shipping_amount'], dict):
                rate['shipping_amount']['amount'] = original_amount + LABEL_MARKUP
            elif 'amount' in rate:
                rate['amount'] = original_amount + LABEL_MARKUP
            else:
                # Create shipping_amount structure if it doesn't exist
                rate['shipping_amount'] = {'amount': original_amount + LABEL_MARKUP}
                rate['amount'] = original_amount + LABEL_MARKUP
        
        logger.info(f"💰 Added ${LABEL_MARKUP} markup to {len(context.user_data['rates'])} rates")
        
        # Save to cache and session using service
        from services.shipping_service import save_rates_to_cache_and_session
        from server import session_manager
        
        user_id = update.effective_user.id
        await save_rates_to_cache_and_session(
            rates=context.user_data['rates'],
            order_data=data,
            user_id=user_id,
            context=context,
            shipstation_cache=shipstation_cache,
            session_manager=session_manager
        )
        
        # Delete progress message
        try:
            await safe_telegram_call(progress_msg.delete())
        except telegram.error.BadRequest:
            pass  # Already deleted
        
        # Display rates using reusable function
        from repositories import get_user_repo
        from server import STATE_NAMES, SELECT_CARRIER
        
        user_repo = get_user_repo()
        return await display_shipping_rates(
            update, 
            context, 
            context.user_data['rates'],
            find_user_by_telegram_id_func=user_repo.find_by_telegram_id,
            safe_telegram_call_func=safe_telegram_call,
            STATE_NAMES=STATE_NAMES,
            SELECT_CARRIER=SELECT_CARRIER
        )
        
    except Exception as e:
        logger.error(f"Error getting rates: {e}", exc_info=True)
        
        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Notify admin about rate fetch error
        telegram_id = update.effective_user.id if update.effective_user else None
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id) if telegram_id else None
        if user:
            await notify_admin_error(
                user_info=user,
                error_type="Rate Fetch Failed",
                error_details=f"Exception: {str(e)}\n\nAddresses:\nFrom: {data.get('from_city')}, {data.get('from_state')}\nTo: {data.get('to_city')}, {data.get('to_state')}"
            )
        
        await safe_telegram_call(message.reply_text(
            "❌ Произошла ошибка при получении тарифов.\n\nПроверьте корректность адресов и попробуйте снова, или обратитесь в поддержку.",
            reply_markup=reply_markup
        ))
        return CONFIRM_DATA  # Stay to handle callback

