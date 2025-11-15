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
    SKIP_PARCEL_DIMENSIONS = 'skip_parcel_dimensions'  # Skip all dimensions (L/W/H) after weight
    SKIP_PARCEL_WIDTH_HEIGHT = 'skip_parcel_width_height'  # Skip W and H after length
    SKIP_PARCEL_HEIGHT = 'skip_parcel_height'  # Skip only height
    
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


def get_standard_size_and_cancel_keyboard(standard_size_callback: str) -> InlineKeyboardMarkup:
    """
    Keyboard with 'Use Standard Size' and Cancel buttons (for parcel dimensions)
    
    Args:
        standard_size_callback: Callback data for standard size button
    
    Returns:
        InlineKeyboardMarkup with standard size and cancel buttons
    """
    keyboard = [
        [InlineKeyboardButton("⏭️ Использовать стандартные размеры", callback_data=standard_size_callback)],
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
        return """⚠️ *Внимание!*

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


class TemplateMessages:
    """Messages for template management"""
    
    @staticmethod
    def no_templates() -> str:
        """Message when user has no templates"""
        return "📋 У вас пока нет сохранённых шаблонов.\n\nШаблоны создаются автоматически после успешного создания заказа."
    
    @staticmethod
    def templates_list(count: int) -> str:
        """Message for templates list"""
        return f"📋 Ваши шаблоны ({count}):\n\nВыберите шаблон для просмотра или использования:"
    
    @staticmethod
    def template_details(template: dict) -> str:
        """Format template details message"""
        return f"""📄 Шаблон: {template.get('name', 'Без названия')}

📍 Адрес отправителя:
{template.get('from_name')}
{template.get('from_street1')}
{template.get('from_street2') or ''}
{template.get('from_city')}, {template.get('from_state')} {template.get('from_zip')}
📞 {template.get('from_phone') or 'Не указан'}

📍 Адрес получателя:
{template.get('to_name')}
{template.get('to_street1')}
{template.get('to_street2') or ''}
{template.get('to_city')}, {template.get('to_state')} {template.get('to_zip')}
📞 {template.get('to_phone') or 'Не указан'}"""
    
    @staticmethod
    def template_loaded(template_name: str) -> str:
        """Message when template is loaded"""
        return f"""✅ Шаблон "{template_name}" загружен!

Адреса заполнены автоматически.
Введите вес посылки в фунтах (lb):"""
    
    @staticmethod
    def confirm_delete(template_name: str) -> str:
        """Confirmation message for template deletion"""
        return f"""⚠️ Вы уверены, что хотите удалить шаблон "{template_name}"?

Это действие нельзя отменить."""
    
    @staticmethod
    def rename_prompt() -> str:
        """Prompt for template rename"""
        return "📝 Введите новое название для шаблона:"
    
    @staticmethod
    def template_deleted() -> str:
        """Success message after deletion"""
        return "✅ Шаблон удалён"
    
    @staticmethod
    def template_not_found() -> str:
        """Error message when template not found"""
        return "❌ Шаблон не найден"
    
    @staticmethod
    def delete_error() -> str:
        """Error message on deletion failure"""
        return "❌ Ошибка при удалении шаблона"
    
    @staticmethod
    def name_too_long() -> str:
        """Error when template name is too long"""
        return "❌ Название слишком длинное (максимум 50 символов)"


class OrderFlowMessages:
    """Messages for order flow (non-step messages)"""
    
    @staticmethod
    def create_order_choice() -> str:
        """Choice between new order or from template"""
        return """📦 Создать заказ

Выберите способ создания:"""
    
    @staticmethod
    def new_order_start() -> str:
        """Start new order message"""
        return """📦 Создание нового заказа

Шаг 1/13: 👤 Имя отправителя
Например: John Smith"""
    
    @staticmethod
    def select_template() -> str:
        """Select template for order"""
        return "📋 *Выберите шаблон:*\n\n"
    
    @staticmethod
    def no_templates_error() -> str:
        """Error when no templates available"""
        return "❌ У вас нет сохраненных шаблонов"
    
    @staticmethod
    def template_item(i: int, template: dict) -> str:
        """Format single template for list"""
        from_name = template.get('from_name', '')
        from_street = template.get('from_street1', '')
        from_city = template.get('from_city', '')
        from_state = template.get('from_state', '')
        from_zip = template.get('from_zip', '')
        to_name = template.get('to_name', '')
        to_street = template.get('to_street1', '')
        to_city = template.get('to_city', '')
        to_state = template.get('to_state', '')
        to_zip = template.get('to_zip', '')
        
        return f"""*{i}. {template['name']}*
📤 От: {from_name}
   {from_street}, {from_city}, {from_state} {from_zip}
📥 Кому: {to_name}
   {to_street}, {to_city}, {to_state} {to_zip}

"""


class OrderStepMessages:
    """Messages for order creation steps"""
    
    @staticmethod
    def step_message(step_num: int, total_steps: int, prompt: str) -> str:
        """Format step message"""
        return f"Шаг {step_num}/{total_steps}: {prompt}"
    
    @staticmethod
    def get_step_keyboard_and_message(state: str):
        """
        Get keyboard and message for a given state (for order restoration)
        
        Args:
            state: State constant (e.g., 'FROM_NAME', 'FROM_ADDRESS2')
        
        Returns:
            Tuple of (keyboard, message_text) or (None, message_text) if no keyboard
        """
        
        # Map states to their messages and keyboards
        state_mapping = {
            'FROM_NAME': (None, OrderStepMessages.FROM_NAME),
            'FROM_ADDRESS': (None, OrderStepMessages.FROM_ADDRESS),
            'FROM_ADDRESS2': (
                get_skip_and_cancel_keyboard(CallbackData.SKIP_FROM_ADDRESS2),
                OrderStepMessages.FROM_ADDRESS2
            ),
            'FROM_CITY': (None, OrderStepMessages.FROM_CITY),
            'FROM_STATE': (None, OrderStepMessages.FROM_STATE),
            'FROM_ZIP': (None, OrderStepMessages.FROM_ZIP),
            'FROM_PHONE': (
                get_skip_and_cancel_keyboard(CallbackData.SKIP_FROM_PHONE),
                OrderStepMessages.FROM_PHONE
            ),
            'TO_NAME': (None, OrderStepMessages.TO_NAME),
            'TO_ADDRESS': (None, OrderStepMessages.TO_ADDRESS),
            'TO_ADDRESS2': (
                get_skip_and_cancel_keyboard(CallbackData.SKIP_TO_ADDRESS2),
                OrderStepMessages.TO_ADDRESS2
            ),
            'TO_CITY': (None, OrderStepMessages.TO_CITY),
            'TO_STATE': (None, OrderStepMessages.TO_STATE),
            'TO_ZIP': (None, OrderStepMessages.TO_ZIP),
            'TO_PHONE': (
                get_skip_and_cancel_keyboard(CallbackData.SKIP_TO_PHONE),
                OrderStepMessages.TO_PHONE
            ),
            'PARCEL_WEIGHT': (None, OrderStepMessages.PARCEL_WEIGHT),
            'PARCEL_LENGTH': (
                get_standard_size_and_cancel_keyboard(CallbackData.SKIP_PARCEL_DIMENSIONS),
                OrderStepMessages.PARCEL_LENGTH
            ),
            'PARCEL_WIDTH': (
                get_standard_size_and_cancel_keyboard(CallbackData.SKIP_PARCEL_WIDTH_HEIGHT),
                OrderStepMessages.PARCEL_WIDTH
            ),
            'PARCEL_HEIGHT': (
                get_standard_size_and_cancel_keyboard(CallbackData.SKIP_PARCEL_HEIGHT),
                OrderStepMessages.PARCEL_HEIGHT
            ),
        }
        
        return state_mapping.get(state, (None, "Продолжаем оформление заказа..."))
    
    # FROM address steps
    FROM_NAME = step_message.__func__(1, 18, "👤 Имя отправителя\nНапример: John Smith")
    FROM_ADDRESS = step_message.__func__(2, 18, "🏠 Адрес отправителя\nНапример: 215 Clayton St.")
    FROM_ADDRESS2 = step_message.__func__(3, 18, "🏢 Адрес 2 (опционально)\nНапример: Apt 4B или Suite 200\nИли нажмите \"Пропустить\" ")
    FROM_CITY = step_message.__func__(4, 18, "🏙 Город отправителя\nНапример: San Francisco")
    FROM_STATE = step_message.__func__(5, 18, "📍 Штат отправителя (2 буквы)\nНапример: CA, NY, TX, FL")
    FROM_ZIP = step_message.__func__(6, 18, "📮 ZIP код отправителя\nНапример: 94102")
    FROM_PHONE = step_message.__func__(7, 18, "📞 Телефон отправителя (опционально)\nНапример: +11234567890 или 1234567890\nИли нажмите \"Пропустить\" ")
    
    # TO address steps
    TO_NAME = step_message.__func__(8, 18, "👤 Имя получателя\nНапример: Jane Doe")
    TO_ADDRESS = step_message.__func__(9, 18, "🏠 Адрес получателя\nНапример: 123 Main St.")
    TO_ADDRESS2 = step_message.__func__(10, 18, "🏢 Адрес 2 получателя (опционально)\nНапример: Apt 4B\nИли нажмите \"Пропустить\" ")
    TO_CITY = step_message.__func__(11, 18, "🏙 Город получателя\nНапример: Los Angeles")
    TO_STATE = step_message.__func__(12, 18, "📍 Штат получателя (2 буквы)\nНапример: CA, NY, TX")
    TO_ZIP = step_message.__func__(13, 18, "📮 ZIP код получателя\nНапример: 90001")
    TO_PHONE = step_message.__func__(14, 18, "📞 Телефон получателя (опционально)\nНапример: +11234567890\nИли нажмите \"Пропустить\" ")
    
    # Parcel steps
    PARCEL_WEIGHT = step_message.__func__(15, 18, "📦 Вес посылки (в фунтах)\nНапример: 5 или 5.5")
    PARCEL_LENGTH = step_message.__func__(16, 18, "📏 Длина посылки (в дюймах)\nНапример: 10 или 10.5")
    PARCEL_WIDTH = step_message.__func__(17, 18, "📐 Ширина посылки (в дюймах)\nНапример: 8 или 8.5")
    PARCEL_HEIGHT = step_message.__func__(18, 18, "📦 Высота посылки (в дюймах)\nНапример: 6 или 6.5")
    
    # Special state for calculating rates
    CALCULATING_RATES = "⏳ Рассчитываю доступные тарифы...\n\nПожалуйста, подождите."


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


# ============================================================
# ORDER FLOW KEYBOARDS
# ============================================================

def get_new_order_choice_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard for choosing new order or from template
    
    Returns:
        InlineKeyboardMarkup with new/template/cancel buttons
    """
    keyboard = [
        [InlineKeyboardButton("📝 Новый заказ", callback_data='order_new')],
        [InlineKeyboardButton("📋 Из шаблона", callback_data='order_from_template')],
        [InlineKeyboardButton(ButtonTexts.CANCEL, callback_data=CallbackData.START)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_template_selection_keyboard(templates: List[dict]) -> InlineKeyboardMarkup:
    """
    Build keyboard with templates for order creation
    
    Args:
        templates: List of template dicts with 'name' and 'id' fields
    
    Returns:
        InlineKeyboardMarkup with template buttons + cancel
    """
    keyboard = []
    
    for i, template in enumerate(templates, 1):
        keyboard.append([InlineKeyboardButton(
            f"{i}. {template['name']}", 
            callback_data=f"template_use_{template['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(ButtonTexts.CANCEL, callback_data=CallbackData.START)])
    
    return InlineKeyboardMarkup(keyboard)


def get_edit_data_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard for editing data when there's an error
    
    Returns:
        InlineKeyboardMarkup with edit/cancel buttons
    """
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать данные", callback_data='edit_data')],
        [InlineKeyboardButton(ButtonTexts.CANCEL, callback_data='cancel_order')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_edit_addresses_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard for editing addresses when there's an error
    
    Returns:
        InlineKeyboardMarkup with edit addresses/cancel buttons
    """
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
        [InlineKeyboardButton(ButtonTexts.CANCEL, callback_data='cancel_order')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_retry_edit_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard with retry, edit addresses, and cancel options
    
    Returns:
        InlineKeyboardMarkup with retry/edit/cancel buttons
    """
    keyboard = [
        [InlineKeyboardButton("🔄 Попробовать снова", callback_data='continue_order')],
        [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
        [InlineKeyboardButton(ButtonTexts.CANCEL, callback_data='cancel_order')]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_rates_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard with back to rates and cancel buttons
    
    Returns:
        InlineKeyboardMarkup with back/cancel buttons
    """
    keyboard = [
        [
            InlineKeyboardButton("◀️ Назад к тарифам", callback_data='back_to_rates'),
            InlineKeyboardButton(ButtonTexts.CANCEL, callback_data='cancel_order')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_payment_keyboard(balance: float, amount: float) -> InlineKeyboardMarkup:
    """
    Build payment keyboard based on balance
    
    Args:
        balance: User's current balance
        amount: Order amount
    
    Returns:
        InlineKeyboardMarkup with appropriate payment options
    """
    keyboard = []
    
    if balance >= amount:
        # Sufficient funds - show pay from balance button
        keyboard.append([InlineKeyboardButton(
            f"💳 Оплатить с баланса (${balance:.2f})",
            callback_data='pay_from_balance'
        )])
    else:
        # Insufficient funds - show top-up button
        keyboard.append([InlineKeyboardButton(
            "💵 Пополнить баланс",
            callback_data='top_up_balance'
        )])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад к тарифам", callback_data='back_to_rates'),
        InlineKeyboardButton(ButtonTexts.CANCEL, callback_data='cancel_order')
    ])
    
    return InlineKeyboardMarkup(keyboard)



# ============================================================
# SHIPPING RATES UI COMPONENTS
# ============================================================

class ShippingRatesUI:
    """UI components for shipping rates display and selection"""
    
    # Carrier icons mapping
    CARRIER_ICONS = {
        'UPS': '🛡 UPS',
        'USPS': '🦅 USPS',
        'Stamps.com': '🦅 USPS',
        'FedEx One Balance': '⚡ FedEx',
        'FedEx': '⚡ FedEx'
    }
    
    @staticmethod
    def progress_message(seconds: int = 0) -> str:
        """Progress message while fetching rates"""
        return f"⏳ Получаю доступные курьерские службы и тарифы... ({seconds} сек)"
    
    @staticmethod
    def cache_hit_message() -> str:
        """Message when using cached rates"""
        return "✅ Тарифы загружены из кэша"
    
    @staticmethod
    def missing_fields_error(fields: list) -> str:
        """Error message for missing required fields"""
        fields_list = "\n• ".join(fields)
        return f"""❌ Ошибка: Отсутствуют обязательные поля:

• {fields_list}

Пожалуйста, заполните все необходимые поля заказа."""
    
    @staticmethod
    def api_error_message(error: str) -> str:
        """Error message for API failures"""
        return f"""❌ Ошибка при получении тарифов

*Детали:* {error}

Пожалуйста, попробуйте снова или обратитесь в поддержку."""
    
    @staticmethod
    def no_rates_found() -> str:
        """Message when no rates are available"""
        return """❌ К сожалению, не удалось найти доступные тарифы для указанных адресов.

Возможные причины:
• Указанные адреса не обслуживаются курьерскими службами
• Вес или размеры посылки превышают допустимые лимиты
• Временные проблемы с курьерскими службами

Пожалуйста, проверьте введенные данные или попробуйте позже."""
    
    @staticmethod
    def address_validation_error() -> str:
        """Message for address validation errors"""
        return """❌ Ошибка валидации адресов

ShipStation не смог проверить один или оба адреса.

*Что делать:*
• Проверьте правильность написания адресов
• Убедитесь, что ZIP коды соответствуют городам
• Попробуйте указать более точный адрес

Используйте кнопки ниже для редактирования."""
    
    @staticmethod
    def insufficient_balance() -> str:
        """Message when balance is insufficient"""
        return "❌ Недостаточно средств на балансе."
    
    @staticmethod
    def format_rates_message(rates: list, user_balance: float) -> str:
        """
        Format shipping rates list message
        
        Args:
            rates: List of rate dictionaries
            user_balance: User's current balance
        
        Returns:
            Formatted message string
        """
        from datetime import datetime, timedelta, timezone
        
        # Filter to show only popular rates
        filtered_rates = ShippingRatesUI.filter_popular_rates(rates)
        
        # Group rates by carrier
        rates_by_carrier = {}
        for i, rate in enumerate(filtered_rates):
            carrier = rate['carrier']
            if carrier not in rates_by_carrier:
                rates_by_carrier[carrier] = []
            rates_by_carrier[carrier].append((i, rate))
        
        # Count unique carriers
        unique_carriers = len(set(r['carrier'] for r in filtered_rates))
        
        # Build message
        message = f"📦 Найдено {len(filtered_rates)} тарифов от {unique_carriers} курьеров:\n\n"
        
        # Display rates grouped by carrier
        for carrier in sorted(rates_by_carrier.keys()):
            carrier_icon = ShippingRatesUI.CARRIER_ICONS.get(carrier, '📦')
            message += f"{'='*30}\n<b>{carrier_icon}</b>\n{'='*30}\n\n"
            
            carrier_rates = rates_by_carrier[carrier]
            for idx, rate in carrier_rates:
                days_text = f" ({rate['days']} дней)" if rate['days'] else ""
                
                # Calculate estimated delivery date
                if rate['days']:
                    delivery_date = datetime.now(timezone.utc) + timedelta(days=rate['days'])
                    date_text = f" → {delivery_date.strftime('%d.%m')}"
                else:
                    date_text = ""
                
                message += f"• {rate['service']}{days_text}{date_text}\n  💰 ${rate['amount']:.2f}\n\n"
        
        # Add user balance info
        message += f"\n{'='*30}\n"
        message += f"💰 <b>Ваш баланс: ${user_balance:.2f}</b>\n"
        message += f"{'='*30}\n"
        
        return message
    
    @staticmethod
    def filter_popular_rates(rates: list) -> list:
        """
        Filter rates to show only popular services from top 3 carriers
        
        Popular services:
        - USPS: Priority Mail, Media Mail, First Class, Ground Advantage, Priority Express
        - FedEx: Ground, Home Delivery, 2Day, Express Saver
        - UPS: Ground, 3 Day Select, 2nd Day Air, Next Day Air
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Popular services by carrier
        POPULAR_SERVICES = {
            'USPS': ['priority mail', 'media mail', 'first class', 'ground advantage', 'express'],
            'FedEx': ['ground', 'home delivery', '2day', 'express saver', '2 day'],
            'UPS': ['ground', '3 day select', '2nd day air', 'next day air', 'second day']
        }
        
        filtered = []
        for rate in rates:
            carrier = rate.get('carrier_friendly_name', rate.get('carrier', ''))
            service = rate.get('service_type', rate.get('service', ''))
            
            carrier_lower = carrier.lower()
            service_lower = service.lower()
            
            # Check each carrier
            for popular_carrier, popular_keywords in POPULAR_SERVICES.items():
                if popular_carrier.lower() in carrier_lower:
                    # Check if any popular keyword is in the service name
                    for keyword in popular_keywords:
                        if keyword in service_lower:
                            filtered.append(rate)
                            logger.info(f"✅ Matched: {popular_carrier} - {service}")
                            break  # Found match, move to next rate
                    break  # Carrier identified, move to next rate
        
        logger.info(f"📊 Showing {len(filtered)} popular rates from {len(rates)} total")
        return filtered if filtered else rates  # Return all if no popular rates found
    
    @staticmethod
    def build_rates_keyboard(rates: list) -> InlineKeyboardMarkup:
        """
        Build keyboard with rate selection buttons
        
        Args:
            rates: List of rate dictionaries
        
        Returns:
            InlineKeyboardMarkup with rate buttons
        """
        # Filter to show only popular rates
        filtered_rates = ShippingRatesUI.filter_popular_rates(rates)
        
        keyboard = []
        
        # Add rate selection buttons with cleaned format
        for rate in filtered_rates:
            # Extract carrier name (remove "Stamps.com" prefix if present)
            carrier_full = rate.get('carrier_friendly_name', rate.get('carrier', 'Unknown'))
            carrier_full = carrier_full.replace('Stamps.com ', '').replace('stamps.com ', '')
            
            service = rate.get('service_type', rate.get('service', 'Standard'))
            amount = rate.get('shipping_amount', {}).get('amount', rate.get('amount', 0.0))
            
            # Clean carrier name: extract main carrier (USPS, UPS, FedEx)
            carrier = carrier_full
            for known_carrier in ['USPS', 'UPS', 'FedEx']:
                if known_carrier.lower() in carrier_full.lower():
                    carrier = known_carrier
                    break
            
            # Remove carrier name from service if it's duplicated
            service_clean = service
            if carrier.lower() in service.lower():
                # Remove carrier prefix from service
                service_clean = service.replace(carrier, '').replace(carrier.upper(), '').strip()
            
            # Format: "USPS Media Mail - $12.50"
            button_text = f"{carrier} {service_clean} - ${amount:.2f}"
            
            rate_id = rate.get('rate_id', '')
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f'select_carrier_{rate_id}'
            )])
        
        # Add refresh and cancel buttons
        keyboard.append([InlineKeyboardButton("🔄 Обновить тарифы", callback_data='refresh_rates')])
        keyboard.append([InlineKeyboardButton(ButtonTexts.CANCEL, callback_data=CallbackData.CANCEL_ORDER)])
        
        return InlineKeyboardMarkup(keyboard)


# ============================================================
# LABEL CREATION UI COMPONENTS
# ============================================================

class LabelCreationUI:
    """UI components for shipping label creation"""
    
    @staticmethod
    def creating_label_message() -> str:
        """Progress message while creating label"""
        return "📝 Создаю shipping label..."
    
    @staticmethod
    def success_message(tracking_number: str, carrier: str) -> str:
        """Success message after label creation"""
        return f"""✅ *Label создан успешно!*

📋 *Tracking номер:* `{tracking_number}`
🚚 *Курьер:* {carrier}

Label отправлен вам в виде PDF файла."""
    
    @staticmethod
    def error_message(error: str) -> str:
        """Error message for label creation failure"""
        return f"""❌ *Ошибка при создании label*

*Детали:* {error}

Пожалуйста, попробуйте снова или обратитесь в поддержку."""
    
    @staticmethod
    def insufficient_funds_message(required: float, available: float) -> str:
        """Message when balance is insufficient"""
        deficit = required - available
        return f"""❌ *Недостаточно средств*

💰 *Требуется:* ${required:.2f}
💳 *Доступно:* ${available:.2f}
📉 *Не хватает:* ${deficit:.2f}

Пожалуйста, пополните баланс."""
    
    @staticmethod
    def payment_success_message(amount: float, new_balance: float) -> str:
        """Success message after payment"""
        return f"""✅ *Оплата прошла успешно!*

💰 *Списано:* ${amount:.2f}
💳 *Новый баланс:* ${new_balance:.2f}

Создаю shipping label..."""


# ============================================================
# DATA CONFIRMATION UI COMPONENTS
# ============================================================

class DataConfirmationUI:
    """UI components for order data confirmation screen"""
    
    @staticmethod
    def confirmation_header() -> str:
        """Header for data confirmation"""
        return "📋 *Проверьте введенные данные:*\n\n"
    
    @staticmethod
    def format_address_section(title: str, data: dict, prefix: str) -> str:
        """
        Format address section for confirmation
        
        Args:
            title: Section title (e.g., "Отправитель", "Получатель")
            data: Context user_data dict
            prefix: Field prefix ('from' or 'to')
        
        Returns:
            Formatted address section string
        """
        name = data.get(f'{prefix}_name', '')
        street = data.get(f'{prefix}_street', '')
        street2 = data.get(f'{prefix}_street2', '')
        city = data.get(f'{prefix}_city', '')
        state = data.get(f'{prefix}_state', '')
        zip_code = data.get(f'{prefix}_zip', '')
        phone = data.get(f'{prefix}_phone', '')
        
        section = f"*{title}:*\n"
        section += f"👤 {name}\n"
        section += f"📍 {street}\n"
        if street2:
            section += f"   {street2}\n"
        section += f"🏙 {city}, {state} {zip_code}\n"
        if phone:
            section += f"📞 {phone}\n"
        section += "\n"
        
        return section
    
    @staticmethod
    def format_parcel_section(data: dict) -> str:
        """
        Format parcel information section
        
        Args:
            data: Context user_data dict
        
        Returns:
            Formatted parcel section string
        """
        weight = data.get('weight', '')
        length = data.get('length', '')
        width = data.get('width', '')
        height = data.get('height', '')
        
        section = "*Посылка:*\n"
        section += f"⚖️ Вес: {weight} lb\n"
        
        if length and width and height:
            section += f"📏 Размеры: {length}\" × {width}\" × {height}\"\n"
        
        return section
    
    @staticmethod
    def build_confirmation_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard for data confirmation screen"""
        keyboard = [
            [InlineKeyboardButton("✅ Всё верно, показать тарифы", callback_data='show_rates')],
            [InlineKeyboardButton("✏️ Редактировать данные", callback_data='edit_data')],
            [InlineKeyboardButton("💾 Сохранить как шаблон", callback_data='save_as_template')],
            [InlineKeyboardButton(ButtonTexts.CANCEL, callback_data=CallbackData.CANCEL_ORDER)]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_edit_menu_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard for edit menu"""
        keyboard = [
            [InlineKeyboardButton("📤 Адрес отправителя", callback_data='edit_from_address')],
            [InlineKeyboardButton("📥 Адрес получателя", callback_data='edit_to_address')],
            [InlineKeyboardButton("📦 Посылка", callback_data='edit_parcel')],
            [InlineKeyboardButton("◀️ Назад", callback_data='back_to_confirmation')]
        ]
        return InlineKeyboardMarkup(keyboard)



# ============================================================
# PAYMENT FLOW UI COMPONENTS
# ============================================================

class PaymentFlowUI:
    """UI components for payment and balance management"""
    
    @staticmethod
    def balance_screen(balance: float) -> str:
        """Display current balance with topup prompt"""
        return f"""*💳 Ваш баланс: ${balance:.2f}*

*Вы можете использовать баланс для оплаты заказов.*

*Введите сумму для пополнения (минимум $10):*"""
    
    @staticmethod
    def insufficient_balance_error() -> str:
        """Error when balance is too low"""
        return "❌ Недостаточно средств на балансе."
    
    @staticmethod
    def payment_success_balance(amount: float, new_balance: float, order_id: str = None) -> str:
        """Success message after paying from balance"""
        from utils.order_utils import format_order_id_for_display
        
        order_info = ""
        if order_id:
            display_id = format_order_id_for_display(order_id)
            order_info = f"📦 Номер заказа: #{display_id}\n\n"
        
        return f"""✅ Заказ оплачен с баланса!

{order_info}💳 Списано: ${amount:.2f}
💰 Новый баланс: ${new_balance:.2f}

Label будет создан и отправлен вам в течение минуты."""
    
    @staticmethod
    def topup_amount_too_small() -> str:
        """Error for minimum topup amount"""
        return "❌ *Минимальная сумма для пополнения: $10*"
    
    @staticmethod
    def topup_amount_too_large() -> str:
        """Error for maximum topup amount"""
        return "❌ *Максимальная сумма для пополнения: $10,000*"
    
    @staticmethod
    def topup_invalid_format() -> str:
        """Error for invalid number format"""
        return "❌ *Неверный формат. Введите число (например: 10 или 25.50)*"
    
    @staticmethod
    def topup_invoice_error(error_msg: str) -> str:
        """Error creating payment invoice"""
        return f"❌ *Ошибка создания инвойса:* {error_msg}"
    
    @staticmethod
    def topup_payment_link(amount: float, pay_link: str) -> str:
        """Payment link message for topup"""
        return f"""💳 Ссылка для оплаты ${amount:.2f}:

{pay_link}

После оплаты средства будут зачислены автоматически."""
    
    @staticmethod
    def topup_crypto_selection(amount: float) -> str:
        """Crypto selection message"""
        return f"""💰 Выберите криптовалюту для пополнения на ${amount:.2f}:"""
    
    @staticmethod
    def payment_method_selection(amount: float, balance: float) -> str:
        """Payment method selection screen"""
        if balance >= amount:
            return f"""💳 Выберите способ оплаты:

Сумма к оплате: ${amount:.2f}
Ваш баланс: ${balance:.2f}"""
        else:
            deficit = amount - balance
            return f"""💳 Выберите способ оплаты:

Сумма к оплате: ${amount:.2f}
Ваш баланс: ${balance:.2f}
Не хватает: ${deficit:.2f}"""
    
    @staticmethod
    def build_balance_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for balance screen"""
        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data='start')],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_crypto_selection_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for cryptocurrency selection"""
        keyboard = [
            [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data='crypto_btc')],
            [InlineKeyboardButton("Ξ Ethereum (ETH)", callback_data='crypto_eth')],
            [InlineKeyboardButton("₮ Tether (USDT)", callback_data='crypto_usdt')],
            [InlineKeyboardButton("Ł Litecoin (LTC)", callback_data='crypto_ltc')],
            [InlineKeyboardButton("❌ Отмена", callback_data='start')]
        ]
        return InlineKeyboardMarkup(keyboard)



# ============================================================
# TEMPLATE MANAGEMENT UI COMPONENTS
# ============================================================

class TemplateManagementUI:
    """UI components for template management"""
    
    @staticmethod
    def no_templates_message() -> str:
        """Message when user has no templates"""
        return """📋 *Мои шаблоны*

У вас пока нет сохраненных шаблонов.
Создайте заказ и нажмите "*Сохранить как шаблон*" на экране проверки данных."""
    
    @staticmethod
    def templates_list_header() -> str:
        """Header for templates list"""
        return "📋 *Выберите шаблон:*\n\n"
    
    @staticmethod
    def format_template_item(index: int, template: dict) -> str:
        """Format single template item in list"""
        from_name = template.get('from_name', '')
        from_street = template.get('from_street1', '')
        from_city = template.get('from_city', '')
        from_state = template.get('from_state', '')
        from_zip = template.get('from_zip', '')
        to_name = template.get('to_name', '')
        to_street = template.get('to_street1', '')
        to_city = template.get('to_city', '')
        to_state = template.get('to_state', '')
        to_zip = template.get('to_zip', '')
        
        return f"""*{index}. {template['name']}*
📤 От: {from_name}
   {from_street}, {from_city}, {from_state} {from_zip}
📥 Кому: {to_name}
   {to_street}, {to_city}, {to_state} {to_zip}

"""
    
    @staticmethod
    def template_saved_success(template_name: str) -> str:
        """Success message after saving template"""
        return f"""✅ *Шаблон сохранён!*

Название: *{template_name}*

Вы можете использовать этот шаблон для создания заказов в будущем."""
    
    @staticmethod
    def template_name_prompt() -> str:
        """Prompt to enter template name"""
        return "💾 *Введите название для шаблона:*"
    
    @staticmethod
    def template_deleted_success(template_name: str) -> str:
        """Success message after deleting template"""
        return f"""✅ *Шаблон удалён*

Шаблон "{template_name}" был успешно удалён."""
    
    @staticmethod
    def template_rename_prompt(current_name: str) -> str:
        """Prompt to rename template"""
        return f"""✏️ *Переименование шаблона*

Текущее название: *{current_name}*

Введите новое название:"""
    
    @staticmethod
    def template_renamed_success(old_name: str, new_name: str) -> str:
        """Success message after renaming"""
        return f"""✅ *Шаблон переименован*

*{old_name}* → *{new_name}*"""
    
    @staticmethod
    def confirm_delete_template(template_name: str) -> str:
        """Confirmation message for template deletion"""
        return f"""❓ *Удалить шаблон?*

Шаблон: *{template_name}*

Это действие нельзя отменить."""
    
    @staticmethod
    def build_no_templates_keyboard() -> InlineKeyboardMarkup:
        """Keyboard when no templates exist"""
        keyboard = [
            [InlineKeyboardButton("📦 Создать заказ", callback_data='new_order')],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_template_view_keyboard(template_id: str) -> InlineKeyboardMarkup:
        """Keyboard for viewing a single template"""
        keyboard = [
            [InlineKeyboardButton("📦 Использовать шаблон", callback_data=f'use_template_{template_id}')],
            [InlineKeyboardButton("✏️ Переименовать", callback_data=f'rename_template_{template_id}')],
            [InlineKeyboardButton("🗑 Удалить", callback_data=f'delete_template_{template_id}')],
            [InlineKeyboardButton("◀️ Назад к списку", callback_data='my_templates')]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_confirm_delete_keyboard(template_id: str) -> InlineKeyboardMarkup:
        """Keyboard for confirming template deletion"""
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_{template_id}')],
            [InlineKeyboardButton("❌ Отмена", callback_data=f'template_view_{template_id}')]
        ]
        return InlineKeyboardMarkup(keyboard)

