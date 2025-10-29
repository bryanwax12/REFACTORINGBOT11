from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import requests
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import asyncio
from aiocryptopay import AioCryptoPay, Networks

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# ShipStation API
SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY', '')
SHIPSTATION_CARRIER_IDS = []  # Cache for carrier IDs

# Admin notifications
ADMIN_TELEGRAM_ID = os.environ.get('ADMIN_TELEGRAM_ID', '')

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
bot_instance = None
if TELEGRAM_BOT_TOKEN:
    bot_instance = Bot(token=TELEGRAM_BOT_TOKEN)

# CryptoBot
CRYPTOBOT_TOKEN = os.environ.get('CRYPTOBOT_TOKEN', '')
crypto = None
if CRYPTOBOT_TOKEN:
    crypto = AioCryptoPay(token=CRYPTOBOT_TOKEN, network=Networks.MAIN_NET)

app = FastAPI(title="Telegram Shipping Bot")
api_router = APIRouter(prefix="/api")

# Models
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    balance: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Address(BaseModel):
    name: str
    street1: str
    street2: Optional[str] = None
    city: str
    state: str
    zip: str
    country: str = "US"
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class Parcel(BaseModel):
    length: float
    width: float
    height: float
    weight: float
    distance_unit: str = "in"
    mass_unit: str = "lb"

class ShippingLabel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    tracking_number: Optional[str] = None
    label_url: Optional[str] = None
    carrier: Optional[str] = None
    service_level: Optional[str] = None
    amount: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    amount: float
    currency: str = "USDT"
    status: str = "pending"
    invoice_id: Optional[int] = None
    pay_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    telegram_id: int
    address_from: Address
    address_to: Address
    parcel: Parcel
    amount: float
    payment_status: str = "pending"
    shipping_status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OrderCreate(BaseModel):
    telegram_id: int
    address_from: Address
    address_to: Address
    parcel: Parcel
    amount: float

# Telegram Bot Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        telegram_id = query.from_user.id
        username = query.from_user.username
        first_name = query.from_user.first_name
        send_method = query.message.reply_text
    else:
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        send_method = update.message.reply_text
    
    existing_user = await db.users.find_one({"telegram_id": telegram_id})
    
    if not existing_user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
        user_dict = user.model_dump()
        user_dict['created_at'] = user_dict['created_at'].isoformat()
        await db.users.insert_one(user_dict)
        
    welcome_message = f"""Добро пожаловать, {first_name}! 🚀

Я помогу вам создать shipping labels с оплатой в криптовалюте.

Выберите действие:"""
    
    # Create keyboard with buttons (2 buttons per row)
    keyboard = [
        [
            InlineKeyboardButton("📦 Создать заказ", callback_data='new_order'),
            InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')
        ],
        [
            InlineKeyboardButton("💳 Мой баланс", callback_data='my_balance'),
            InlineKeyboardButton("🔍 Отследить", callback_data='track')
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data='help')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_method(welcome_message, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send_method = query.message.reply_text
    else:
        send_method = update.message.reply_text
    
    help_text = """📦 Доступные команды:

/start - Начать работу
/my_orders - Посмотреть мои заказы
/track - Отследить посылку
/help - Показать эту справку

Для создания заказа используйте веб-панель или API."""
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_method(help_text, reply_markup=reply_markup)

async def my_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        telegram_id = query.from_user.id
        send_method = query.message.reply_text
    else:
        telegram_id = update.effective_user.id
        send_method = update.message.reply_text
    
    orders = await db.orders.find(
        {"telegram_id": telegram_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    if not orders:
        keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_method("У вас пока нет заказов. Создайте первый заказ через /start → 📦 Новый заказ.", reply_markup=reply_markup)
        return
    
    message = "📦 Ваши последние заказы:\n\n"
    keyboard = []
    
    for i, order in enumerate(orders, 1):
        status_emoji = "✅" if order['payment_status'] == 'paid' else "⏳"
        ship_emoji = "📮" if order['shipping_status'] == 'label_created' else "📦"
        
        # Get recipient name from order data
        recipient_name = order.get('address_to', {}).get('name', 'Не указано')
        
        message += f"""{i}. {status_emoji} Заказ #{order['id'][:8]}
👤 Получатель: {recipient_name}
💰 Оплата: {order['payment_status']}
{ship_emoji} Доставка: {order['shipping_status']}
💵 Сумма: ${order['amount']}
📅 {order.get('created_at', '')[:10]}
"""
        
        # Add button ONLY for orders with label already created (to recreate)
        if order['payment_status'] == 'paid' and order['shipping_status'] == 'label_created':
            keyboard.append([InlineKeyboardButton(
                f"🔄 Пересоздать лейбл для #{order['id'][:8]} ({recipient_name})", 
                callback_data=f"create_label_{order['id']}"
            )])
        
        message += "---\n"
    
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_method(message, reply_markup=reply_markup)

async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send_method = query.message.reply_text
    else:
        send_method = update.message.reply_text
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_method(
        "Для отслеживания посылки используйте веб-панель или укажите tracking number.",
        reply_markup=reply_markup
    )


async def handle_create_label_request(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str):
    """Handle request to create/recreate shipping label for existing paid order"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    # Get order details
    order = await db.orders.find_one({"id": order_id, "telegram_id": telegram_id}, {"_id": 0})
    
    if not order:
        await query.message.reply_text("❌ Заказ не найден.")
        return
    
    if order['payment_status'] != 'paid':
        await query.message.reply_text("❌ Заказ не оплачен. Создание лейбла невозможно.")
        return
    
    # Show confirmation message
    if order['shipping_status'] == 'label_created':
        await query.message.reply_text(f"""⏳ Пересоздаю shipping label для заказа #{order_id[:8]}...
    
Это может занять несколько секунд.""")
    else:
        await query.message.reply_text(f"""⏳ Создаю shipping label для заказа #{order_id[:8]}...
    
Это может занять несколько секунд.""")
    
    # Try to create label
    label_created = await create_and_send_label(order_id, telegram_id, query.message)
    
    if label_created:
        # Update order payment status to paid (if it was failed before)
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"payment_status": "paid"}}
        )
        
        keyboard = [[
            InlineKeyboardButton("📦 Мои заказы", callback_data='my_orders'),
            InlineKeyboardButton("🔙 Главное меню", callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "✅ Shipping label успешно создан!",
            reply_markup=reply_markup
        )
    else:
        keyboard = [[
            InlineKeyboardButton("📦 Мои заказы", callback_data='my_orders'),
            InlineKeyboardButton("🔙 Главное меню", callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "❌ Не удалось создать shipping label. Пожалуйста, свяжитесь с администратором.",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'start':
        await start_command(update, context)
    elif query.data == 'my_orders':
        await my_orders_command(update, context)
    elif query.data == 'my_balance':
        await my_balance_command(update, context)
    elif query.data == 'track':
        await track_command(update, context)
    elif query.data == 'help':
        await help_command(update, context)
    elif query.data == 'new_order':
        await new_order_start(update, context)
    elif query.data == 'cancel_order':
        await cancel_order(update, context)
    elif query.data.startswith('create_label_'):
        # Handle create label button
        order_id = query.data.replace('create_label_', '')
        await handle_create_label_request(update, context, order_id)

async def my_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        telegram_id = query.from_user.id
        send_method = query.message.reply_text
    else:
        telegram_id = update.effective_user.id
        send_method = update.message.reply_text
    
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    balance = user.get('balance', 0.0) if user else 0.0
    
    message = f"""💳 Ваш баланс: ${balance:.2f}

Вы можете использовать баланс для оплаты заказов.

Хотите пополнить баланс?"""
    
    keyboard = [
        [
            InlineKeyboardButton("💵 $10", callback_data='topup_10'),
            InlineKeyboardButton("💵 $25", callback_data='topup_25')
        ],
        [
            InlineKeyboardButton("💵 $50", callback_data='topup_50'),
            InlineKeyboardButton("💵 $100", callback_data='topup_100')
        ],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_method(message, reply_markup=reply_markup)

async def handle_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    topup_amount = float(query.data.split('_')[1])
    telegram_id = query.from_user.id
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    
    if crypto:
        invoice = await crypto.create_invoice(
            asset="USDT",
            amount=topup_amount
        )
        
        pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'mini_app_invoice_url', None)
        
        # Save top-up payment
        payment = Payment(
            order_id=f"topup_{user['id']}",
            amount=topup_amount,
            invoice_id=invoice.invoice_id,
            pay_url=pay_url,
            currency="USDT",
            status="pending"
        )
        payment_dict = payment.model_dump()
        payment_dict['created_at'] = payment_dict['created_at'].isoformat()
        payment_dict['telegram_id'] = telegram_id
        payment_dict['type'] = 'topup'
        await db.payments.insert_one(payment_dict)
        
        keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            f"""💵 Пополнение баланса

💰 Оплатите ${topup_amount} USDT:
{pay_url}

После оплаты баланс будет пополнен автоматически.""",
            reply_markup=reply_markup
        )

# Conversation states for order creation
FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, FROM_STATE, FROM_ZIP, FROM_PHONE, TO_NAME, TO_ADDRESS, TO_ADDRESS2, TO_CITY, TO_STATE, TO_ZIP, TO_PHONE, PARCEL_WEIGHT, CONFIRM_DATA, EDIT_MENU, SELECT_CARRIER, PAYMENT_METHOD, TOPUP_AMOUNT = range(20)

async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        """📦 Создание нового заказа

Шаг 1/11: Имя отправителя
Например: John Smith""",
        reply_markup=reply_markup
    )
    return FROM_NAME

async def order_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in name):
        await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: John Smith")
        return FROM_NAME
    
    # Validate name
    if len(name) < 2:
        await update.message.reply_text("❌ Имя слишком короткое. Введите полное имя (минимум 2 символа):")
        return FROM_NAME
    
    if len(name) > 50:
        await update.message.reply_text("❌ Имя слишком длинное. Максимум 50 символов:")
        return FROM_NAME
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in name):
        await update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки")
        return FROM_NAME
    
    context.user_data['from_name'] = name
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 2/13: Адрес отправителя
Например: 215 Clayton St.""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = FROM_ADDRESS  # Save state for next step
    return FROM_ADDRESS

async def order_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    
    # Debug logging
    logger.info(f"Address validation: '{address}' length={len(address)} bytes={address.encode()}")
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address):
        await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: 215 Clayton St")
        return FROM_ADDRESS
    
    # Validate address
    if len(address) < 3:
        await update.message.reply_text("❌ Адрес слишком короткий. Введите полный адрес:")
        return FROM_ADDRESS
    
    if len(address) > 100:
        await update.message.reply_text("❌ Адрес слишком длинный. Максимум 100 символов:")
        return FROM_ADDRESS
    
    # Only Latin letters, numbers, spaces, and common address symbols
    invalid_chars = [c for c in address if not (ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/&"))]
    if invalid_chars:
        invalid_display = ', '.join([f"'{c}'" for c in set(invalid_chars)])
        logger.warning(f"Invalid characters in address: {invalid_chars} (ords: {[ord(c) for c in invalid_chars]})")
        await update.message.reply_text(
            f"❌ Найдены недопустимые символы: {invalid_display}\n\n"
            f"Используйте только:\n"
            f"• Английские буквы (A-Z, a-z)\n"
            f"• Цифры (0-9)\n"
            f"• Пробелы\n"
            f"• Спецсимволы: . - , ' # / &"
        )
        return FROM_ADDRESS
    
    context.user_data['from_street'] = address
    
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_from_address2')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 3/13: Квартира/Офис отправителя (необязательно)
Например: Apt 5, Suite 201
Или нажмите "Пропустить" """,
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = FROM_ADDRESS2  # Save state for next step
    return FROM_ADDRESS2

async def order_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        address2 = update.message.text.strip()
        
        # Check for Cyrillic or non-Latin characters
        if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address2):
            await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: Apt 5, Suite 201")
            return FROM_ADDRESS2
        
        # Only Latin letters, numbers, spaces, and common address symbols
        if not all((ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/")) for c in address2):
            await update.message.reply_text("❌ Используйте только английские буквы и цифры. Разрешены: буквы, цифры, пробелы, дефисы, точки, запятые")
            return FROM_ADDRESS2
        
        context.user_data['from_street2'] = address2
    else:
        context.user_data['from_street2'] = None
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await (update.message or update.callback_query.message).reply_text(
        """Шаг 4/13: Город отправителя
Например: San Francisco""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = FROM_CITY  # Save state for next step
    return FROM_CITY

async def skip_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['from_street2'] = None
    return await order_from_address2(update, context)

async def order_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in city):
        await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: San Francisco")
        return FROM_CITY
    
    # Validate city
    if len(city) < 2:
        await update.message.reply_text("❌ Название города слишком короткое:")
        return FROM_CITY
    
    if len(city) > 50:
        await update.message.reply_text("❌ Название города слишком длинное. Максимум 50 символов:")
        return FROM_CITY
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in city):
        await update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки")
        return FROM_CITY
    
    context.user_data['from_city'] = city
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 5/13: Штат отправителя (2 буквы)
Например: CA""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = FROM_STATE  # Save state for next step
    return FROM_STATE

async def order_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = update.message.text.strip().upper()
    
    # Validate state
    if len(state) != 2:
        await update.message.reply_text("❌ Код штата должен быть ровно 2 буквы. Например: CA, NY, TX:")
        return FROM_STATE
    
    if not state.isalpha():
        await update.message.reply_text("❌ Код штата должен содержать только буквы:")
        return FROM_STATE
    
    # Valid US state codes
    valid_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'DC', 'PR', 'VI', 'GU'
    }
    
    if state not in valid_states:
        await update.message.reply_text("❌ Неверный код штата. Введите корректный код (например: CA, NY, TX):")
        return FROM_STATE
    
    context.user_data['from_state'] = state
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 6/13: ZIP код отправителя
Например: 94117""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = FROM_ZIP  # Save state for next step
    return FROM_ZIP


async def get_shipstation_carrier_ids():
    """Get and cache ShipStation carrier IDs"""
    global SHIPSTATION_CARRIER_IDS
    
    # Return cached IDs if available
    if SHIPSTATION_CARRIER_IDS:
        return SHIPSTATION_CARRIER_IDS
    
    try:
        if not SHIPSTATION_API_KEY:
            logger.error("ShipStation API key not configured")
            return []
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            'https://api.shipstation.com/v2/carriers',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            carriers = data.get('carriers', [])
            
            # Exclude specific carriers: GlobalPost, Stamps.com
            excluded_carriers = ['globalpost', 'stamps_com', 'stamps']
            
            # Extract carrier IDs from active carriers, excluding unwanted ones
            carrier_ids = [
                c['carrier_id'] 
                for c in carriers 
                if c.get('carrier_id') and c.get('carrier_code', '').lower() not in excluded_carriers
            ]
            
            SHIPSTATION_CARRIER_IDS = carrier_ids
            logger.info(f"Loaded {len(carrier_ids)} ShipStation carriers (excluded: {excluded_carriers}): {carrier_ids}")
            return carrier_ids
        else:
            logger.error(f"Failed to get carriers: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting carrier IDs: {e}")
        return []


async def validate_address_with_shipstation(name, street1, street2, city, state, zip_code):
    """Validate address using ShipStation API V2
    Note: ShipStation V2 does not have address validation endpoint,
    so we always return valid to allow order to proceed
    """
    try:
        # ShipStation V2 doesn't have address validation
        # Return success to allow order creation
        logger.info(f"Address validation skipped (not available in ShipStation V2): {street1}, {city}, {state} {zip_code}")
        return {
            'is_valid': True,
            'message': 'Адрес принят (валидация недоступна в ShipStation)'
        }
            
    except Exception as e:
        logger.error(f"Error validating address: {e}")
        return {
            'is_valid': True,  # Fallback to allow order if validation fails
            'message': 'Проверка недоступна, продолжаем'
        }

async def notify_admin_error(user_info: dict, error_type: str, error_details: str, order_id: str = None):
    """Send error notification to admin"""
    if not ADMIN_TELEGRAM_ID or not bot_instance:
        return
    
    try:
        username = user_info.get('username', 'N/A')
        telegram_id = user_info.get('telegram_id', 'N/A')
        first_name = user_info.get('first_name', 'N/A')
        
        message = f"""🚨 <b>ОШИБКА В БОТЕ</b> 🚨

👤 <b>Пользователь:</b>
   • ID: {telegram_id}
   • Имя: {first_name}
   • Username: @{username if username != 'N/A' else 'не указан'}

❌ <b>Тип ошибки:</b> {error_type}

📋 <b>Детали:</b>
{error_details}
"""
        
        if order_id:
            message += f"\n🔖 <b>Order ID:</b> {order_id}"
        
        await bot_instance.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=message,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

async def order_from_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zip_code = update.message.text.strip()
    
    # Validate ZIP code
    import re
    # US ZIP format: 5 digits or 5-4 digits
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        await update.message.reply_text("❌ Неверный формат ZIP кода. Используйте формат: 12345 или 12345-6789:")
        return FROM_ZIP
    
    context.user_data['from_zip'] = zip_code
    
    # Check if we're editing from address
    if context.user_data.get('editing_from_address'):
        context.user_data['editing_from_address'] = False
        await update.message.reply_text("✅ Адрес отправителя обновлен!")
        return await show_data_confirmation(update, context)
    
    keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data='skip_from_phone')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 7/13: Телефон отправителя
Например: +1234567890 или 1234567890""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = FROM_PHONE  # Save state for next step
    return FROM_PHONE

async def order_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's a callback query (skip phone button)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'skip_from_phone':
            # Skip phone - set empty or default value
            context.user_data['from_phone'] = ''
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                """Шаг 8/13: Имя получателя
Например: Jane Doe""",
                reply_markup=reply_markup
            )
            context.user_data['last_state'] = TO_NAME  # Save state for next step
            return TO_NAME
    
    phone = update.message.text.strip()
    
    # Check if phone starts with valid characters (+ or digit)
    if not phone or (phone[0] not in '0123456789+'):
        await update.message.reply_text("❌ Неверный формат телефона. Телефон должен начинаться с + или цифры\nНапример: +1234567890 или 1234567890")
        return FROM_PHONE
    
    # Validate phone format
    import re
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a valid US phone number (10 or 11 digits)
    if len(digits_only) < 10 or len(digits_only) > 11:
        await update.message.reply_text("❌ Неверный формат телефона. Введите 10 цифр (например: 1234567890):")
        return FROM_PHONE
    
    # Format phone number
    if len(digits_only) == 11 and digits_only[0] == '1':
        formatted_phone = f"+{digits_only}"
    elif len(digits_only) == 10:
        formatted_phone = f"+1{digits_only}"
    else:
        formatted_phone = f"+{digits_only}"
    
    context.user_data['from_phone'] = formatted_phone
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 8/13: Имя получателя
Например: Jane Doe""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = TO_NAME  # Save state for next step
    return TO_NAME

async def order_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in name):
        await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: John Smith")
        return TO_NAME
    
    # Validate name
    if len(name) < 2:
        await update.message.reply_text("❌ Имя слишком короткое. Введите полное имя (минимум 2 символа):")
        return TO_NAME
    
    if len(name) > 50:
        await update.message.reply_text("❌ Имя слишком длинное. Максимум 50 символов:")
        return TO_NAME
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in name):
        await update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки")
        return TO_NAME
    
    context.user_data['to_name'] = name
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        await update.message.reply_text(
            """Шаг 2/6: Адрес получателя
Например: 123 Main St.""",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            """Шаг 9/13: Адрес получателя
Например: 123 Main St.""",
            reply_markup=reply_markup
        )
    context.user_data['last_state'] = TO_ADDRESS  # Save state for next step
    return TO_ADDRESS

async def order_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address):
        await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: 123 Main St")
        return TO_ADDRESS
    
    # Validate address
    if len(address) < 3:
        await update.message.reply_text("❌ Адрес слишком короткий. Введите полный адрес:")
        return TO_ADDRESS
    
    if len(address) > 100:
        await update.message.reply_text("❌ Адрес слишком длинный. Максимум 100 символов:")
        return TO_ADDRESS
    
    # Only Latin letters, numbers, spaces, and common address symbols
    invalid_chars = [c for c in address if not (ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/&"))]
    if invalid_chars:
        invalid_display = ', '.join([f"'{c}'" for c in set(invalid_chars)])
        await update.message.reply_text(
            f"❌ Найдены недопустимые символы: {invalid_display}\n\n"
            f"Используйте только:\n"
            f"• Английские буквы (A-Z, a-z)\n"
            f"• Цифры (0-9)\n"
            f"• Пробелы\n"
            f"• Спецсимволы: . - , ' # / &"
        )
        return TO_ADDRESS
    
    context.user_data['to_street'] = address
    
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_to_address2')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        await update.message.reply_text(
            """Шаг 3/6: Квартира/Офис получателя (необязательно)
Например: Apt 12, Suite 305
Или нажмите "Пропустить" """,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            """Шаг 10/13: Квартира/Офис получателя (необязательно)
Например: Apt 12, Suite 305
Или нажмите "Пропустить" """,
            reply_markup=reply_markup
        )
    context.user_data['last_state'] = TO_ADDRESS2  # Save state for next step
    return TO_ADDRESS2

async def order_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        address2 = update.message.text.strip()
        
        # Check for Cyrillic or non-Latin characters
        if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address2):
            await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: Apt 12, Suite 305")
            return TO_ADDRESS2
        
        # Only Latin letters, numbers, spaces, and common address symbols
        if not all((ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/")) for c in address2):
            await update.message.reply_text("❌ Используйте только английские буквы и цифры. Разрешены: буквы, цифры, пробелы, дефисы, точки, запятые")
            return TO_ADDRESS2
        
        context.user_data['to_street2'] = address2
    else:
        context.user_data['to_street2'] = None
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        await (update.message or update.callback_query.message).reply_text(
            """Шаг 4/6: Город получателя
Например: New York""",
            reply_markup=reply_markup
        )
    else:
        await (update.message or update.callback_query.message).reply_text(
            """Шаг 11/13: Город получателя
Например: New York""",
            reply_markup=reply_markup
        )
    context.user_data['last_state'] = TO_CITY  # Save state for next step
    return TO_CITY

async def skip_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['to_street2'] = None
    return await order_to_address2(update, context)

async def order_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in city):
        await update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: New York")
        return TO_CITY
    
    # Validate city
    if len(city) < 2:
        await update.message.reply_text("❌ Название города слишком короткое:")
        return TO_CITY
    
    if len(city) > 50:
        await update.message.reply_text("❌ Название города слишком длинное. Максимум 50 символов:")
        return TO_CITY
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in city):
        await update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки")
        return TO_CITY
    
    context.user_data['to_city'] = city
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 11/13: Штат получателя (2 буквы)
Например: NY""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = TO_STATE  # Save state for next step
    return TO_STATE

async def order_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = update.message.text.strip().upper()
    
    # Validate state
    if len(state) != 2:
        await update.message.reply_text("❌ Код штата должен быть ровно 2 буквы. Например: CA, NY, TX:")
        return TO_STATE
    
    if not state.isalpha():
        await update.message.reply_text("❌ Код штата должен содержать только буквы:")
        return TO_STATE
    
    # Valid US state codes
    valid_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'DC', 'PR', 'VI', 'GU'
    }
    
    if state not in valid_states:
        await update.message.reply_text("❌ Неверный код штата. Введите корректный код (например: CA, NY, TX):")
        return TO_STATE
    
    context.user_data['to_state'] = state
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 12/13: ZIP код получателя
Например: 10007""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = TO_ZIP  # Save state for next step
    return TO_ZIP

async def order_to_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zip_code = update.message.text.strip()
    
    # Validate ZIP code
    import re
    # US ZIP format: 5 digits or 5-4 digits
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        await update.message.reply_text("❌ Неверный формат ZIP кода. Используйте формат: 12345 или 12345-6789:")
        return TO_ZIP
    
    context.user_data['to_zip'] = zip_code
    
    # Check if we're editing to address
    if context.user_data.get('editing_to_address'):
        context.user_data['editing_to_address'] = False
        await update.message.reply_text("✅ Адрес получателя обновлен!")
        return await show_data_confirmation(update, context)
    
    keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data='skip_to_phone')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 14/15: Телефон получателя
Например: +1234567890 или 1234567890""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = TO_PHONE  # Save state for next step
    return TO_PHONE

async def order_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's a callback query (skip phone button)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'skip_to_phone':
            # Skip phone - set empty or default value
            context.user_data['to_phone'] = ''
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                """Шаг 15/15: Вес посылки в фунтах (lb)
Например: 2""",
                reply_markup=reply_markup
            )
            context.user_data['last_state'] = PARCEL_WEIGHT  # Save state for next step
            return PARCEL_WEIGHT
    
    phone = update.message.text.strip()
    
    # Check if phone starts with valid characters (+ or digit)
    if not phone or (phone[0] not in '0123456789+'):
        await update.message.reply_text("❌ Неверный формат телефона. Телефон должен начинаться с + или цифры\nНапример: +1234567890 или 1234567890")
        return TO_PHONE
    
    # Validate phone format
    import re
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a valid US phone number (10 or 11 digits)
    if len(digits_only) < 10 or len(digits_only) > 11:
        await update.message.reply_text("❌ Неверный формат телефона. Введите 10 цифр (например: 1234567890):")
        return TO_PHONE
    
    # Format phone number
    if len(digits_only) == 11 and digits_only[0] == '1':
        formatted_phone = f"+{digits_only}"
    elif len(digits_only) == 10:
        formatted_phone = f"+1{digits_only}"
    else:
        formatted_phone = f"+{digits_only}"
    
    context.user_data['to_phone'] = formatted_phone
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 15/15: Вес посылки в фунтах (lb)
Например: 2""",
        reply_markup=reply_markup
    )
    context.user_data['last_state'] = PARCEL_WEIGHT  # Save state for next step
    return PARCEL_WEIGHT

async def order_parcel_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.strip())
        
        if weight <= 0:
            await update.message.reply_text("❌ Вес должен быть больше 0. Попробуйте еще раз:")
            return PARCEL_WEIGHT
        
        if weight > 150:
            await update.message.reply_text("❌ Вес слишком большой. Максимум 150 фунтов. Попробуйте еще раз:")
            return PARCEL_WEIGHT
        
        context.user_data['weight'] = weight
        
        # Check if we're editing parcel weight
        if context.user_data.get('editing_parcel'):
            context.user_data['editing_parcel'] = False
            await update.message.reply_text("✅ Вес посылки обновлен!")
        
        # Show data confirmation instead of immediately fetching rates
        context.user_data['last_state'] = CONFIRM_DATA  # Save state for next step
        return await show_data_confirmation(update, context)
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введите число (например: 2 или 2.5):")
        return PARCEL_WEIGHT


async def show_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show summary of entered data with edit option"""
    data = context.user_data
    
    # Format the summary message
    message = "📋 Проверьте введенные данные:\n\n"
    message += "📤 ОТПРАВИТЕЛЬ:\n"
    message += f"   Имя: {data.get('from_name')}\n"
    message += f"   Адрес: {data.get('from_street')}\n"
    if data.get('from_street2'):
        message += f"   Квартира: {data.get('from_street2')}\n"
    message += f"   Город: {data.get('from_city')}\n"
    message += f"   Штат: {data.get('from_state')}\n"
    message += f"   ZIP: {data.get('from_zip')}\n"
    message += f"   Телефон: {data.get('from_phone')}\n\n"
    
    message += "📥 ПОЛУЧАТЕЛЬ:\n"
    message += f"   Имя: {data.get('to_name')}\n"
    message += f"   Адрес: {data.get('to_street')}\n"
    if data.get('to_street2'):
        message += f"   Квартира: {data.get('to_street2')}\n"
    message += f"   Город: {data.get('to_city')}\n"
    message += f"   Штат: {data.get('to_state')}\n"
    message += f"   ZIP: {data.get('to_zip')}\n"
    message += f"   Телефон: {data.get('to_phone')}\n\n"
    
    message += "📦 ПОСЫЛКА:\n"
    message += f"   Вес: {data.get('weight')} фунтов\n"
    
    keyboard = [
        [InlineKeyboardButton("✅ Всё верно, показать тарифы", callback_data='confirm_data')],
        [InlineKeyboardButton("✏️ Редактировать данные", callback_data='edit_data')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if it's a message or callback query
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)
    
    context.user_data['last_state'] = CONFIRM_DATA  # Save state for cancel return
    return CONFIRM_DATA

async def handle_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's choice on data confirmation"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel_order':
        await cancel_order(update, context)
        return ConversationHandler.END
    
    if query.data == 'confirm_data':
        # User confirmed data, proceed to fetch rates
        return await fetch_shipping_rates(update, context)
    
    if query.data == 'edit_data':
        # Show edit menu
        return await show_edit_menu(update, context)
    
    if query.data == 'edit_addresses_error':
        # Show edit menu after rate error
        return await show_edit_menu(update, context)

async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu to select what to edit"""
    query = update.callback_query
    
    message = "✏️ Что вы хотите изменить?"
    
    keyboard = [
        [InlineKeyboardButton("📤 Адрес отправителя", callback_data='edit_from_address')],
        [InlineKeyboardButton("📥 Адрес получателя", callback_data='edit_to_address')],
        [InlineKeyboardButton("📦 Вес посылки", callback_data='edit_parcel')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_confirmation')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(message, reply_markup=reply_markup)
    context.user_data['last_state'] = EDIT_MENU  # Save state for cancel return
    return EDIT_MENU

async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's choice of what to edit"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'back_to_confirmation':
        return await show_data_confirmation(update, context)
    
    if query.data == 'edit_from_address':
        context.user_data['editing_from_address'] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "📤 Редактирование адреса отправителя\n\nШаг 1/6: Имя отправителя\nНапример: John Smith",
            reply_markup=reply_markup
        )
        context.user_data['last_state'] = FROM_NAME  # Save state for cancel return
        return FROM_NAME
    
    if query.data == 'edit_to_address':
        context.user_data['editing_to_address'] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "📥 Редактирование адреса получателя\n\nШаг 1/6: Имя получателя\nНапример: Jane Doe",
            reply_markup=reply_markup
        )
        context.user_data['last_state'] = TO_NAME  # Save state for cancel return
        return TO_NAME
    
    if query.data == 'edit_parcel':
        context.user_data['editing_parcel'] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "📦 Редактирование посылки\n\nВведите вес посылки в фунтах:\nНапример: 5 или 2.5",
            reply_markup=reply_markup
        )
        context.user_data['last_state'] = PARCEL_WEIGHT  # Save state for cancel return
        return PARCEL_WEIGHT

async def fetch_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch shipping rates from ShipStation"""
    query = update.callback_query
    
    await query.message.reply_text("⏳ Получаю доступные курьерские службы и тарифы...")
    
    try:
        import requests
        import asyncio
        
        data = context.user_data
        
        # Get carrier IDs
        carrier_ids = await get_shipstation_carrier_ids()
        if not carrier_ids:
            keyboard = [
                [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "❌ Ошибка: не удалось загрузить список курьеров.\n\nПожалуйста, попробуйте позже.",
                reply_markup=reply_markup
            )
            return CONFIRM_DATA
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Create rate request for ShipStation V2
        rate_request = {
            'rate_options': {
                'carrier_ids': carrier_ids  # Use actual carrier IDs
            },
            'shipment': {
                'ship_to': {
                    'name': data['to_name'],
                    'phone': data.get('to_phone') or '+15551234567',  # Default phone if not provided
                    'address_line1': data['to_street'],
                    'address_line2': data.get('to_street2', ''),
                    'city_locality': data['to_city'],
                    'state_province': data['to_state'],
                    'postal_code': data['to_zip'],
                    'country_code': 'US',
                    'address_residential_indicator': 'unknown'
                },
                'ship_from': {
                    'name': data['from_name'],
                    'phone': data.get('from_phone') or '+15551234567',  # Default phone if not provided
                    'address_line1': data['from_street'],
                    'address_line2': data.get('from_street2', ''),
                    'city_locality': data['from_city'],
                    'state_province': data['from_state'],
                    'postal_code': data['from_zip'],
                    'country_code': 'US'
                },
                'packages': [{
                    'weight': {
                        'value': data['weight'],
                        'unit': 'pound'
                    },
                    'dimensions': {
                        'length': 5,
                        'width': 5,
                        'height': 5,
                        'unit': 'inch'
                    }
                }]
            }
        }
        
        # Get rates from ShipStation
        response = requests.post(
            'https://api.shipstation.com/v2/rates',
            headers=headers,
            json=rate_request,
            timeout=15
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('message', f'Status code: {response.status_code}')
            logger.error(f"ShipStation rate request failed: {error_msg}")
            
            keyboard = [
                [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"❌ Ошибка при получении тарифов:\n{error_msg}\n\nПроверьте правильность введенных адресов.",
                reply_markup=reply_markup
            )
            return CONFIRM_DATA  # Stay to handle callback
        
        rate_response = response.json()
        all_rates = rate_response.get('rate_response', {}).get('rates', [])
        
        # Filter out GlobalPost and Stamps.com rates
        excluded_carriers = ['globalpost', 'stamps_com', 'stamps.com']
        all_rates = [
            rate for rate in all_rates 
            if rate.get('carrier_code', '').lower() not in excluded_carriers
        ]
        
        # Filter to keep only specific services per carrier
        allowed_services = {
            'ups': [
                'ups_ground',
                'ups_3_day_select',  # 3-day delivery
                'ups_2nd_day_air',
                'ups_next_day_air',
                'ups_next_day_air_saver'
            ],
            'fedex_walleted': [
                'fedex_ground',
                'fedex_economy',  # FedEx Express Saver - 3-day delivery
                'fedex_2day',
                'fedex_standard_overnight',
                'fedex_priority_overnight'
            ],
            'usps': [
                'usps_ground_advantage',
                'usps_priority_mail',  # Already includes 2-3 day delivery
                'usps_priority_mail_express'
            ]
        }
        
        # Apply service filter
        filtered_rates = []
        for rate in all_rates:
            carrier_code = rate.get('carrier_code', '').lower()
            service_code = rate.get('service_code', '').lower()
            
            if carrier_code in allowed_services:
                if service_code in allowed_services[carrier_code]:
                    filtered_rates.append(rate)
            else:
                # Keep rates from other carriers if any
                filtered_rates.append(rate)
        
        all_rates = filtered_rates
        
        if not all_rates or len(all_rates) == 0:
            keyboard = [
                [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"❌ Нет доступных тарифов для данного направления.\n\nПроверьте правильность введенных адресов.",
                reply_markup=reply_markup
            )
            return CONFIRM_DATA  # Stay to handle callback
        
        # Log carriers
        carriers = set([r['carrier_friendly_name'] for r in all_rates])
        logger.info(f"Got {len(all_rates)} rates from carriers: {carriers}")
        
        # Balance rates across carriers - show best rates from each carrier
        markup = 10.00  # Markup in USD
        context.user_data['rates'] = []
        
        # Group rates by carrier
        rates_by_carrier = {}
        for rate in all_rates:
            carrier = rate['carrier_friendly_name']
            if carrier not in rates_by_carrier:
                rates_by_carrier[carrier] = []
            rates_by_carrier[carrier].append(rate)
        
        # Sort each carrier's rates by price and take top 5 from each
        balanced_rates = []
        for carrier, carrier_rates in rates_by_carrier.items():
            # Sort by price (ascending)
            sorted_carrier_rates = sorted(carrier_rates, key=lambda r: float(r['shipping_amount']['amount']))
            # Take top 5 cheapest from each carrier
            balanced_rates.extend(sorted_carrier_rates[:5])
        
        # Sort all balanced rates by carrier, then by price
        balanced_rates = sorted(balanced_rates, key=lambda r: (r['carrier_friendly_name'], float(r['shipping_amount']['amount'])))
        
        # Take top 15 overall but maintain carrier grouping
        for rate in balanced_rates[:15]:
            rate_data = {
                'rate_id': rate['rate_id'],
                'carrier': rate['carrier_friendly_name'],
                'carrier_code': rate['carrier_code'],
                'service': rate['service_type'],
                'service_code': rate['service_code'],
                'original_amount': float(rate['shipping_amount']['amount']),
                'amount': float(rate['shipping_amount']['amount']) + markup,
                'currency': rate['shipping_amount']['currency'],
                'days': rate.get('delivery_days')
            }
            context.user_data['rates'].append(rate_data)
        
        # Create buttons for carrier selection
        from datetime import datetime, timedelta, timezone
        
        # Carrier logos/icons - узнаваемые символы
        carrier_icons = {
            'UPS': '🛡 UPS',  # Щит - фирменный логотип UPS (коричнево-золотой щит)
            'USPS': '🦅 USPS',  # Орёл - символ почтовой службы США
            'FedEx One Balance': '⚡ FedEx',  # Молния - символ скорости FedEx Express
            'FedEx': '⚡ FedEx'
        }
        
        # Group rates by carrier for display
        rates_by_carrier_display = {}
        for i, rate in enumerate(context.user_data['rates']):
            carrier = rate['carrier']
            if carrier not in rates_by_carrier_display:
                rates_by_carrier_display[carrier] = []
            rates_by_carrier_display[carrier].append((i, rate))
        
        # Count unique carriers
        unique_carriers = set([r['carrier'] for r in context.user_data['rates']])
        
        message = f"📦 Найдено {len(context.user_data['rates'])} тарифов от {len(unique_carriers)} курьеров:\n\n"
        keyboard = []
        
        # Display rates grouped by carrier
        for carrier in sorted(rates_by_carrier_display.keys()):
            # Add carrier header with icon (bold text for carrier name)
            carrier_icon = carrier_icons.get(carrier, '📦')
            message += f"{'='*30}\n<b>{carrier_icon}</b>\n{'='*30}\n\n"
            
            rates = rates_by_carrier_display[carrier]
            for idx, rate in rates:
                days_text = f" ({rate['days']} дней)" if rate['days'] else ""
                
                # Calculate estimated delivery date
                if rate['days']:
                    delivery_date = datetime.now(timezone.utc) + timedelta(days=rate['days'])
                    date_text = f" → {delivery_date.strftime('%d.%m')}"
                else:
                    date_text = ""
                
                message += f"• {rate['service']}{days_text}{date_text}\n  💰 ${rate['amount']:.2f}\n\n"
                
                # Show full name in button (without icon)
                button_text = f"{carrier} - {rate['service']} - ${rate['amount']:.2f}"
                
                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'select_carrier_{idx}'
                )])
        
        # Add cancel button
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Save state for cancel return - only when showing rates
        context.user_data['last_state'] = SELECT_CARRIER
        
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
        return SELECT_CARRIER
        
    except Exception as e:
        logger.error(f"Error getting rates: {e}", exc_info=True)
        
        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Notify admin about rate fetch error
        telegram_id = query.from_user.id
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if user:
            await notify_admin_error(
                user_info=user,
                error_type="Rate Fetch Failed",
                error_details=f"Exception: {str(e)}\n\nAddresses:\nFrom: {data.get('from_city')}, {data.get('from_state')}\nTo: {data.get('to_city')}, {data.get('to_state')}"
            )
        
        await query.message.reply_text(
            f"❌ Ошибка при получении тарифов:\n{str(e)}\n\nПроверьте корректность адресов и попробуйте снова.",
            reply_markup=reply_markup
        )
        return CONFIRM_DATA  # Stay to handle callback

async def select_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    # Get selected carrier index
    carrier_idx = int(query.data.split('_')[-1])
    selected_rate = context.user_data['rates'][carrier_idx]
    context.user_data['selected_rate'] = selected_rate
    context.user_data['last_state'] = PAYMENT_METHOD  # Save state for cancel return
    
    # Get user balance
    telegram_id = query.from_user.id
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    balance = user.get('balance', 0.0)
    
    # Show payment options
    amount = selected_rate['amount']  # Amount with markup
    original_amount = selected_rate['original_amount']  # GoShippo price
    markup = amount - original_amount
    data = context.user_data
    
    confirmation_text = f"""✅ Выбрано: {selected_rate['carrier']} - {selected_rate['service']}

📦 Детали заказа:
📤 От: {data['from_name']}, {data['from_city']}, {data['from_state']}
📥 До: {data['to_name']}, {data['to_city']}, {data['to_state']}
⚖️ Вес: {data['weight']} lb

💰 Стоимость: ${amount:.2f}

💳 Ваш баланс: ${balance:.2f}
"""
    
    keyboard = []
    
    if balance >= amount:
        # Достаточно денег - показываем только кнопку оплаты с баланса
        confirmation_text += "\n✅ У вас достаточно средств на балансе!"
        keyboard.append([InlineKeyboardButton(
            f"💳 Оплатить с баланса (${balance:.2f})",
            callback_data='pay_from_balance'
        )])
        keyboard.append([
            InlineKeyboardButton("◀️ Назад к тарифам", callback_data='back_to_rates'),
            InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')
        ])
    else:
        # Недостаточно денег - показываем кнопку пополнения
        shortage = amount - balance
        confirmation_text += f"\n⚠️ Недостаточно средств. Необходимо: ${shortage:.2f}"
        keyboard.append([InlineKeyboardButton(
            f"💵 Пополнить баланс",
            callback_data='top_up_balance'
        )])
        keyboard.append([
            InlineKeyboardButton("◀️ Назад к тарифам", callback_data='back_to_rates'),
            InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(confirmation_text, reply_markup=reply_markup)
    return PAYMENT_METHOD

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    # Handle back to rates
    if query.data == 'back_to_rates':
        # Return to rate selection - call fetch_shipping_rates again
        return await fetch_shipping_rates(update, context)
    
    telegram_id = query.from_user.id
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    data = context.user_data
    selected_rate = data['selected_rate']
    amount = selected_rate['amount']
    
    try:
        if query.data == 'pay_from_balance':
            # Pay from balance
            if user.get('balance', 0) < amount:
                await query.message.reply_text("❌ Недостаточно средств на балансе.")
                return ConversationHandler.END
            
            # Create order
            order = await create_order_in_db(user, data, selected_rate, amount)
            
            # Try to create shipping label first
            label_created = await create_and_send_label(order['id'], telegram_id, query.message)
            
            if label_created:
                # Only deduct balance if label was created successfully
                new_balance = user['balance'] - amount
                await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {"balance": new_balance}}
                )
                
                # Update order as paid
                await db.orders.update_one(
                    {"id": order['id']},
                    {"$set": {"payment_status": "paid"}}
                )
                
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    f"""✅ Заказ оплачен с баланса!
💳 Списано: ${amount}
💰 Новый баланс: ${new_balance:.2f}

Shipping label создан успешно!""",
                    reply_markup=reply_markup
                )
            else:
                # Label creation failed - don't charge user
                await db.orders.update_one(
                    {"id": order['id']},
                    {"$set": {"payment_status": "failed", "shipping_status": "failed"}}
                )
                
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    """❌ Не удалось создать shipping label.
                    
Оплата не списана. Ваш баланс не изменился.

Пожалуйста, свяжитесь с администратором.""",
                    reply_markup=reply_markup
                )
            
        elif query.data == 'pay_with_crypto':
            # Create order
            order = await create_order_in_db(user, data, selected_rate, amount)
            
            # Create crypto invoice
            if crypto:
                invoice = await crypto.create_invoice(
                    asset="USDT",
                    amount=amount
                )
                
                pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'mini_app_invoice_url', None)
                
                payment = Payment(
                    order_id=order['id'],
                    amount=amount,
                    invoice_id=invoice.invoice_id,
                    pay_url=pay_url
                )
                payment_dict = payment.model_dump()
                payment_dict['created_at'] = payment_dict['created_at'].isoformat()
                await db.payments.insert_one(payment_dict)
                
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    f"""✅ Заказ создан!

💰 Оплатите ${amount} USDT:
{pay_url}

После оплаты мы автоматически создадим shipping label.""",
                    reply_markup=reply_markup
                )
            else:
                await query.message.reply_text("❌ Система оплаты не настроена.")
                
        elif query.data == 'top_up_balance':
            # Request custom top-up amount
            context.user_data['last_state'] = TOPUP_AMOUNT  # Save state for cancel return
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                """💵 Пополнение баланса

Введите сумму пополнения в долларах США (USD):

Например: 50

Минимальная сумма: $5
Максимальная сумма: $1000""",
                reply_markup=reply_markup
            )
            return TOPUP_AMOUNT
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Payment error: {e}")
        await query.message.reply_text(f"❌ Ошибка при оплате: {str(e)}")
        return ConversationHandler.END

async def handle_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom top-up amount input"""
    try:
        amount_text = update.message.text.strip()
        
        # Validate amount
        try:
            topup_amount = float(amount_text)
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат суммы. Введите число, например: 50"
            )
            return TOPUP_AMOUNT
        
        # Check limits
        if topup_amount < 5:
            await update.message.reply_text(
                "❌ Минимальная сумма пополнения: $5"
            )
            return TOPUP_AMOUNT
        
        if topup_amount > 1000:
            await update.message.reply_text(
                "❌ Максимальная сумма пополнения: $1000"
            )
            return TOPUP_AMOUNT
        
        # Save amount in context
        context.user_data['topup_amount'] = topup_amount
        
        # Show cryptocurrency selection (only BTC, ETH, USDT, LTC)
        keyboard = [
            [
                InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data='topup_crypto_btc'),
                InlineKeyboardButton("Ξ Ethereum (ETH)", callback_data='topup_crypto_eth')
            ],
            [
                InlineKeyboardButton("₮ USDT (Tether)", callback_data='topup_crypto_usdt'),
                InlineKeyboardButton("Ł Litecoin (LTC)", callback_data='topup_crypto_ltc')
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"""💰 Выберите криптовалюту для пополнения:

💵 Сумма: ${topup_amount}

Доступные криптовалюты:
• Bitcoin (BTC)
• Ethereum (ETH)  
• USDT (Tether)
• Litecoin (LTC)""",
            reply_markup=reply_markup
        )
        return TOPUP_AMOUNT  # Stay in same state to handle crypto selection
        
    except Exception as e:
        logger.error(f"Top-up amount handling error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        return ConversationHandler.END

async def handle_topup_crypto_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cryptocurrency selection for top-up"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    try:
        # Extract cryptocurrency from callback data
        crypto_asset = query.data.replace('topup_crypto_', '').upper()
        topup_amount = context.user_data.get('topup_amount')
        
        if not topup_amount:
            await query.message.reply_text("❌ Ошибка: сумма не найдена. Начните заново.")
            return ConversationHandler.END
        
        telegram_id = query.from_user.id
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        # Crypto names for display
        crypto_names = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'USDT': 'USDT (Tether)',
            'TON': 'TON',
            'LTC': 'Litecoin',
            'USDC': 'USDC',
            'BNB': 'BNB (Binance Coin)',
            'TRX': 'TRX (Tron)'
        }
        
        if crypto:
            # Create invoice with selected cryptocurrency
            invoice = await crypto.create_invoice(
                asset=crypto_asset,
                amount=topup_amount
            )
            
            pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'mini_app_invoice_url', None)
            
            # Save top-up payment
            payment = Payment(
                order_id=f"topup_{user['id']}",
                amount=topup_amount,
                invoice_id=invoice.invoice_id,
                pay_url=pay_url,
                currency=crypto_asset,
                status="pending"
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            payment_dict['telegram_id'] = telegram_id
            payment_dict['type'] = 'topup'
            await db.payments.insert_one(payment_dict)
            
            keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            crypto_display_name = crypto_names.get(crypto_asset, crypto_asset)
            
            await query.message.reply_text(
                f"""✅ Счёт на пополнение создан!

💵 Сумма: ${topup_amount}
💰 Криптовалюта: {crypto_display_name}

Оплатите по ссылке:
{pay_url}

⏰ После оплаты баланс будет пополнен автоматически, и вы сможете оплатить заказ.""",
                reply_markup=reply_markup
            )
        else:
            await query.message.reply_text("❌ Система оплаты не настроена.")
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Crypto selection handling error: {e}")
        await query.message.reply_text(f"❌ Ошибка: {str(e)}")
        return ConversationHandler.END

async def create_order_in_db(user, data, selected_rate, amount):
    order = Order(
        user_id=user['id'],
        telegram_id=user['telegram_id'],
        address_from=Address(
            name=data['from_name'],
            street1=data['from_street'],
            street2=data.get('from_street2'),
            city=data['from_city'],
            state=data['from_state'],
            zip=data['from_zip'],
            country="US",
            phone=data.get('from_phone', '')
        ),
        address_to=Address(
            name=data['to_name'],
            street1=data['to_street'],
            street2=data.get('to_street2'),
            city=data['to_city'],
            state=data['to_state'],
            zip=data['to_zip'],
            country="US",
            phone=data.get('to_phone', '')
        ),
        parcel=Parcel(
            length=5,
            width=5,
            height=5,
            weight=data['weight'],
            distance_unit="in",
            mass_unit="lb"
        ),
        amount=amount  # This is the amount with markup that user pays
    )
    
    order_dict = order.model_dump()
    order_dict['created_at'] = order_dict['created_at'].isoformat()
    order_dict['selected_carrier'] = selected_rate['carrier']
    order_dict['selected_service'] = selected_rate['service']
    order_dict['selected_service_code'] = selected_rate.get('service_code', '')  # Add service_code
    order_dict['rate_id'] = selected_rate['rate_id']
    order_dict['original_amount'] = selected_rate['original_amount']  # Store original GoShippo price
    order_dict['markup'] = amount - selected_rate['original_amount']  # Store markup amount
    await db.orders.insert_one(order_dict)
    
    return order_dict

async def create_and_send_label(order_id, telegram_id, message):
    try:
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        
        logger.info(f"Creating label for order {order_id}")
        
        import requests
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Create label request for ShipStation V2
        label_request = {
            'label_layout': 'letter',
            'label_format': 'pdf',
            'shipment': {
                'ship_to': {
                    'name': order['address_to']['name'],
                    'phone': order['address_to'].get('phone') or '+15551234567',  # Default phone if empty
                    'address_line1': order['address_to']['street1'],
                    'address_line2': order['address_to'].get('street2', ''),
                    'city_locality': order['address_to']['city'],
                    'state_province': order['address_to']['state'],
                    'postal_code': order['address_to']['zip'],
                    'country_code': order['address_to'].get('country', 'US')
                },
                'ship_from': {
                    'name': order['address_from']['name'],
                    'phone': order['address_from'].get('phone') or '+15551234567',  # Default phone if empty
                    'address_line1': order['address_from']['street1'],
                    'address_line2': order['address_from'].get('street2', ''),
                    'city_locality': order['address_from']['city'],
                    'state_province': order['address_from']['state'],
                    'postal_code': order['address_from']['zip'],
                    'country_code': order['address_from'].get('country', 'US')
                },
                'packages': [{
                    'weight': {
                        'value': order['parcel']['weight'],
                        'unit': 'pound'
                    },
                    'dimensions': {
                        'length': order['parcel'].get('length', 5),
                        'width': order['parcel'].get('width', 5),
                        'height': order['parcel'].get('height', 5),
                        'unit': 'inch'
                    }
                }],
                'service_code': order.get('selected_service_code', order.get('service_code', ''))  # Add service_code
            },
            'rate_id': order['rate_id']
        }
        
        logger.info(f"Purchasing label with rate_id: {order['rate_id']}")
        
        response = requests.post(
            'https://api.shipstation.com/v2/labels',
            headers=headers,
            json=label_request,
            timeout=30
        )
        
        if response.status_code != 201:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('message', f'Status code: {response.status_code}')
            logger.error(f"Label creation failed: {error_msg}")
            logger.error(f"Response: {response.text}")
            
            # Notify admin about label creation error
            user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
            if user:
                error_details = f"ShipStation API Error:\n{response.text[:500]}"
                await notify_admin_error(
                    user_info=user,
                    error_type="Label Creation Failed",
                    error_details=error_details,
                    order_id=order_id
                )
            
            raise Exception(error_msg)
        
        label_response = response.json()
        
        # Extract label data
        tracking_number = label_response.get('tracking_number', '')
        label_download_url = label_response.get('label_download', {}).get('pdf', '')
        
        logger.info(f"Label created: tracking={tracking_number}, label_url={label_download_url}")
        
        # Save label
        label = ShippingLabel(
            order_id=order_id,
            tracking_number=tracking_number,
            label_url=label_download_url,
            carrier=order['selected_carrier'],
            service_level=order['selected_service'],
            amount=str(order['amount']),  # User paid amount (with markup)
            status='created'
        )
        
        label_dict = label.model_dump()
        label_dict['created_at'] = label_dict['created_at'].isoformat()
        label_dict['original_amount'] = order.get('original_amount')  # ShipStation price
        await db.shipping_labels.insert_one(label_dict)
        
        # Update order
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"shipping_status": "label_created"}}
        )
        
        # Send label to user
        if bot_instance:
            await bot_instance.send_message(
                chat_id=telegram_id,
                text=f"""📦 Shipping label создан!

Tracking: {tracking_number}
Carrier: {order['selected_carrier']}
Service: {order['selected_service']}

Label PDF: {label_download_url}

Вы оплатили: ${order['amount']:.2f}"""
            )
        logger.info(f"Label created successfully for order {order_id}")
        return True  # Success
        
    except Exception as e:
        logger.error(f"Error creating label: {e}", exc_info=True)
        
        # Notify admin about error
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if user:
            await notify_admin_error(
                user_info=user,
                error_type="Label Creation Exception",
                error_details=str(e),
                order_id=order_id
            )
        
        # Send polite message to user
        user_message = """😔 К сожалению, в данный момент мы не можем сгенерировать shipping label.

Пожалуйста, свяжитесь с администратором.

Приносим извинения за неудобства!"""
        
        if message:
            await message.reply_text(user_message)
        elif bot_instance:
            await bot_instance.send_message(
                chat_id=telegram_id,
                text=user_message
            )
        
        return False  # Failed

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
    
    # Don't save current_state - it's already saved in last_state
    keyboard = [
        [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='return_to_order')],
        [InlineKeyboardButton("✅ Да, отменить заказ", callback_data='confirm_cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "⚠️ Вы уверены, что хотите отменить создание заказа?\n\nВсе введённые данные будут потеряны.",
        reply_markup=reply_markup
    )
    
    # Return the state we were in before cancel
    return context.user_data.get('last_state', PAYMENT_METHOD)

async def confirm_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm order cancellation"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text("❌ Создание заказа отменено.", reply_markup=reply_markup)
    return ConversationHandler.END

async def return_to_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order after cancel button - restore exact screen"""
    query = update.callback_query
    await query.answer()
    
    # Get the state we were in when cancel was pressed
    last_state = context.user_data.get('last_state')
    
    # If no last_state - just continue
    if not last_state:
        await query.message.reply_text("Продолжаем оформление заказа...")
        return FROM_NAME
    
    # Restore exact screen with instructions for each state
    if last_state == FROM_NAME:
        await query.message.reply_text("Шаг 1/13: Имя отправителя\n\nНапример: Ivan Petrov")
        return FROM_NAME
    
    elif last_state == FROM_ADDRESS:
        await query.message.reply_text("Шаг 2/13: Адрес отправителя\n\nВведите улицу и номер дома\nНапример: 215 Clayton St")
        return FROM_ADDRESS
    
    elif last_state == FROM_ADDRESS2:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_from_address2')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            """Шаг 3/13: Квартира/Офис отправителя (необязательно)

Например: Apt 5, Suite 201

Или нажмите "Пропустить" """,
            reply_markup=reply_markup
        )
        return FROM_ADDRESS2
    
    elif last_state == FROM_CITY:
        await query.message.reply_text("Шаг 4/13: Город отправителя\n\nНапример: Los Angeles")
        return FROM_CITY
    
    elif last_state == FROM_STATE:
        await query.message.reply_text("Шаг 5/13: Штат отправителя\n\nВведите двухбуквенный код штата\nНапример: CA, NY, TX")
        return FROM_STATE
    
    elif last_state == FROM_ZIP:
        await query.message.reply_text("Шаг 6/13: ZIP код отправителя\n\nНапример: 90001")
        return FROM_ZIP
    
    elif last_state == FROM_PHONE:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_from_phone')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Шаг 7/13: Телефон отправителя (необязательно)\n\nНапример: 5551234567\nИли нажмите 'Пропустить'",
            reply_markup=reply_markup
        )
        return FROM_PHONE
    
    elif last_state == TO_NAME:
        await query.message.reply_text("Шаг 8/13: Имя получателя\n\nНапример: John Smith")
        return TO_NAME
    
    elif last_state == TO_ADDRESS:
        await query.message.reply_text("Шаг 9/13: Адрес получателя\n\nВведите улицу и номер дома\nНапример: 123 Main St")
        return TO_ADDRESS
    
    if last_state == TO_ADDRESS2:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_to_address2')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            """Шаг 10/13: Квартира/Офис получателя (необязательно)

Например: Apt 12, Suite 305

Или нажмите "Пропустить" """,
            reply_markup=reply_markup
        )
        return TO_ADDRESS2
    
    elif last_state == TO_CITY:
        await query.message.reply_text("Шаг 11/13: Город получателя\n\nНапример: New York")
        return TO_CITY
    
    elif last_state == TO_STATE:
        await query.message.reply_text("Шаг 11/13: Штат получателя\n\nВведите двухбуквенный код штата\nНапример: CA, NY, TX")
        return TO_STATE
    
    elif last_state == TO_ZIP:
        await query.message.reply_text("Шаг 12/13: ZIP код получателя\n\nНапример: 10001")
        return TO_ZIP
    
    elif last_state == TO_PHONE:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_to_phone')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Шаг 13/13: Телефон получателя (необязательно)\n\nНапример: 5559876543\nИли нажмите 'Пропустить'",
            reply_markup=reply_markup
        )
        return TO_PHONE
    
    elif last_state == PARCEL_WEIGHT:
        await query.message.reply_text("Шаг 14/13: Вес посылки\n\nВведите вес в фунтах (lb)\nНапример: 2.5")
        return PARCEL_WEIGHT
    
    # Special states - show their specific screens
    elif last_state == CONFIRM_DATA:
        # User was on data confirmation screen
        return await show_data_confirmation(update, context)
    
    elif last_state == EDIT_MENU:
        # User was on edit menu screen
        return await show_edit_menu(update, context)
    
    # Later stages - restore specific screens
    elif last_state == SELECT_CARRIER:
        # Check if we have enough data to fetch rates
        data = context.user_data
        required_fields = ['from_name', 'from_city', 'from_state', 'from_zip', 
                          'to_name', 'to_city', 'to_state', 'to_zip', 'weight']
        
        if all(field in data for field in required_fields):
            # Have all data - can fetch rates
            await query.message.reply_text("Возвращаемся к выбору тарифа...")
            return await fetch_shipping_rates(update, context)
        else:
            # Missing data - just continue
            await query.message.reply_text("Продолжаем оформление заказа...")
            return last_state
    
    elif last_state == PAYMENT_METHOD:
        # Return to payment screen
        data = context.user_data
        selected_rate = data.get('selected_rate')
        
        if selected_rate:
            telegram_id = query.from_user.id
            user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
            balance = user.get('balance', 0)
            amount = selected_rate['amount']
            
            confirmation_text = f"""✅ Выбрано: {selected_rate['carrier']} - {selected_rate['service']}

📦 Детали заказа:
📤 От: {data['from_name']}, {data['from_city']}, {data['from_state']}
📥 До: {data['to_name']}, {data['to_city']}, {data['to_state']}
⚖️ Вес: {data['weight']} lb

💰 Стоимость: ${amount:.2f}

💳 Ваш баланс: ${balance:.2f}
"""
            
            keyboard = []
            
            if balance >= amount:
                confirmation_text += "\n✅ У вас достаточно средств на балансе!"
                keyboard.append([InlineKeyboardButton(
                    f"💳 Оплатить с баланса (${balance:.2f})",
                    callback_data='pay_from_balance'
                )])
                keyboard.append([
                    InlineKeyboardButton("◀️ Назад к тарифам", callback_data='back_to_rates'),
                    InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')
                ])
            else:
                shortage = amount - balance
                confirmation_text += f"\n⚠️ Недостаточно средств. Необходимо: ${shortage:.2f}"
                keyboard.append([InlineKeyboardButton(
                    f"💵 Пополнить баланс",
                    callback_data='top_up_balance'
                )])
                keyboard.append([
                    InlineKeyboardButton("◀️ Назад к тарифам", callback_data='back_to_rates'),
                    InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(confirmation_text, reply_markup=reply_markup)
            return PAYMENT_METHOD
        else:
            await query.message.reply_text("Продолжаем...")
            return last_state
    
    elif last_state == TOPUP_AMOUNT:
        # Return to top-up amount input
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            """💵 Пополнение баланса

Введите сумму пополнения в долларах США (USD):

Например: 50

Минимальная сумма: $5
Максимальная сумма: $1000""",
            reply_markup=reply_markup
        )
        return TOPUP_AMOUNT
    
    else:
        # Default fallback
        await query.message.reply_text("Продолжаем оформление заказа...")
        return last_state if last_state else PAYMENT_METHOD

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Telegram Shipping Bot API", "status": "running"}

@api_router.post("/orders", response_model=dict)
async def create_order(order_data: OrderCreate):
    try:
        # Check user exists
        user = await db.users.find_one({"telegram_id": order_data.telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found. Please /start the bot first.")
        
        # Create order
        order = Order(
            user_id=user['id'],
            telegram_id=order_data.telegram_id,
            address_from=order_data.address_from,
            address_to=order_data.address_to,
            parcel=order_data.parcel,
            amount=order_data.amount
        )
        
        order_dict = order.model_dump()
        order_dict['created_at'] = order_dict['created_at'].isoformat()
        await db.orders.insert_one(order_dict)
        
        # Create crypto payment invoice
        if crypto:
            invoice = await crypto.create_invoice(
                asset="USDT",
                amount=order_data.amount
            )
            
            # Get payment URL from bot_invoice_url or mini_app_invoice_url
            pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'mini_app_invoice_url', None)
            
            payment = Payment(
                order_id=order.id,
                amount=order_data.amount,
                invoice_id=invoice.invoice_id,
                pay_url=pay_url
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            await db.payments.insert_one(payment_dict)
            
            # Send payment link to user
            if bot_instance and pay_url:
                await bot_instance.send_message(
                    chat_id=order_data.telegram_id,
                    text=f"""✅ Заказ создан!

💰 Оплатите {order_data.amount} USDT:
{pay_url}

После оплаты мы автоматически создадим shipping label."""
                )
            
            return {
                "order_id": order.id,
                "payment_url": pay_url,
                "amount": order_data.amount,
                "currency": "USDT"
            }
        else:
            return {
                "order_id": order.id,
                "message": "Order created but payment system not configured"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/orders", response_model=List[dict])
async def get_orders(telegram_id: Optional[int] = None):
    query = {"telegram_id": telegram_id} if telegram_id else {}
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return orders

@api_router.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@api_router.post("/shipping/create-label")
async def create_shipping_label(order_id: str):
    try:
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order['payment_status'] != 'paid':
            raise HTTPException(status_code=400, detail="Order not paid")
        
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        # Use the main label creation function
        result = await create_and_send_label(order_id, order['telegram_id'], None)
        
        if result:
            # Get the created label
            label = await db.shipping_labels.find_one({"order_id": order_id}, {"_id": 0})
            return {
                "order_id": order_id,
                "tracking_number": label['tracking_number'],
                "label_url": label['label_url'],
                "status": "success"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create label")
        
    except Exception as e:
        logger.error(f"Error creating label: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/shipping/track/{tracking_number}")
async def track_shipment(tracking_number: str, carrier: str):
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # ShipStation V2 tracking endpoint
        response = requests.get(
            f'https://api.shipstation.com/v2/tracking?tracking_number={tracking_number}&carrier_code={carrier}',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            tracking_data = response.json()
            return {
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status": tracking_data.get('status', 'UNKNOWN'),
                "tracking_history": tracking_data.get('events', [])
            }
        else:
            return {
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status": "UNKNOWN",
                "message": "Tracking information not available"
            }
    except Exception as e:
        logger.error(f"Error tracking shipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/webhooks/cryptopay")
async def cryptopay_webhook(request: Request):
    try:
        body = await request.json()
        
        # Verify webhook signature
        if crypto:
            # Update payment status
            invoice_id = body.get('payload', {}).get('invoice_id')
            payment_status = body.get('payload', {}).get('status')
            
            if payment_status == 'paid':
                payment = await db.payments.find_one({"invoice_id": invoice_id}, {"_id": 0})
                if payment:
                    # Update payment
                    await db.payments.update_one(
                        {"invoice_id": invoice_id},
                        {"$set": {"status": "paid"}}
                    )
                    
                    # Check if it's a top-up
                    if payment.get('type') == 'topup':
                        # Add to balance
                        telegram_id = payment.get('telegram_id')
                        amount = payment.get('amount', 0)
                        
                        await db.users.update_one(
                            {"telegram_id": telegram_id},
                            {"$inc": {"balance": amount}}
                        )
                        
                        # Notify user
                        if bot_instance:
                            user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
                            new_balance = user.get('balance', 0)
                            
                            await bot_instance.send_message(
                                chat_id=telegram_id,
                                text=f"""✅ Баланс пополнен!

💰 Зачислено: ${amount}
💳 Новый баланс: ${new_balance:.2f}"""
                            )
                    else:
                        # Regular order payment
                        # Update order
                        await db.orders.update_one(
                            {"id": payment['order_id']},
                            {"$set": {"payment_status": "paid"}}
                        )
                        
                        # Auto-create shipping label
                        try:
                            order = await db.orders.find_one({"id": payment['order_id']}, {"_id": 0})
                            await create_and_send_label(payment['order_id'], order['telegram_id'], None)
                        except Exception as e:
                            logger.error(f"Failed to create label: {e}")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

@api_router.get("/users")
async def get_users():
    users = await db.users.find({}, {"_id": 0}).to_list(100)
    return users

@api_router.get("/users/{telegram_id}/details")
async def get_user_details(telegram_id: int):
    try:
        # Get user
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user orders
        orders = await db.orders.find(
            {"telegram_id": telegram_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        # Get user payments
        payments = await db.payments.find(
            {"telegram_id": telegram_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        # Get shipping labels for user orders
        order_ids = [order['id'] for order in orders]
        labels = await db.shipping_labels.find(
            {"order_id": {"$in": order_ids}},
            {"_id": 0}
        ).to_list(100)
        
        # Calculate stats
        total_orders = len(orders)
        paid_orders = len([o for o in orders if o.get('payment_status') == 'paid'])
        total_spent = sum([o.get('amount', 0) for o in orders if o.get('payment_status') == 'paid'])
        
        # Calculate rating based on activity
        rating_score = 0
        rating_score += paid_orders * 10  # 10 points per paid order
        rating_score += total_spent * 0.5  # 0.5 points per dollar spent
        
        if paid_orders >= 10:
            rating_level = "🏆 VIP"
        elif paid_orders >= 5:
            rating_level = "⭐ Gold"
        elif paid_orders >= 2:
            rating_level = "🥈 Silver"
        elif paid_orders >= 1:
            rating_level = "🥉 Bronze"
        else:
            rating_level = "🆕 New"
        
        return {
            "user": user,
            "orders": orders,
            "payments": payments,
            "labels": labels,
            "stats": {
                "total_orders": total_orders,
                "paid_orders": paid_orders,
                "pending_orders": total_orders - paid_orders,
                "total_spent": total_spent,
                "rating_score": rating_score,
                "rating_level": rating_level,
                "average_order_value": total_spent / paid_orders if paid_orders > 0 else 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/users/leaderboard")
async def get_leaderboard():
    try:
        users = await db.users.find({}, {"_id": 0}).to_list(1000)
        
        leaderboard = []
        for user in users:
            orders = await db.orders.find(
                {"telegram_id": user['telegram_id'], "payment_status": "paid"},
                {"_id": 0}
            ).to_list(100)
            
            total_orders = len(orders)
            total_spent = sum([o.get('amount', 0) for o in orders])
            
            rating_score = 0
            rating_score += total_orders * 10
            rating_score += total_spent * 0.5
            
            if total_orders >= 10:
                rating_level = "🏆 VIP"
            elif total_orders >= 5:
                rating_level = "⭐ Gold"
            elif total_orders >= 2:
                rating_level = "🥈 Silver"
            elif total_orders >= 1:
                rating_level = "🥉 Bronze"
            else:
                rating_level = "🆕 New"
            
            leaderboard.append({
                "telegram_id": user['telegram_id'],
                "first_name": user.get('first_name', 'Unknown'),
                "username": user.get('username'),
                "total_orders": total_orders,
                "total_spent": total_spent,
                "rating_score": rating_score,
                "rating_level": rating_level,
                "balance": user.get('balance', 0)
            })
        
        # Sort by rating score
        leaderboard.sort(key=lambda x: x['rating_score'], reverse=True)
        
        return leaderboard
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/{telegram_id}/balance/add")
async def add_balance(telegram_id: int, amount: float):
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Add balance
        new_balance = user.get('balance', 0) + amount
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"balance": new_balance}}
        )
        
        # Notify user via Telegram
        if bot_instance:
            await bot_instance.send_message(
                chat_id=telegram_id,
                text=f"""💰 Баланс пополнен администратором!

Зачислено: ${amount:.2f}
Новый баланс: ${new_balance:.2f}"""
            )
        
        return {"success": True, "new_balance": new_balance, "added": amount}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/{telegram_id}/balance/deduct")
async def deduct_balance(telegram_id: int, amount: float):
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_balance = user.get('balance', 0)
        if current_balance < amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        # Deduct balance
        new_balance = current_balance - amount
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"balance": new_balance}}
        )
        
        # Notify user via Telegram
        if bot_instance:
            await bot_instance.send_message(
                chat_id=telegram_id,
                text=f"""⚠️ Баланс изменен администратором!

Списано: ${amount:.2f}
Новый баланс: ${new_balance:.2f}"""
            )
        
        return {"success": True, "new_balance": new_balance, "deducted": amount}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/carriers")
async def get_carriers():
    """Get list of active carrier accounts from ShipStation"""
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Get carrier accounts
        response = requests.get(
            'https://api.shipstation.com/v2/carriers',
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch carriers")
        
        carriers_data = response.json()
        carriers = carriers_data.get('carriers', [])
        
        # Format carriers
        active_carriers = [
            {
                "carrier": carrier.get('friendly_name'),
                "carrier_code": carrier.get('carrier_code'),
                "account_id": carrier.get('carrier_id'),
                "active": not carrier.get('disabled_by_billing_plan', False),
                "services": len(carrier.get('services', []))
            }
            for carrier in carriers
        ]
        
        return {
            "carriers": active_carriers,
            "total": len(active_carriers)
        }
        
    except Exception as e:
        logger.error(f"Error fetching carriers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ShippingRateRequest(BaseModel):
    from_address: Address
    to_address: Address
    parcel: Parcel

@api_router.post("/calculate-shipping")
async def calculate_shipping_rates(request: ShippingRateRequest):
    """Calculate shipping rates for given addresses and parcel"""
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        # Get carrier IDs
        carrier_ids = await get_shipstation_carrier_ids()
        if not carrier_ids:
            raise HTTPException(status_code=500, detail="Failed to load carrier information")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Convert addresses to ShipStation format
        from_addr = request.from_address.model_dump()
        to_addr = request.to_address.model_dump()
        parcel = request.parcel.model_dump()
        
        # Create rate request
        rate_request = {
            'rate_options': {
                'carrier_ids': carrier_ids  # Use actual carrier IDs
            },
            'shipment': {
                'ship_from': {
                    'name': from_addr.get('name', ''),
                    'phone': from_addr.get('phone') or '+15551234567',  # Default phone if not provided
                    'address_line1': from_addr.get('street1', ''),
                    'address_line2': from_addr.get('street2', ''),
                    'city_locality': from_addr.get('city', ''),
                    'state_province': from_addr.get('state', ''),
                    'postal_code': from_addr.get('zip', ''),
                    'country_code': from_addr.get('country', 'US')
                },
                'ship_to': {
                    'name': to_addr.get('name', ''),
                    'phone': to_addr.get('phone') or '+15551234567',  # Default phone if not provided
                    'address_line1': to_addr.get('street1', ''),
                    'address_line2': to_addr.get('street2', ''),
                    'city_locality': to_addr.get('city', ''),
                    'state_province': to_addr.get('state', ''),
                    'postal_code': to_addr.get('zip', ''),
                    'country_code': to_addr.get('country', 'US'),
                    'address_residential_indicator': 'unknown'
                },
                'packages': [{
                    'weight': {
                        'value': parcel.get('weight', 1),
                        'unit': 'pound'
                    },
                    'dimensions': {
                        'length': parcel.get('length', 5),
                        'width': parcel.get('width', 5),
                        'height': parcel.get('height', 5),
                        'unit': 'inch'
                    }
                }]
            }
        }
        
        response = requests.post(
            'https://api.shipstation.com/v2/rates',
            headers=headers,
            json=rate_request,
            timeout=15
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('message', f'Status code: {response.status_code}')
            raise HTTPException(status_code=400, detail=f"Failed to get rates: {error_msg}")
        
        rate_response = response.json()
        all_rates = rate_response.get('rate_response', {}).get('rates', [])
        
        # Filter out GlobalPost and Stamps.com rates
        excluded_carriers = ['globalpost', 'stamps_com', 'stamps.com']
        all_rates = [
            rate for rate in all_rates 
            if rate.get('carrier_code', '').lower() not in excluded_carriers
        ]
        
        # Filter to keep only specific services per carrier
        allowed_services = {
            'ups': [
                'ups_ground',
                'ups_3_day_select',  # 3-day delivery
                'ups_2nd_day_air',
                'ups_next_day_air',
                'ups_next_day_air_saver'
            ],
            'fedex_walleted': [
                'fedex_ground',
                'fedex_economy',  # FedEx Express Saver - 3-day delivery
                'fedex_2day',
                'fedex_standard_overnight',
                'fedex_priority_overnight'
            ],
            'usps': [
                'usps_ground_advantage',
                'usps_priority_mail',  # Already includes 2-3 day delivery
                'usps_priority_mail_express'
            ]
        }
        
        # Apply service filter
        filtered_rates = []
        for rate in all_rates:
            carrier_code = rate.get('carrier_code', '').lower()
            service_code = rate.get('service_code', '').lower()
            
            if carrier_code in allowed_services:
                if service_code in allowed_services[carrier_code]:
                    filtered_rates.append(rate)
            else:
                # Keep rates from other carriers if any
                filtered_rates.append(rate)
        
        all_rates = filtered_rates
        
        if not all_rates:
            raise HTTPException(status_code=400, detail="No shipping rates available")
        
        # Format rates for response
        formatted_rates = [
            {
                'rate_id': rate['rate_id'],
                'carrier': rate['carrier_friendly_name'],
                'carrier_code': rate['carrier_code'],
                'service': rate['service_type'],
                'service_code': rate['service_code'],
                'amount': float(rate['shipping_amount']['amount']),
                'currency': rate['shipping_amount']['currency'],
                'estimated_days': rate.get('delivery_days')
            }
            for rate in all_rates
        ]
        
        carriers = set([r['carrier'] for r in formatted_rates])
        
        return {
            "rates": formatted_rates,
            "total_rates": len(formatted_rates),
            "carriers": list(carriers)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating shipping rates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/stats")
async def get_stats():
    total_users = await db.users.count_documents({})
    total_orders = await db.orders.count_documents({})
    paid_orders = await db.orders.count_documents({"payment_status": "paid"})
    total_revenue = await db.orders.aggregate([
        {"$match": {"payment_status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    
    revenue = total_revenue[0]['total'] if total_revenue else 0
    
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "total_revenue": revenue
    }

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting application...")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "your_telegram_bot_token_here":
        try:
            logger.info("Initializing Telegram Bot...")
            application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            
            # Conversation handler for order creation
            order_conv_handler = ConversationHandler(
                entry_points=[CallbackQueryHandler(new_order_start, pattern='^new_order$')],
                states={
                    FROM_NAME: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_name),
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
                        CallbackQueryHandler(order_from_phone, pattern='^skip_from_phone$'),
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
                        CallbackQueryHandler(order_to_phone, pattern='^skip_to_phone$'),
                        CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                        CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
                    ],
                    PARCEL_WEIGHT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_weight),
                        CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                        CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
                    ],
                    CONFIRM_DATA: [CallbackQueryHandler(handle_data_confirmation, pattern='^(confirm_data|edit_data|edit_addresses_error|return_to_order|confirm_cancel|cancel_order)$')],
                    EDIT_MENU: [CallbackQueryHandler(handle_edit_choice, pattern='^(edit_from_address|edit_to_address|edit_parcel|back_to_confirmation|return_to_order|confirm_cancel)$')],
                    SELECT_CARRIER: [CallbackQueryHandler(select_carrier, pattern='^(select_carrier_|return_to_order|confirm_cancel|cancel_order)')],
                    PAYMENT_METHOD: [CallbackQueryHandler(process_payment, pattern='^(pay_from_balance|pay_with_crypto|top_up_balance|back_to_rates|return_to_order|confirm_cancel|cancel_order)')],
                    TOPUP_AMOUNT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topup_amount),
                        CallbackQueryHandler(handle_topup_crypto_selection, pattern='^(topup_crypto_|return_to_order|confirm_cancel|cancel_order)')
                    ]
                },
                fallbacks=[
                    CallbackQueryHandler(cancel_order, pattern='^cancel_order$'),
                    CommandHandler('start', start_command)
                ]
            )
            
            application.add_handler(order_conv_handler)
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CommandHandler("my_orders", my_orders_command))
            application.add_handler(CommandHandler("track", track_command))
            application.add_handler(CommandHandler("balance", my_balance_command))
            application.add_handler(CallbackQueryHandler(handle_topup, pattern='^topup_\d+$'))
            application.add_handler(CallbackQueryHandler(button_callback))
            
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            
            logger.info("Telegram Bot started successfully!")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}")
            logger.warning("Application will continue without Telegram Bot")
    else:
        logger.warning("Telegram Bot Token not configured. Bot features will be disabled.")
        logger.info("To enable Telegram Bot, add TELEGRAM_BOT_TOKEN to backend/.env")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()