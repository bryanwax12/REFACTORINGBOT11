"""
Order Flow: Shipping Rates Handlers
Handles fetching and displaying shipping rates
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.common_handlers import safe_telegram_call

logger = logging.getLogger(__name__)

async def fetch_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch shipping rates from ShipStation with caching"""
    query = update.callback_query
    
    # Import cache
    from services.shipstation_cache import shipstation_cache
    
    data = context.user_data
    
    # Check cache first (before showing progress message)
    cached_rates = shipstation_cache.get(
        from_zip=data['from_zip'],
        to_zip=data['to_zip'],
        weight=data['weight'],
        length=data.get('length', 10),
        width=data.get('width', 10),
        height=data.get('height', 10)
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
        return await display_shipping_rates(update, context, cached_rates)
    
    # Cache MISS - need to fetch from API
    # Send initial progress message
    from utils.ui_utils import ShippingRatesUI
    progress_msg = await safe_telegram_call(query.message.reply_text(ShippingRatesUI.progress_message(0)))
    
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
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'Missing required fields: {", ".join(missing_fields)}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            from utils.ui_utils import get_edit_data_keyboard
            reply_markup = get_edit_data_keyboard()
            await safe_telegram_call(query.message.reply_text(
                f"❌ Отсутствуют обязательные данные: {', '.join(missing_fields)}\n\nПожалуйста, заполните все поля.",
                reply_markup=reply_markup
            ))
            return CONFIRM_DATA
        
        # Get carrier IDs
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        carrier_ids = await get_shipstation_carrier_ids()
        if not carrier_ids:
            from utils.ui_utils import get_edit_addresses_keyboard
            reply_markup = get_edit_addresses_keyboard()
            await safe_telegram_call(query.message.reply_text(
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
        rate_request = build_shipstation_rates_request(data, carrier_ids)
        
        # Log the request for debugging
        logger.info(f"ShipStation rate request: {rate_request}")
        
        # Get rates from ShipStation with progress updates
        async def update_progress():
            """Update progress message every 5 seconds"""
            start_time = datetime.now(timezone.utc)
            while True:
                await asyncio.sleep(5)
                elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds())
                try:
                    await safe_telegram_call(progress_msg.edit_text(
                        ShippingRatesUI.progress_message(elapsed)
                    ))
                except Exception:
                    break  # Stop if message was deleted or can't be edited
        
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
            except Exception:
                pass
            
            from utils.ui_utils import get_retry_edit_cancel_keyboard
            reply_markup = get_retry_edit_cancel_keyboard()
            
            await safe_telegram_call(query.message.reply_text(
                f"❌ {error_msg}\n\nПопробуйте еще раз или проверьте правильность адресов.",
                reply_markup=reply_markup
            ))
            return CONFIRM_DATA
        
        if not success:
            # Handle other API errors
            logger.error(f"ShipStation rate request failed: {error_msg}")
            
            # Log error to session
            user_id = update.effective_user.id
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'ShipStation API error: {error_msg}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Delete progress message
            try:
                await safe_telegram_call(progress_msg.delete())
            except Exception:
                pass
            
            from utils.ui_utils import get_edit_addresses_keyboard, ShippingRatesUI
            reply_markup = get_edit_addresses_keyboard()
            
            await safe_telegram_call(query.message.reply_text(
                ShippingRatesUI.api_error_message(error_msg),
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
            except Exception:
                pass
            
            from utils.ui_utils import get_edit_addresses_keyboard, ShippingRatesUI
            reply_markup = get_edit_addresses_keyboard()
            
            await safe_telegram_call(query.message.reply_text(
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
        
        # Save to cache and session using service
        from services.shipping_service import save_rates_to_cache_and_session
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
        except Exception:
            pass
        
        # Display rates using reusable function
        return await display_shipping_rates(update, context, context.user_data['rates'])
        
    except Exception as e:
        logger.error(f"Error getting rates: {e}", exc_info=True)
        
        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Notify admin about rate fetch error
        telegram_id = query.from_user.id
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        if user:
            await notify_admin_error(
                user_info=user,
                error_type="Rate Fetch Failed",
                error_details=f"Exception: {str(e)}\n\nAddresses:\nFrom: {data.get('from_city')}, {data.get('from_state')}\nTo: {data.get('to_city')}, {data.get('to_state')}"
            )
        
        await safe_telegram_call(query.message.reply_text(
            f"❌ Ошибка при получении тарифов:\n{str(e)}\n\nПроверьте корректность адресов и попробуйте снова.",
            reply_markup=reply_markup
        ))
        return CONFIRM_DATA  # Stay to handle callback

