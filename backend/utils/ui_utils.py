"""
UI Utilities for Telegram Bot
Centralized UI components: keyboards, buttons, message templates
"""
from typing import Optional, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# BUTTON TEXT CONSTANTS
# ============================================================

class ButtonTexts:
    """Centralized button text constants"""
    
    # Navigation
    BACK_TO_MENU = "🔙 Главное меню"
    CANCEL = "❌ Отмена"
    SKIP = "⏭️ Пропустить"
    CONFIRM = "✅ Подтвердить"
    
    # Actions
    CREATE_ORDER = "📦 Создать заказ"
    MY_TEMPLATES = "📋 Мои шаблоны"
    HELP = "❓ Помощь"
    FAQ = "📖 FAQ"
    
    # Payment
    PAY_CRYPTO = "💳 Оплатить криптой"
    PAY_FROM_BALANCE = "💰 Оплатить с баланса"
    ADD_BALANCE = "💵 Пополнить баланс"
    GO_TO_PAYMENT = "💳 Перейти к оплате"
    RETURN_TO_PAYMENT = "💳 Оплатить заказ"
    
    # Confirmations
    YES_TO_MENU = "✅ Да, в главное меню"
    NO_RETURN = "❌ Отмена, вернуться"
    
    # Admin
    CONTACT_ADMIN = "💬 Связаться с администратором"
    
    @staticmethod
    def my_balance(balance: float) -> str:
        """Dynamic balance button text"""
        return f"💳 Мой баланс (${balance:.2f})"


class CallbackData:
    """Centralized callback_data constants"""
    
    # Navigation
    START = 'start'
    MAIN_MENU = 'main_menu'
    HELP = 'help'
    FAQ = 'faq'
    
    # Order
    NEW_ORDER = 'new_order'
    CANCEL_ORDER = 'cancel_order'
    CONFIRM_EXIT_TO_MENU = 'confirm_exit_to_menu'
    
    # Order Flow Skips
    SKIP_FROM_ADDRESS2 = 'skip_from_address2'
    SKIP_FROM_PHONE = 'skip_from_phone'
    SKIP_TO_ADDRESS2 = 'skip_to_address2'
    SKIP_TO_PHONE = 'skip_to_phone'
    
    # Payment
    MY_BALANCE = 'my_balance'
    RETURN_TO_PAYMENT = 'return_to_payment'
    
    # Templates
    MY_TEMPLATES = 'my_templates'


# ============================================================
# KEYBOARD BUILDERS
# ============================================================

def get_main_menu_keyboard(user_balance: float = 0.0) -> InlineKeyboardMarkup:
    """
    Build main menu keyboard with dynamic balance
    
    Args:
        user_balance: User's current balance
    
    Returns:
        InlineKeyboardMarkup with menu buttons
    """
    keyboard = [
        [InlineKeyboardButton(ButtonTexts.CREATE_ORDER, callback_data=CallbackData.NEW_ORDER)],
        [InlineKeyboardButton(ButtonTexts.my_balance(user_balance), callback_data=CallbackData.MY_BALANCE)],
        [InlineKeyboardButton(ButtonTexts.MY_TEMPLATES, callback_data=CallbackData.MY_TEMPLATES)],
        [InlineKeyboardButton(ButtonTexts.HELP, callback_data=CallbackData.HELP)],
        [InlineKeyboardButton(ButtonTexts.FAQ, callback_data=CallbackData.FAQ)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button keyboard (used in order flow)"""
    keyboard = [[InlineKeyboardButton(ButtonTexts.CANCEL, callback_data=CallbackData.CANCEL_ORDER)]]
    return InlineKeyboardMarkup(keyboard)


def get_skip_and_cancel_keyboard(skip_callback: str) -> InlineKeyboardMarkup:
    """
    Keyboard with Skip and Cancel buttons (for optional fields)
    
    Args:
        skip_callback: Callback data for skip button
    
    Returns:
        InlineKeyboardMarkup with skip and cancel
    """
    keyboard = [
        [InlineKeyboardButton(ButtonTexts.SKIP, callback_data=skip_callback)],
        [InlineKeyboardButton(ButtonTexts.CANCEL, callback_data=CallbackData.CANCEL_ORDER)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Simple back to menu button"""
    keyboard = [[InlineKeyboardButton(ButtonTexts.BACK_TO_MENU, callback_data=CallbackData.START)]]
    return InlineKeyboardMarkup(keyboard)


def get_help_keyboard(admin_telegram_id: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Help screen keyboard with optional admin contact
    
    Args:
        admin_telegram_id: Telegram ID of admin (optional)
    
    Returns:
        InlineKeyboardMarkup with help buttons
    """
    keyboard = []
    
    if admin_telegram_id:
        keyboard.append([
            InlineKeyboardButton(
                ButtonTexts.CONTACT_ADMIN, 
                url=f"tg://user?id={admin_telegram_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(ButtonTexts.BACK_TO_MENU, callback_data=CallbackData.START)])
    
    return InlineKeyboardMarkup(keyboard)


def get_exit_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for confirming exit to main menu (when user has pending order)"""
    keyboard = [
        [InlineKeyboardButton(ButtonTexts.YES_TO_MENU, callback_data=CallbackData.CONFIRM_EXIT_TO_MENU)],
        [InlineKeyboardButton(ButtonTexts.NO_RETURN, callback_data=CallbackData.RETURN_TO_PAYMENT)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_payment_success_keyboard(has_pending_order: bool = False, order_amount: float = 0.0) -> InlineKeyboardMarkup:
    """
    Keyboard after successful balance top-up
    
    Args:
        has_pending_order: Whether user has a pending order
        order_amount: Amount of pending order
    
    Returns:
        InlineKeyboardMarkup with appropriate buttons
    """
    keyboard = []
    
    if has_pending_order and order_amount > 0:
        keyboard.append([InlineKeyboardButton(ButtonTexts.RETURN_TO_PAYMENT, callback_data=CallbackData.RETURN_TO_PAYMENT)])
    
    keyboard.append([InlineKeyboardButton(ButtonTexts.BACK_TO_MENU, callback_data=CallbackData.START)])
    
    return InlineKeyboardMarkup(keyboard)


def get_cancel_and_menu_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with Cancel and Back to Menu (for payment flows)"""
    keyboard = [
        [InlineKeyboardButton(ButtonTexts.CANCEL, callback_data=CallbackData.START)],
        [InlineKeyboardButton(ButtonTexts.BACK_TO_MENU, callback_data=CallbackData.START)]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================
# MESSAGE TEMPLATES
# ============================================================

class MessageTemplates:
    """Centralized message text templates"""
    
    @staticmethod
    def welcome(first_name: str) -> str:
        """Welcome message for /start command"""
        return f"""*Добро пожаловать, {first_name}! 🚀*

*Я помогу вам создать shipping labels.*

*Выберите действие:*"""
    
    @staticmethod
    def help_text() -> str:
        """Help message text"""
        return """


*Если у вас возникли вопросы или проблемы, нажмите кнопку ниже:*


"""
    
    @staticmethod
    def faq_text() -> str:
        """FAQ message text"""
        return """📦 *White Label Shipping Bot*

*Создавайте профессиональные shipping labels за минуты!*

✅ *Что я умею:*
• Создание shipping labels для любых посылок
• Поддержка всех популярных курьеров (UPS, FedEx, USPS)
• Точный расчёт стоимости доставки
• Оплата криптовалютой (BTC, ETH, USDT, LTC)
• Индивидуальные скидки

🌍 *Доставка:*
Отправляйте посылки из любой точки США

💰 *Преимущества:*
• Быстрое оформление
• Прозрачные цены
• Безопасные платежи
• Поддержка 24/7"""
    
    @staticmethod
    def maintenance_mode() -> str:
        """Maintenance mode message"""
        return """🔧 *Бот находится на техническом обслуживании.*

Пожалуйста, попробуйте позже.

Приносим извинения за неудобства."""
    
    @staticmethod
    def user_blocked() -> str:
        """User blocked message"""
        return """⛔️ *Вы заблокированы*

Ваш доступ к боту был ограничен администратором.

Для получения дополнительной информации, пожалуйста, свяжитесь с администратором."""
    
    @staticmethod
    def exit_warning(order_amount: float) -> str:
        """Warning when user tries to exit with pending order"""
        return f"""⚠️ *Внимание!*

У вас есть неоплаченный заказ.

Если вы перейдете в главное меню, все данные заказа будут удалены и вам придется создавать заказ заново.

Вы уверены?"""
    
    @staticmethod
    def balance_topped_up(requested: float, actual: float, new_balance: float) -> str:
        """Balance top-up success message"""
        if abs(actual - requested) > 0.01:
            amount_text = f"""💰 *Запрошено:* ${requested:.2f}
💰 *Зачислено:* ${actual:.2f}"""
        else:
            amount_text = f"💰 *Зачислено:* ${actual:.2f}"
        
        return f"""✅ *Спасибо! Ваш баланс пополнен!*

{amount_text}
💳 *Новый баланс:* ${new_balance:.2f}"""
    
    @staticmethod
    def balance_topped_up_with_order(requested: float, actual: float, new_balance: float, order_amount: float) -> str:
        """Balance top-up with pending order"""
        base_message = MessageTemplates.balance_topped_up(requested, actual, new_balance)
        return f"""{base_message}

📦 *Сумма заказа к оплате:* ${order_amount:.2f}
_Нажмите 'Оплатить заказ' чтобы завершить оплату_"""


class OrderStepMessages:
    """Messages for order creation steps"""
    
    @staticmethod
    def step_message(step_num: int, total_steps: int, prompt: str) -> str:
        """Format step message"""
        return f"Шаг {step_num}/{total_steps}: {prompt}"
    
    # FROM address steps
    FROM_NAME = step_message.__func__(1, 13, "👤 Имя отправителя\nНапример: John Smith")
    FROM_ADDRESS = step_message.__func__(2, 13, "🏠 Адрес отправителя\nНапример: 215 Clayton St.")
    FROM_ADDRESS2 = step_message.__func__(3, 13, "🏢 Адрес 2 (опционально)\nНапример: Apt 4B или Suite 200\nИли нажмите \"Пропустить\" ")
    FROM_CITY = step_message.__func__(4, 13, "🏙 Город отправителя\nНапример: San Francisco")
    FROM_STATE = step_message.__func__(5, 13, "📍 Штат отправителя (2 буквы)\nНапример: CA, NY, TX, FL")
    FROM_ZIP = step_message.__func__(6, 13, "📮 ZIP код отправителя\nНапример: 94102")
    FROM_PHONE = step_message.__func__(7, 13, "📞 Телефон отправителя (опционально)\nНапример: +11234567890 или 1234567890\nИли нажмите \"Пропустить\" ")
    
    # TO address steps
    TO_NAME = step_message.__func__(8, 13, "👤 Имя получателя\nНапример: Jane Doe")
    TO_ADDRESS = step_message.__func__(9, 13, "🏠 Адрес получателя\nНапример: 123 Main St.")
    TO_ADDRESS2 = step_message.__func__(10, 13, "🏢 Адрес 2 получателя (опционально)\nНапример: Apt 4B\nИли нажмите \"Пропустить\" ")
    TO_CITY = step_message.__func__(11, 13, "🏙 Город получателя\nНапример: Los Angeles")
    TO_STATE = step_message.__func__(12, 13, "📍 Штат получателя (2 буквы)\nНапример: CA, NY, TX")
    TO_ZIP = step_message.__func__(13, 13, "📮 ZIP код получателя\nНапример: 90001")
    TO_PHONE = "📞 Телефон получателя (опционально)\nНапример: +11234567890\nИли нажмите \"Пропустить\" "
    
    # Parcel steps
    PARCEL_WEIGHT = """📦 Вес посылки (в фунтах)
Например: 5 или 5.5
Минимум: 0.1 фунта
Максимум: 150 фунтов"""
    
    PARCEL_LENGTH = """📏 Длина посылки (в дюймах)
Например: 10 или 10.5
Минимум: 0.1 дюйма
Максимум: 108 дюймов"""
    
    PARCEL_WIDTH = """📐 Ширина посылки (в дюймах)
Например: 8 или 8.5"""
    
    PARCEL_HEIGHT = """📦 Высота посылки (в дюймах)
Например: 6 или 6.5"""


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def build_custom_keyboard(buttons: List[List[dict]]) -> InlineKeyboardMarkup:
    """
    Build custom keyboard from button configuration
    
    Args:
        buttons: List of rows, each row is list of button configs
                 Button config: {"text": "...", "callback_data": "..."}
                 or {"text": "...", "url": "..."}
    
    Returns:
        InlineKeyboardMarkup
    
    Example:
        buttons = [
            [{"text": "Button 1", "callback_data": "btn1"}],
            [{"text": "Button 2", "url": "https://example.com"}]
        ]
    """
    keyboard = []
    for row in buttons:
        keyboard_row = []
        for btn in row:
            if 'url' in btn:
                keyboard_row.append(InlineKeyboardButton(btn['text'], url=btn['url']))
            elif 'callback_data' in btn:
                keyboard_row.append(InlineKeyboardButton(btn['text'], callback_data=btn['callback_data']))
        if keyboard_row:
            keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(keyboard)


def add_back_button(keyboard: List[List[InlineKeyboardButton]], 
                    callback_data: str = CallbackData.START) -> List[List[InlineKeyboardButton]]:
    """
    Add back button to existing keyboard
    
    Args:
        keyboard: Existing keyboard (list of lists)
        callback_data: Callback for back button
    
    Returns:
        Updated keyboard with back button
    """
    keyboard.append([InlineKeyboardButton(ButtonTexts.BACK_TO_MENU, callback_data=callback_data)])
    return keyboard


# ============================================================
# TEMPLATE-SPECIFIC KEYBOARDS
# ============================================================

def get_template_view_keyboard(template_id: str) -> InlineKeyboardMarkup:
    """
    Keyboard for template detail view with action buttons
    
    Args:
        template_id: ID of the template
    
    Returns:
        InlineKeyboardMarkup with use/edit/delete buttons
    """
    keyboard = [
        [InlineKeyboardButton("✅ Использовать шаблон", callback_data=f'template_use_{template_id}')],
        [InlineKeyboardButton("✏️ Переименовать", callback_data=f'template_rename_{template_id}')],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f'template_delete_{template_id}')],
        [InlineKeyboardButton("🔙 К списку шаблонов", callback_data=CallbackData.MY_TEMPLATES)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_template_delete_confirmation_keyboard(template_id: str) -> InlineKeyboardMarkup:
    """
    Confirmation keyboard for template deletion
    
    Args:
        template_id: ID of the template to delete
    
    Returns:
        InlineKeyboardMarkup with confirm/cancel buttons
    """
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f'template_confirm_delete_{template_id}')],
        [InlineKeyboardButton("❌ Отмена", callback_data=f'template_view_{template_id}')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_template_rename_keyboard(template_id: str) -> InlineKeyboardMarkup:
    """
    Keyboard for template rename flow
    
    Args:
        template_id: ID of the template being renamed
    
    Returns:
        InlineKeyboardMarkup with cancel button
    """
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f'template_view_{template_id}')]]
    return InlineKeyboardMarkup(keyboard)


def get_templates_list_keyboard(templates: List[dict]) -> InlineKeyboardMarkup:
    """
    Build keyboard with list of user's templates
    
    Args:
        templates: List of template dicts with 'name' and 'id' fields
    
    Returns:
        InlineKeyboardMarkup with template buttons + back to menu
    """
    keyboard = []
    
    for template in templates:
        template_name = template.get('name', 'Без названия')
        template_id = template.get('id')
        keyboard.append([InlineKeyboardButton(
            f"📄 {template_name}",
            callback_data=f'template_view_{template_id}'
        )])
    
    keyboard.append([InlineKeyboardButton(ButtonTexts.BACK_TO_MENU, callback_data=CallbackData.START)])
    
    return InlineKeyboardMarkup(keyboard)
