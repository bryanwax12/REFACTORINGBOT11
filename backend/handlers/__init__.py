"""Handlers package for Telegram bot"""

# Payment handlers (balance, topup)
from .payment_handlers import (
    my_balance_command,
    handle_topup_amount_input,
    add_balance,
    deduct_balance
)

# Template handlers (save, view, edit, delete templates)
from .template_handlers import (
    my_templates_menu,
    view_template,
    use_template,
    delete_template,
    confirm_delete_template,
    rename_template_start,
    rename_template_save,
    save_order_as_template
)

# Order flow handlers (main conversation)
# TODO: Gradually migrate from server.py
# from .order_handlers import (
#     new_order_start,
#     order_conv_handler
# )

__all__ = [
    # Payment
    'my_balance_command',
    'handle_topup_amount_input',
    'add_balance',
    'deduct_balance',
    # Templates
    'my_templates_menu',
    'view_template',
    'use_template',
    'delete_template',
    'confirm_delete_template',
    'rename_template_start',
    'rename_template_save',
    'save_order_as_template',
]
