"""
Unit tests for UI Components
Tests 5 UI classes in utils/ui_utils.py

UI Components являются simple formatters без сложной логики,
поэтому тесты проверяют правильность форматирования строк и структуры клавиатур.
"""
import pytest
from utils.ui_utils import (
    ShippingRatesUI,
    LabelCreationUI,
    DataConfirmationUI,
    PaymentFlowUI,
    TemplateManagementUI
)


# ============================================================
# SHIPPING RATES UI TESTS
# ============================================================

def test_shipping_rates_progress_message():
    """Test progress message formatting"""
    msg = ShippingRatesUI.progress_message(5)
    
    assert '⏳' in msg
    assert '5 сек' in msg


def test_shipping_rates_cache_hit():
    """Test cache hit message"""
    msg = ShippingRatesUI.cache_hit_message()
    
    assert '✅' in msg
    assert 'кэш' in msg.lower()


def test_shipping_rates_missing_fields_error():
    """Test missing fields error formatting"""
    fields = ['from_city', 'to_zip', 'weight']
    msg = ShippingRatesUI.missing_fields_error(fields)
    
    assert '❌' in msg
    assert 'from_city' in msg
    assert 'to_zip' in msg
    assert 'weight' in msg


def test_shipping_rates_format_rates_message():
    """Test rates list formatting"""
    rates = [
        {
            'carrier': 'UPS',
            'service': 'Ground',
            'amount': 15.50,
            'days': 3
        },
        {
            'carrier': 'FedEx',
            'service': '2 Day',
            'amount': 25.00,
            'days': 2
        }
    ]
    
    msg = ShippingRatesUI.format_rates_message(rates, user_balance=50.00)
    
    assert 'UPS' in msg
    assert 'FedEx' in msg
    assert '$15.50' in msg
    assert '$25.00' in msg
    assert '$50.00' in msg  # Balance


def test_shipping_rates_build_keyboard():
    """Test rates keyboard building"""
    rates = [
        {'carrier': 'UPS', 'service': 'Ground', 'amount': 15.50},
        {'carrier': 'FedEx', 'service': '2Day', 'amount': 25.00}
    ]
    
    keyboard = ShippingRatesUI.build_rates_keyboard(rates)
    
    # Should have rate buttons + refresh + cancel
    assert len(keyboard.inline_keyboard) >= 3


# ============================================================
# LABEL CREATION UI TESTS
# ============================================================

def test_label_creation_creating_message():
    """Test creating label progress message"""
    msg = LabelCreationUI.creating_label_message()
    
    assert '📝' in msg
    assert 'label' in msg.lower()


def test_label_creation_success_message():
    """Test success message formatting"""
    msg = LabelCreationUI.success_message('1234567890', 'UPS')
    
    assert '✅' in msg
    assert '1234567890' in msg
    assert 'UPS' in msg


def test_label_creation_error_message():
    """Test error message formatting"""
    msg = LabelCreationUI.error_message('API timeout')
    
    assert '❌' in msg
    assert 'API timeout' in msg


def test_label_creation_insufficient_funds():
    """Test insufficient funds message"""
    msg = LabelCreationUI.insufficient_funds_message(30.00, 25.00)
    
    assert '❌' in msg
    assert '$30.00' in msg  # Required
    assert '$25.00' in msg  # Available
    assert '$5.00' in msg   # Deficit


# ============================================================
# DATA CONFIRMATION UI TESTS
# ============================================================

def test_data_confirmation_header():
    """Test confirmation header"""
    header = DataConfirmationUI.confirmation_header()
    
    assert '📋' in header
    assert 'данные' in header.lower()


def test_data_confirmation_format_address():
    """Test address section formatting"""
    data = {
        'from_name': 'John Doe',
        'from_street': '123 Main St',
        'from_street2': 'Apt 4',
        'from_city': 'New York',
        'from_state': 'NY',
        'from_zip': '10001',
        'from_phone': '+15551234567'
    }
    
    section = DataConfirmationUI.format_address_section('Отправитель', data, 'from')
    
    assert 'Отправитель' in section
    assert 'John Doe' in section
    assert '123 Main St' in section
    assert 'Apt 4' in section
    assert 'New York' in section


def test_data_confirmation_format_parcel():
    """Test parcel section formatting"""
    data = {
        'weight': 5.5,
        'length': 12,
        'width': 8,
        'height': 6
    }
    
    section = DataConfirmationUI.format_parcel_section(data)
    
    assert 'Посылка' in section
    assert '5.5' in section
    assert '12' in section


def test_data_confirmation_build_keyboard():
    """Test confirmation keyboard building"""
    keyboard = DataConfirmationUI.build_confirmation_keyboard()
    
    # Should have at least 4 buttons
    assert len(keyboard.inline_keyboard) >= 4


def test_data_confirmation_build_edit_menu():
    """Test edit menu keyboard"""
    keyboard = DataConfirmationUI.build_edit_menu_keyboard()
    
    # Should have sender, recipient, parcel, back buttons
    assert len(keyboard.inline_keyboard) == 4


# ============================================================
# PAYMENT FLOW UI TESTS
# ============================================================

def test_payment_flow_balance_screen():
    """Test balance screen formatting"""
    msg = PaymentFlowUI.balance_screen(75.50)
    
    assert '💳' in msg
    assert '$75.50' in msg
    assert 'баланс' in msg.lower()


def test_payment_flow_insufficient_balance_error():
    """Test insufficient balance error"""
    msg = PaymentFlowUI.insufficient_balance_error()
    
    assert '❌' in msg
    assert 'недостаточно' in msg.lower()


def test_payment_flow_payment_success():
    """Test payment success message"""
    msg = PaymentFlowUI.payment_success_balance(25.00, 50.00)
    
    assert '✅' in msg
    assert '$25.00' in msg  # Amount
    assert '$50.00' in msg  # New balance


def test_payment_flow_topup_amount_validation():
    """Test topup validation messages"""
    # Too small
    msg = PaymentFlowUI.topup_amount_too_small()
    assert '❌' in msg
    assert '10' in msg
    
    # Too large
    msg = PaymentFlowUI.topup_amount_too_large()
    assert '❌' in msg
    assert '10,000' in msg or '10000' in msg


def test_payment_flow_payment_method_selection():
    """Test payment method selection message"""
    # Sufficient balance
    msg = PaymentFlowUI.payment_method_selection(25.00, 50.00)
    assert '$25.00' in msg
    assert '$50.00' in msg
    
    # Insufficient balance
    msg = PaymentFlowUI.payment_method_selection(75.00, 50.00)
    assert '$75.00' in msg
    assert '$50.00' in msg
    assert '$25.00' in msg  # Deficit


def test_payment_flow_build_keyboards():
    """Test keyboard builders"""
    balance_kb = PaymentFlowUI.build_balance_keyboard()
    assert len(balance_kb.inline_keyboard) >= 1
    
    crypto_kb = PaymentFlowUI.build_crypto_selection_keyboard()
    # BTC, ETH, USDT, LTC, Cancel
    assert len(crypto_kb.inline_keyboard) >= 5


# ============================================================
# TEMPLATE MANAGEMENT UI TESTS
# ============================================================

def test_template_management_no_templates():
    """Test no templates message"""
    msg = TemplateManagementUI.no_templates_message()
    
    assert '📋' in msg
    assert 'шаблон' in msg.lower()


def test_template_management_list_header():
    """Test templates list header"""
    header = TemplateManagementUI.templates_list_header()
    
    assert '📋' in header
    assert 'шаблон' in header.lower()


def test_template_management_format_template():
    """Test template item formatting"""
    template = {
        'name': 'Home to Work',
        'from_name': 'John Doe',
        'from_street1': '123 Main St',
        'from_city': 'New York',
        'from_state': 'NY',
        'from_zip': '10001',
        'to_name': 'Jane Smith',
        'to_street1': '456 Oak Ave',
        'to_city': 'Los Angeles',
        'to_state': 'CA',
        'to_zip': '90001'
    }
    
    formatted = TemplateManagementUI.format_template_item(1, template)
    
    assert 'Home to Work' in formatted
    assert 'John Doe' in formatted
    assert 'Jane Smith' in formatted


def test_template_management_saved_success():
    """Test template saved success message"""
    msg = TemplateManagementUI.template_saved_success('My Template')
    
    assert '✅' in msg
    assert 'My Template' in msg


def test_template_management_deleted_success():
    """Test template deleted message"""
    msg = TemplateManagementUI.template_deleted_success('Old Template')
    
    assert '✅' in msg
    assert 'Old Template' in msg


def test_template_management_build_keyboards():
    """Test keyboard builders"""
    # No templates keyboard
    no_kb = TemplateManagementUI.build_no_templates_keyboard()
    assert len(no_kb.inline_keyboard) >= 2
    
    # View template keyboard
    view_kb = TemplateManagementUI.build_template_view_keyboard('template_123')
    assert len(view_kb.inline_keyboard) == 4
    
    # Confirm delete keyboard
    del_kb = TemplateManagementUI.build_confirm_delete_keyboard('template_123')
    assert len(del_kb.inline_keyboard) == 2


# ============================================================
# INTEGRATION TEST
# ============================================================

def test_ui_components_consistency():
    """Test that all UI components follow consistent patterns"""
    # All error messages should have ❌
    assert '❌' in ShippingRatesUI.api_error_message('test')
    assert '❌' in LabelCreationUI.error_message('test')
    assert '❌' in PaymentFlowUI.insufficient_balance_error()
    
    # All success messages should have ✅
    assert '✅' in LabelCreationUI.success_message('123', 'UPS')
    assert '✅' in PaymentFlowUI.payment_success_balance(10, 40)
    assert '✅' in TemplateManagementUI.template_saved_success('test')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
