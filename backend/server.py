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
import shippo
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

# Shippo API
SHIPPO_API_KEY = os.environ.get('SHIPPO_API_KEY', '')

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
        await send_method("У вас пока нет заказов. Создайте первый заказ через веб-панель.", reply_markup=reply_markup)
        return
    
    message = "📦 Ваши заказы:\n\n"
    for order in orders:
        status_emoji = "✅" if order['payment_status'] == 'paid' else "⏳"
        ship_emoji = "📮" if order['shipping_status'] == 'label_created' else "📦"
        
        message += f"""{status_emoji} Заказ #{order['id'][:8]}
💰 Оплата: {order['payment_status']}
{ship_emoji} Доставка: {order['shipping_status']}
💵 Сумма: ${order['amount']}
📅 {order.get('created_at', '')[:10]}
---\n"""
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
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
FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, FROM_STATE, FROM_ZIP, TO_NAME, TO_ADDRESS, TO_ADDRESS2, TO_CITY, TO_STATE, TO_ZIP, PARCEL_WEIGHT, SELECT_CARRIER, PAYMENT_METHOD = range(15)

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
        """Шаг 2/11: Адрес отправителя
Например: 215 Clayton St.""",
        reply_markup=reply_markup
    )
    return FROM_ADDRESS

async def order_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    
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
    if not all((ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/")) for c in address):
        await update.message.reply_text("❌ Используйте только английские буквы и цифры. Разрешены: буквы, цифры, пробелы, дефисы, точки, запятые")
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
    return FROM_ZIP

async def order_from_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zip_code = update.message.text.strip()
    
    # Validate ZIP code
    import re
    # US ZIP format: 5 digits or 5-4 digits
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        await update.message.reply_text("❌ Неверный формат ZIP кода. Используйте формат: 12345 или 12345-6789:")
        return FROM_ZIP
    
    context.user_data['from_zip'] = zip_code
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """✅ Адрес отправителя сохранен

Шаг 7/13: Имя получателя
Например: Jane Doe""",
        reply_markup=reply_markup
    )
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
    
    await update.message.reply_text(
        """Шаг 8/13: Адрес получателя
Например: 123 Main St.""",
        reply_markup=reply_markup
    )
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
    if not all((ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/")) for c in address):
        await update.message.reply_text("❌ Используйте только английские буквы и цифры. Разрешены: буквы, цифры, пробелы, дефисы, точки, запятые")
        return TO_ADDRESS
    
    context.user_data['to_street'] = address
    
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_to_address2')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 9/13: Квартира/Офис получателя (необязательно)
Например: Apt 12, Suite 305
Или нажмите "Пропустить" """,
        reply_markup=reply_markup
    )
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
    
    await (update.message or update.callback_query.message).reply_text(
        """Шаг 10/13: Город получателя
Например: New York""",
        reply_markup=reply_markup
    )
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
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """✅ Адрес получателя сохранен

Шаг 13/13: Вес посылки в фунтах (lb)
Например: 2""",
        reply_markup=reply_markup
    )
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
        
        # Get shipping rates from GoShippo
        await update.message.reply_text("⏳ Получаю доступные курьерские службы и тарифы...")
        
        try:
            import requests
            
            data = context.user_data
            
            # Get all carrier accounts using REST API
            headers = {
                'Authorization': f'ShippoToken {SHIPPO_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            carrier_accounts = []
            try:
                acc_response = requests.get('https://api.goshippo.com/carrier_accounts/', headers=headers)
                if acc_response.status_code == 200:
                    accounts_data = acc_response.json()
                    if 'results' in accounts_data:
                        carrier_accounts = [
                            acc['object_id'] for acc in accounts_data['results']
                            if acc.get('active') and acc.get('test')
                        ]
                        logger.info(f"Found {len(carrier_accounts)} active carrier accounts")
            except Exception as e:
                logger.warning(f"Could not fetch carrier accounts: {e}")
            
            # Create shipment to get rates
            shipment_data = {
                'address_from': {
                    'name': data['from_name'],
                    'street1': data['from_street'],
                    'city': data['from_city'],
                    'state': data['from_state'],
                    'zip': data['from_zip'],
                    'country': 'US'
                },
                'address_to': {
                    'name': data['to_name'],
                    'street1': data['to_street'],
                    'city': data['to_city'],
                    'state': data['to_state'],
                    'zip': data['to_zip'],
                    'country': 'US'
                },
                'parcels': [{
                    'length': 5,
                    'width': 5,
                    'height': 5,
                    'weight': weight,
                    'distance_unit': 'in',
                    'mass_unit': 'lb'
                }],
                'async': False
            }
            
            # Add optional street2
            if data.get('from_street2'):
                shipment_data['address_from']['street2'] = data['from_street2']
            if data.get('to_street2'):
                shipment_data['address_to']['street2'] = data['to_street2']
            
            # Add carrier accounts if available
            if carrier_accounts:
                shipment_data['carrier_accounts'] = carrier_accounts
            
            shipment_response = requests.post(
                'https://api.goshippo.com/shipments/',
                headers=headers,
                json=shipment_data
            )
            
            if shipment_response.status_code != 201:
                error_msg = shipment_response.json().get('messages', [{}])[0].get('text', 'Неизвестная ошибка')
                await update.message.reply_text(f"❌ Ошибка при получении тарифов:\n{error_msg}\n\nПроверьте правильность введенных адресов.")
                return ConversationHandler.END
            
            shipment = shipment_response.json()
            
            if not shipment.get('rates') or len(shipment['rates']) == 0:
                await update.message.reply_text("❌ Не удалось получить тарифы. Возможные причины:\n• Неверный ZIP код\n• Недоступный маршрут\n• Проверьте корректность адресов")
                return ConversationHandler.END
            
            # Save rates - show up to 10 carriers with $10 markup
            markup = 10.00  # Markup in USD
            context.user_data['rates'] = [
                {
                    'rate_id': rate['object_id'],
                    'carrier': rate['provider'],
                    'service': rate['servicelevel'].get('name') if isinstance(rate.get('servicelevel'), dict) else str(rate.get('servicelevel', '')),
                    'original_amount': float(rate['amount']),  # Original price from GoShippo
                    'amount': float(rate['amount']) + markup,  # Price shown to user (with markup)
                    'currency': rate['currency'],
                    'days': rate.get('estimated_days')
                }
                for rate in shipment['rates'][:10]  # Show up to 10 rates
            ]
            
            # Create buttons for carrier selection
            message = "📦 Доступные тарифы:\n\n"
            keyboard = []
            
            for i, rate in enumerate(context.user_data['rates']):
                days_text = f" ({rate['days']} дней)" if rate['days'] else ""
                message += f"{i+1}. {rate['carrier']} - {rate['service']}{days_text}\n   💰 ${rate['amount']:.2f}\n\n"
                
                # Show carrier name with price in button
                button_text = f"{rate['carrier']} - ${rate['amount']:.2f}"
                if rate['days']:
                    button_text = f"{rate['carrier']} {rate['days']}д - ${rate['amount']:.2f}"
                
                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'select_carrier_{i}'
                )])
            
            message += f"\n💡 Цена включает доставку + сервисный сбор ${markup:.2f}\n"
            if len(context.user_data['rates']) == 1:
                message += "\n⚠️ В Test mode доступен только USPS.\n"
                message += "Для FedEx, UPS, DHL нужно:\n"
                message += "• Войти на apps.goshippo.com\n"
                message += "• Settings → Carriers\n"
                message += "• Добавить carrier accounts\n\n"
            
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup)
            return SELECT_CARRIER
            
        except Exception as e:
            logger.error(f"Error getting rates: {e}")
            await update.message.reply_text(f"❌ Ошибка при получении тарифов:\n{str(e)}\n\nПроверьте корректность адресов и попробуйте снова.")
            return ConversationHandler.END
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введите число (например: 2 или 2.5):")
        return PARCEL_WEIGHT

async def select_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel_order':
        await cancel_order(update, context)
        return ConversationHandler.END
    
    # Get selected carrier index
    carrier_idx = int(query.data.split('_')[-1])
    selected_rate = context.user_data['rates'][carrier_idx]
    context.user_data['selected_rate'] = selected_rate
    
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

💰 Стоимость:
   Доставка: ${original_amount:.2f}
   Сервисный сбор: ${markup:.2f}
   ──────────────────
   Итого: ${amount:.2f}

💳 Ваш баланс: ${balance:.2f}

Выберите способ оплаты:"""
    
    keyboard = []
    
    if balance >= amount:
        keyboard.append([InlineKeyboardButton(
            f"💳 С баланса (${balance:.2f})",
            callback_data='pay_from_balance'
        )])
    
    keyboard.append([InlineKeyboardButton(
        f"💰 Криптой (${amount})",
        callback_data='pay_with_crypto'
    )])
    
    keyboard.append([
        InlineKeyboardButton("💵 Пополнить", callback_data='top_up_balance'),
        InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(confirmation_text, reply_markup=reply_markup)
    return PAYMENT_METHOD

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel_order':
        await cancel_order(update, context)
        return ConversationHandler.END
    
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
            
            # Deduct from balance
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
            
            # Create shipping label
            await create_and_send_label(order['id'], telegram_id, query.message)
            
            keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"""✅ Заказ оплачен с баланса!
💳 Списано: ${amount}
💰 Новый баланс: ${new_balance:.2f}

Создаю shipping label...""",
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
            # Create top-up invoice
            keyboard = [
                [
                    InlineKeyboardButton("$10", callback_data='topup_10'),
                    InlineKeyboardButton("$25", callback_data='topup_25')
                ],
                [
                    InlineKeyboardButton("$50", callback_data='topup_50'),
                    InlineKeyboardButton("$100", callback_data='topup_100')
                ],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "💵 Выберите сумму пополнения:",
                reply_markup=reply_markup
            )
            # Stay in same state to handle top-up
            return PAYMENT_METHOD
            
        # Handle top-up amounts
        elif query.data.startswith('topup_'):
            topup_amount = float(query.data.split('_')[1])
            
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
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Payment error: {e}")
        await query.message.reply_text(f"❌ Ошибка при оплате: {str(e)}")
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
            country="US"
        ),
        address_to=Address(
            name=data['to_name'],
            street1=data['to_street'],
            street2=data.get('to_street2'),
            city=data['to_city'],
            state=data['to_state'],
            zip=data['to_zip'],
            country="US"
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
    order_dict['rate_id'] = selected_rate['rate_id']
    order_dict['original_amount'] = selected_rate['original_amount']  # Store original GoShippo price
    order_dict['markup'] = amount - selected_rate['original_amount']  # Store markup amount
    await db.orders.insert_one(order_dict)
    
    return order_dict

async def create_and_send_label(order_id, telegram_id, message):
    try:
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        
        from shippo import Shippo
        from shippo.models import components
        
        shippo_client = Shippo(api_key_header=SHIPPO_API_KEY)
        
        # Purchase label with saved rate_id
        transaction = shippo_client.transactions.create(
            components.TransactionCreateRequest(
                rate=order['rate_id'],
                label_file_type="PDF",
                async_=False
            )
        )
        
        # Save label
        label = ShippingLabel(
            order_id=order_id,
            tracking_number=transaction.tracking_number,
            label_url=transaction.label_url,
            carrier=order['selected_carrier'],
            service_level=order['selected_service'],
            amount=str(order['amount']),  # User paid amount (with markup)
            status='created'
        )
        
        label_dict = label.model_dump()
        label_dict['created_at'] = label_dict['created_at'].isoformat()
        label_dict['original_amount'] = order.get('original_amount')  # GoShippo price
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

Tracking: {transaction.tracking_number}
Carrier: {order['selected_carrier']}
Service: {order['selected_service']}

Label PDF: {transaction.label_url}

Вы оплатили: ${order['amount']:.2f}"""
            )
    except Exception as e:
        logger.error(f"Error creating label: {e}")
        if message:
            await message.reply_text(f"❌ Ошибка при создании label: {str(e)}")

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send_method = query.message.reply_text
    else:
        send_method = update.message.reply_text
    
    context.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_method("❌ Создание заказа отменено.", reply_markup=reply_markup)
    return ConversationHandler.END

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
        
        if not SHIPPO_API_KEY:
            raise HTTPException(status_code=500, detail="Shippo API not configured")
        
        # Initialize shippo client
        from shippo import Shippo
        shippo_client = Shippo(api_key_header=SHIPPO_API_KEY)
        
        # Create shipment
        address_from = order['address_from']
        address_to = order['address_to']
        parcel = order['parcel']
        
        from shippo.models import components
        
        shipment = shippo_client.shipments.create(
            components.ShipmentCreateRequest(
                address_from=components.AddressCreateRequest(**address_from),
                address_to=components.AddressCreateRequest(**address_to),
                parcels=[components.ParcelCreateRequest(**parcel)],
                async_=False
            )
        )
        
        if not shipment.rates or len(shipment.rates) == 0:
            raise HTTPException(status_code=400, detail="No shipping rates available")
        
        # Select cheapest rate
        rate = min(shipment.rates, key=lambda x: float(x.amount))
        
        # Purchase label
        transaction = shippo_client.transactions.create(
            components.TransactionCreateRequest(
                rate=rate.object_id,
                label_file_type="PDF",
                async_=False
            )
        )
        
        # Save label
        label = ShippingLabel(
            order_id=order_id,
            tracking_number=transaction.tracking_number,
            label_url=transaction.label_url,
            carrier=rate.provider,
            service_level=rate.servicelevel.name if hasattr(rate.servicelevel, 'name') else str(rate.servicelevel),
            amount=str(rate.amount),
            status='created'
        )
        
        label_dict = label.model_dump()
        label_dict['created_at'] = label_dict['created_at'].isoformat()
        await db.shipping_labels.insert_one(label_dict)
        
        # Update order
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"shipping_status": "label_created"}}
        )
        
        # Notify user
        if bot_instance:
            await bot_instance.send_message(
                chat_id=order['telegram_id'],
                text=f"""📦 Shipping label создан!

Tracking: {transaction.tracking_number}
Carrier: {rate.provider}

Label: {transaction.label_url}"""
            )
        
        return label_dict
        
    except Exception as e:
        logger.error(f"Error creating label: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/shipping/track/{tracking_number}")
async def track_shipment(tracking_number: str, carrier: str):
    try:
        if not SHIPPO_API_KEY:
            raise HTTPException(status_code=500, detail="Shippo API not configured")
        
        from shippo import Shippo
        shippo_client = Shippo(api_key_header=SHIPPO_API_KEY)
        
        tracking = shippo_client.tracks.get_status(carrier, tracking_number)
        
        return {
            "tracking_number": tracking_number,
            "carrier": carrier,
            "status": tracking.tracking_status.status if hasattr(tracking, 'tracking_status') and tracking.tracking_status else "UNKNOWN",
            "tracking_history": tracking.tracking_history if hasattr(tracking, 'tracking_history') else []
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
                    FROM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_name)],
                    FROM_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_address)],
                    FROM_ADDRESS2: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_address2),
                        CallbackQueryHandler(skip_from_address2, pattern='^skip_from_address2$')
                    ],
                    FROM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_city)],
                    FROM_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_state)],
                    FROM_ZIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_zip)],
                    TO_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_name)],
                    TO_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_address)],
                    TO_ADDRESS2: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_address2),
                        CallbackQueryHandler(skip_to_address2, pattern='^skip_to_address2$')
                    ],
                    TO_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_city)],
                    TO_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_state)],
                    TO_ZIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_zip)],
                    PARCEL_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_weight)],
                    SELECT_CARRIER: [CallbackQueryHandler(select_carrier, pattern='^(select_carrier_|cancel_order)')],
                    PAYMENT_METHOD: [CallbackQueryHandler(process_payment, pattern='^(pay_from_balance|pay_with_crypto|top_up_balance|topup_|cancel_order)')]
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