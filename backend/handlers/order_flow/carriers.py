"""
Order Flow: Carrier Selection Handlers
Handles carrier selection and rate refresh
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.common_handlers import safe_telegram_call
from utils.handler_decorators import with_user_session, safe_handler

logger = logging.getLogger(__name__)


@safe_handler(fallback_message="❌ Произошла ошибка при обработке выбора курьера.")
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
        context.user_data['shipping_cost'] = selected_rate.get('shipping_amount', {}).get('amount', 0.0)
        
        logger.info(f"✅ Selected: {context.user_data['selected_carrier']} - {context.user_data['selected_service']} - ${context.user_data['shipping_cost']}")
        
        # Proceed to payment
        from handlers.order_flow.payment import handle_payment_selection
        return await handle_payment_selection(update, context)
    
    # Unknown action
    logger.warning(f"⚠️ Unknown carrier action: {data}")
    from server import SELECT_CARRIER
    return SELECT_CARRIER
