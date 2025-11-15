"""
Order Flow: Carrier Selection Handlers
Handles carrier selection and rate refresh
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.common_handlers import safe_telegram_call
from utils.handler_decorators import with_user_session

logger = logging.getLogger(__name__)


@with_user_session(create_user=False, require_session=True)
async def select_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle carrier selection, refresh rates, and cancel actions
    
    Handles:
    - select_carrier_<rate_id>: Select a specific carrier/rate
    - refresh_rates: Refresh shipping rates
    - cancel_order: Cancel order
    - return_to_order: Return to order
    - confirm_cancel: Confirm cancellation
    - check_data: Go back to data confirmation
    """
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"🚚 Carrier action: {data}")
    
    # Handle refresh rates
    if data == 'refresh_rates':
        from handlers.order_flow.rates import fetch_shipping_rates
        logger.info("🔄 Refreshing shipping rates...")
        
        # Clear cached rates to force fresh API call
        if 'rates' in context.user_data:
            del context.user_data['rates']
        if 'rates_cache_key' in context.user_data:
            del context.user_data['rates_cache_key']
        
        # Remove old message with buttons
        try:
            await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
        except Exception as e:
            logger.warning(f"Could not remove old buttons: {e}")
        
        # Add confirmation emoji
        await query.answer("✅ Обновление тарифов...")
        
        return await fetch_shipping_rates(update, context)
    
    # Handle cancel order
    if data == 'cancel_order':
        from handlers.order_flow.cancellation import cancel_order
        return await cancel_order(update, context)
    
    # Handle return to order
    if data == 'return_to_order':
        from handlers.order_flow.cancellation import return_to_order
        return await return_to_order(update, context)
    
    # Handle confirm cancel
    if data == 'confirm_cancel':
        from handlers.order_flow.cancellation import confirm_cancel_order
        return await confirm_cancel_order(update, context)
    
    # Handle check data (go back to confirmation)
    if data == 'check_data':
        from handlers.order_flow.confirmation import show_data_confirmation
        return await show_data_confirmation(update, context)
    
    # Handle carrier selection
    if data.startswith('select_carrier_'):
        rate_id = data.replace('select_carrier_', '')
        logger.info(f"✅ User selected carrier with rate_id: {rate_id}")
        
        # Find selected rate in user_data
        rates = context.user_data.get('rates', [])
        selected_rate = None
        
        for rate in rates:
            if rate.get('rate_id') == rate_id:
                selected_rate = rate
                break
        
        if not selected_rate:
            await safe_telegram_call(query.message.reply_text(
                "❌ Выбранный тариф не найден. Попробуйте обновить список тарифов.",
            ))
            from server import SELECT_CARRIER
            return SELECT_CARRIER
        
        # Save selected rate
        context.user_data['selected_rate'] = selected_rate
        context.user_data['selected_carrier'] = selected_rate.get('carrier_friendly_name', 'Unknown')
        context.user_data['selected_service'] = selected_rate.get('service_type', 'Standard')
        
        # Get base shipping cost from API
        base_cost = selected_rate.get('shipping_amount', {}).get('amount', 0.0)
        
        # Add $10 markup (hidden from user)
        LABEL_MARKUP = 10.0
        final_cost = base_cost + LABEL_MARKUP
        
        context.user_data['shipping_cost'] = base_cost  # Original cost
        context.user_data['final_amount'] = final_cost  # Cost with markup for billing
        
        logger.info(f"✅ Selected: {context.user_data['selected_carrier']} - {context.user_data['selected_service']}")
        logger.info(f"💰 Cost: Base=${base_cost:.2f}, Markup=${LABEL_MARKUP:.2f}, Final=${final_cost:.2f}")
        
        # Remove old message with buttons
        try:
            await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
            # Add checkmark to selected rate
            await query.answer("✅ Тариф выбран!")
        except Exception as e:
            logger.warning(f"Could not update message: {e}")
        
        # Proceed to payment
        from handlers.order_flow.payment import show_payment_methods
        return await show_payment_methods(update, context)
    
    # Unknown action
    logger.warning(f"⚠️ Unknown carrier action: {data}")
    from server import SELECT_CARRIER
    return SELECT_CARRIER
