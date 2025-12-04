"""
Order Flow: Carrier Selection Handlers
Handles carrier selection and rate refresh
"""
import asyncio
import logging
from telegram import Update, ForceReply
from telegram.ext import ContextTypes
from handlers.common_handlers import safe_telegram_call
from utils.handler_decorators import with_user_session

logger = logging.getLogger(__name__)


@with_user_session(create_user=False, require_session=True)
@safe_handler(fallback_state=ConversationHandler.END)
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
    asyncio.create_task(query.answer())  # 🚀 Non-blocking
    
    data = query.data
    logger.info(f"🚚 Carrier action: {data}")
    
    # Handle refresh rates
    if data == 'refresh_rates':
        from handlers.order_flow.rates import fetch_shipping_rates
        from services.shipstation_cache import shipstation_cache
        
        logger.info("🔄 Refreshing shipping rates...")
        
        # Clear cached rates from shipstation_cache to force fresh API call
        user_data = context.user_data
        cache_deleted = shipstation_cache.delete(
            from_zip=user_data.get('from_zip'),
            to_zip=user_data.get('to_zip'),
            weight=user_data.get('parcel_weight'),
            length=user_data.get('parcel_length', 10),
            width=user_data.get('parcel_width', 10),
            height=user_data.get('parcel_height', 10)
        )
        
        if cache_deleted:
            logger.info("✅ Cache cleared successfully")
        else:
            logger.warning("⚠️ No cache entry found to delete")
        
        # Clear context.user_data cached rates
        if 'rates' in context.user_data:
            del context.user_data['rates']
        if 'rates_cache_key' in context.user_data:
            del context.user_data['rates_cache_key']
        
        # Delete old message with rates and buttons
        try:
            await safe_telegram_call(query.message.delete())
            logger.info("🗑️ Deleted old rates message")
        except Exception as e:
            logger.warning(f"Could not delete old message: {e}")
        
        # Answer the callback query
        asyncio.create_task(query.answer())  # 🚀 Non-blocking
        
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
            await safe_telegram_call(update.effective_message.reply_text(
                "❌ Выбранный тариф не найден. Попробуйте обновить список тарифов.",
            ))
            from server import SELECT_CARRIER
            return SELECT_CARRIER
        
        # Save selected rate
        context.user_data['selected_rate'] = selected_rate
        
        # Clean carrier name same as in UI (ui_utils.py)
        carrier_original = selected_rate.get('carrier', selected_rate.get('carrier_friendly_name', 'Unknown'))
        
        # Apply same cleaning logic as in UI
        carrier_clean = carrier_original
        if 'stamps' in carrier_original.lower():
            carrier_clean = 'USPS'
        else:
            for known_carrier in ['USPS', 'UPS', 'FedEx']:
                if known_carrier.lower() in carrier_original.lower():
                    carrier_clean = known_carrier
                    break
        
        context.user_data['selected_carrier'] = carrier_clean
        # Use 'service' field first (from formatted rates), fallback to service_type
        context.user_data['selected_service'] = selected_rate.get('service', selected_rate.get('service_type', 'Standard'))
        
        # Get shipping cost (already includes $10 markup from rates.py)
        # Try shipping_amount dict first, then fallback to amount field
        if 'shipping_amount' in selected_rate and isinstance(selected_rate['shipping_amount'], dict):
            final_cost = selected_rate['shipping_amount'].get('amount', 0.0)
        elif 'amount' in selected_rate:
            final_cost = selected_rate['amount']
        else:
            final_cost = 0.0
            
        original_cost = selected_rate.get('original_amount', final_cost - 10.0)  # Get original (final - markup)
        
        context.user_data['shipping_cost'] = original_cost  # Original cost without markup
        context.user_data['final_amount'] = final_cost  # Cost with markup (what user pays)
        
        logger.info(f"✅ Selected: {context.user_data['selected_carrier']} - {context.user_data['selected_service']}")
        logger.info(f"💰 Cost: Original=${original_cost:.2f}, Final=${final_cost:.2f} (includes $10 markup)")
        logger.info(f"📊 Selected rate structure: {list(selected_rate.keys())}")
        
        # Remove old message with buttons
        try:
            await safe_telegram_call(query.message.edit_reply_markup(reply_markup=None))
            # Add checkmark to selected rate
            await query.answer("✅ Тариф выбран!")
        except Exception as e:
            logger.warning(f"Could not update message: {e}")
        
        # CREATE ORDER with status "pending" (NEW LOGIC)
        from server import create_order_in_db, db
        from repositories import get_user_repo
        
        # Get user
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(query.from_user.id)
        
        if not user:
            await safe_telegram_call(update.effective_message.reply_text("❌ Ошибка: пользователь не найден"))
            from server import SELECT_CARRIER
            return SELECT_CARRIER
        
        # Get discount info
        discount_percent = context.user_data.get('user_discount', 0)
        discount_amount_val = context.user_data.get('discount_amount', 0)
        
        # Check if there's already an order_id in context from previous selection
        existing_order_id = context.user_data.get('order_id')
        
        if existing_order_id:
            # Check if this order exists and is pending
            existing_order = await db.orders.find_one({"order_id": existing_order_id}, {"_id": 0})
            
            if existing_order and existing_order.get('payment_status') == 'pending':
                # Update existing order with new rate
                logger.info(f"📦 Updating existing pending order {existing_order_id}")
                
                # Clean carrier name same as above
                carrier_original = selected_rate.get('carrier', selected_rate.get('carrier_friendly_name', 'Unknown'))
                carrier_clean = carrier_original
                if 'stamps' in carrier_original.lower():
                    carrier_clean = 'USPS'
                else:
                    for known_carrier in ['USPS', 'UPS', 'FedEx']:
                        if known_carrier.lower() in carrier_original.lower():
                            carrier_clean = known_carrier
                            break
                
                await db.orders.update_one(
                    {"order_id": existing_order_id},
                    {"$set": {
                        "selected_carrier": carrier_clean,
                        "selected_service": selected_rate.get('service', selected_rate.get('service_type', 'Standard')),
                        "amount": final_cost
                    }}
                )
                # Reload order from DB to get updated values
                order = await db.orders.find_one({"order_id": existing_order_id}, {"_id": 0})
                if not order:
                    order = existing_order
                logger.info(f"✅ Order {existing_order_id} updated with new rate")
            else:
                # Old order was paid/cancelled, create new one
                # Remove old order_id from context
                if 'order_id' in context.user_data:
                    del context.user_data['order_id']
                
                logger.info(f"📦 Creating new pending order for user {query.from_user.id}")
                order = await create_order_in_db(
                    user=user, 
                    data=context.user_data, 
                    selected_rate=selected_rate, 
                    amount=final_cost, 
                    discount_percent=discount_percent, 
                    discount_amount=discount_amount_val
                )
                context.user_data['order_id'] = order['order_id']
                logger.info(f"✅ Order created: {order['order_id']}, status=pending")
        else:
            # No existing order_id, create new order
            logger.info(f"📦 Creating pending order for user {query.from_user.id}")
            order = await create_order_in_db(
                user=user, 
                data=context.user_data, 
                selected_rate=selected_rate, 
                amount=final_cost, 
                discount_percent=discount_percent, 
                discount_amount=discount_amount_val
            )
            
            # Save order_id in context for later use
            context.user_data['order_id'] = order['order_id']
            logger.info(f"✅ Order created: {order['order_id']}, status=pending")
        
        # Proceed to payment
        from handlers.order_flow.payment import show_payment_methods
        return await show_payment_methods(update, context)
    
    # Unknown action
    logger.warning(f"⚠️ Unknown carrier action: {data}")
    from server import SELECT_CARRIER
    return SELECT_CARRIER
