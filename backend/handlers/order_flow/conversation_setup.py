"""
Order Flow: Conversation Handler Setup
Centralizes the ConversationHandler configuration for order creation flow
"""
import logging
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

logger = logging.getLogger(__name__)


def setup_order_conversation_handler():
    """
    Create and configure the main order conversation handler
    
    Returns:
        ConversationHandler: Configured conversation handler for order flow
    """
    from server import (
        # State constants
        FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, FROM_STATE,
        FROM_ZIP, FROM_PHONE, TO_NAME, TO_ADDRESS, TO_ADDRESS2,
        TO_CITY, TO_STATE, TO_ZIP, TO_PHONE, PARCEL_WEIGHT,
        PARCEL_LENGTH, PARCEL_WIDTH, PARCEL_HEIGHT, CALCULATING_RATES, CONFIRM_DATA,
        EDIT_MENU, SELECT_CARRIER, PAYMENT_METHOD, TOPUP_AMOUNT,
        TEMPLATE_NAME, TEMPLATE_LIST, TEMPLATE_VIEW, TEMPLATE_LOADED,
        start_command
    )
    # Import handlers from their actual locations
    from handlers.order_flow.payment import process_payment
    from handlers.order_flow.confirmation import handle_data_confirmation
    from handlers.order_flow.entry_points import order_new, order_from_template_list
    from handlers.template_handlers import (
        use_template,
        view_template,
        delete_template,
        confirm_delete_template,
        my_templates_menu
    )
    
    # Import handlers from order_flow modules
    from handlers.order_flow.entry_points import (
        new_order_start,
        start_order_with_template,
        return_to_payment_after_topup
    )
    from handlers.order_flow.from_address import (
        order_from_name,
        order_from_address,
        order_from_address2,
        order_from_city,
        order_from_state,
        order_from_zip,
        order_from_phone
    )
    from handlers.order_flow.to_address import (
        order_to_name,
        order_to_address,
        order_to_address2,
        order_to_city,
        order_to_state,
        order_to_zip,
        order_to_phone
    )
    from handlers.order_flow.parcel import (
        order_parcel_weight,
        order_parcel_length,
        order_parcel_width,
        order_parcel_height
    )
    from handlers.order_flow.skip_handlers import (
        skip_from_address2,
        skip_to_address2,
        skip_from_phone,
        skip_to_phone,
        skip_parcel_dimensions,
        skip_parcel_width_height,
        skip_parcel_height
    )
    from handlers.order_flow.rates import fetch_shipping_rates
    from handlers.order_flow.carriers import select_carrier
    from handlers.order_flow.cancellation import (
        cancel_order,
        confirm_cancel_order,
        return_to_order
    )
    from handlers.order_flow.template_save import (
        save_template_name,
        handle_template_update,
        handle_template_new_name,
        continue_order_after_template,
        handle_topup_amount
    )
    from handlers.order_flow.payment import (
        handle_order_summary,
        handle_proceed_to_payment
    )
    from handlers.payment_handlers import handle_topup_crypto_selection
    
    # Import template editing handlers
    from handlers.template_handlers import edit_template_from_address, edit_template_to_address
    
    # Build the conversation handler
    order_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(new_order_start, pattern='^new_order$'),
            CallbackQueryHandler(start_order_with_template, pattern='^start_order_with_template$'),
            CallbackQueryHandler(return_to_payment_after_topup, pattern='^return_to_payment$'),
            CallbackQueryHandler(use_template, pattern='^template_use_'),  # Use template for order
            CallbackQueryHandler(edit_template_from_address, pattern='^template_edit_from_'),  # Edit template FROM
            CallbackQueryHandler(edit_template_to_address, pattern='^template_edit_to_'),  # Edit template TO
        ],
        states={
            FROM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_name),
                CallbackQueryHandler(order_new, pattern='^order_new$'),
                CallbackQueryHandler(order_from_template_list, pattern='^order_from_template$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            FROM_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_address),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            FROM_ADDRESS2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_address2),
                CallbackQueryHandler(skip_from_address2, pattern='^skip_from_address2$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            FROM_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_city),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            FROM_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_state),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            FROM_ZIP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_zip),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            FROM_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_phone),
                CallbackQueryHandler(skip_from_phone, pattern='^skip_from_phone$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            TO_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_name),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            TO_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_address),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            TO_ADDRESS2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_address2),
                CallbackQueryHandler(skip_to_address2, pattern='^skip_to_address2$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            TO_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_city),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            TO_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_state),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            TO_ZIP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_zip),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            TO_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_phone),
                CallbackQueryHandler(skip_to_phone, pattern='^skip_to_phone$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            PARCEL_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_weight),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            PARCEL_LENGTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_length),
                CallbackQueryHandler(skip_parcel_dimensions, pattern='^skip_parcel_dimensions$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            PARCEL_WIDTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_width),
                CallbackQueryHandler(skip_parcel_width_height, pattern='^skip_parcel_width_height$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            PARCEL_HEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_height),
                CallbackQueryHandler(skip_parcel_height, pattern='^skip_parcel_height$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            CALCULATING_RATES: [
                MessageHandler(filters.ALL, fetch_shipping_rates),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            ],
            CONFIRM_DATA: [
                CallbackQueryHandler(handle_data_confirmation, pattern='^(confirm_data|save_template|edit_data|edit_addresses_error|edit_from_address|edit_to_address|return_to_order|confirm_cancel|cancel_order)$')
            ],
            EDIT_MENU: [
                CallbackQueryHandler(handle_data_confirmation, pattern='^(edit_from_address|edit_to_address|edit_parcel|back_to_confirmation|return_to_order|confirm_cancel)$')
            ],
            SELECT_CARRIER: [
                CallbackQueryHandler(select_carrier, pattern='^(select_carrier_|refresh_rates|check_data|return_to_order|confirm_cancel|cancel_order)')
            ],
            PAYMENT_METHOD: [
                CallbackQueryHandler(return_to_order, pattern='^return_to_order$'),
                CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                CallbackQueryHandler(handle_order_summary, pattern='^order_summary$'),
                CallbackQueryHandler(handle_proceed_to_payment, pattern='^proceed_to_payment$'),
                CallbackQueryHandler(handle_topup_crypto_selection, pattern='^topup_crypto_'),
                CallbackQueryHandler(process_payment, pattern='^(pay_from_balance|pay_with_crypto|top_up_balance|topup_for_order|back_to_rates|cancel_order)')
            ],
            TOPUP_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topup_amount)
            ],
            TEMPLATE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_template_name),
                CallbackQueryHandler(handle_template_update, pattern='^template_update_'),
                CallbackQueryHandler(handle_template_new_name, pattern='^template_new_name$'),
                CallbackQueryHandler(continue_order_after_template, pattern='^continue_order$'),
                CallbackQueryHandler(start_command, pattern='^start$')
            ],
            TEMPLATE_LIST: [
                CallbackQueryHandler(use_template, pattern='^template_use_'),
                CallbackQueryHandler(view_template, pattern='^template_view_'),
                CallbackQueryHandler(start_command, pattern='^start$')
            ],
            TEMPLATE_VIEW: [
                CallbackQueryHandler(use_template, pattern='^template_use_'),
                CallbackQueryHandler(delete_template, pattern='^template_delete_'),
                CallbackQueryHandler(confirm_delete_template, pattern='^template_confirm_delete_'),
                CallbackQueryHandler(my_templates_menu, pattern='^my_templates$'),
                CallbackQueryHandler(start_command, pattern='^start$')
            ],
            TEMPLATE_LOADED: [
                CallbackQueryHandler(start_order_with_template, pattern='^start_order_with_template$'),
                CallbackQueryHandler(my_templates_menu, pattern='^my_templates$'),
                CallbackQueryHandler(start_command, pattern='^start$')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_order, pattern='^cancel_order$'),
            CommandHandler('start', start_command)
        ],
        per_chat=True,
        per_user=True,
        per_message=False,  # False is correct: we use MessageHandler (not only CallbackQueryHandler)
        allow_reentry=True,
        block=False,  # CRITICAL: Process messages from same user sequentially to prevent race conditions
        name="order_conversation"  # Name for logging/debugging
    )
    
    logger.info("✅ Order conversation handler configured successfully")
    return order_conv_handler


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = ['setup_order_conversation_handler']
