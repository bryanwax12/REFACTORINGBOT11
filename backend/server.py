from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
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
    
    # Create keyboard with buttons
    keyboard = [
        [InlineKeyboardButton("📦 Создать заказ", callback_data='new_order')],
        [InlineKeyboardButton("📋 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("🔍 Отследить посылку", callback_data='track')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help')]
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
    elif query.data == 'track':
        await track_command(update, context)
    elif query.data == 'help':
        await help_command(update, context)
    elif query.data == 'new_order':
        await new_order_start(update, context)
    elif query.data == 'cancel_order':
        await cancel_order(update, context)

# Conversation states for order creation
AMOUNT, FROM_NAME, FROM_ADDRESS, FROM_CITY, FROM_STATE, FROM_ZIP, TO_NAME, TO_ADDRESS, TO_CITY, TO_STATE, TO_ZIP, CONFIRM = range(12)

async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        """📦 Создание нового заказа

Шаг 1/11: Укажите сумму заказа в USDT
Например: 25.00""",
        reply_markup=reply_markup
    )
    return AMOUNT

async def order_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше 0. Попробуйте еще раз:")
            return AMOUNT
        
        context.user_data['amount'] = amount
        
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"""✅ Сумма: ${amount} USDT

Шаг 2/11: Имя отправителя
Например: John Smith""",
            reply_markup=reply_markup
        )
        return FROM_NAME
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введите число, например: 25.00")
        return AMOUNT

async def order_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['from_name'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 3/11: Адрес отправителя
Например: 215 Clayton St.""",
        reply_markup=reply_markup
    )
    return FROM_ADDRESS

async def order_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['from_street'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 4/11: Город отправителя
Например: San Francisco""",
        reply_markup=reply_markup
    )
    return FROM_CITY

async def order_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['from_city'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 5/11: Штат отправителя (2 буквы)
Например: CA""",
        reply_markup=reply_markup
    )
    return FROM_STATE

async def order_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['from_state'] = update.message.text.upper()
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 6/11: ZIP код отправителя
Например: 94117""",
        reply_markup=reply_markup
    )
    return FROM_ZIP

async def order_from_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['from_zip'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """✅ Адрес отправителя сохранен

Шаг 7/11: Имя получателя
Например: Jane Doe""",
        reply_markup=reply_markup
    )
    return TO_NAME

async def order_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['to_name'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 8/11: Адрес получателя
Например: 123 Main St.""",
        reply_markup=reply_markup
    )
    return TO_ADDRESS

async def order_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['to_street'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 9/11: Город получателя
Например: New York""",
        reply_markup=reply_markup
    )
    return TO_CITY

async def order_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['to_city'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 10/11: Штат получателя (2 буквы)
Например: NY""",
        reply_markup=reply_markup
    )
    return TO_STATE

async def order_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['to_state'] = update.message.text.upper()
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        """Шаг 11/11: ZIP код получателя
Например: 10007""",
        reply_markup=reply_markup
    )
    return TO_ZIP

async def order_to_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['to_zip'] = update.message.text
    
    # Show confirmation
    data = context.user_data
    confirmation_text = f"""📦 Проверьте данные заказа:

💰 Сумма: ${data['amount']} USDT

📤 Отправитель:
{data['from_name']}
{data['from_street']}
{data['from_city']}, {data['from_state']} {data['from_zip']}

📥 Получатель:
{data['to_name']}
{data['to_street']}
{data['to_city']}, {data['to_state']} {data['to_zip']}

📦 Посылка: 5x5x5 дюймов, 2 фунта (стандарт)

Всё верно?"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Создать заказ", callback_data='confirm_order')],
        [InlineKeyboardButton("❌ Отменить", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
    return CONFIRM

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cancel_order':
        await cancel_order(update, context)
        return ConversationHandler.END
    
    # Create order
    try:
        data = context.user_data
        telegram_id = query.from_user.id
        
        # Check user exists
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        # Create order
        order = Order(
            user_id=user['id'],
            telegram_id=telegram_id,
            address_from=Address(
                name=data['from_name'],
                street1=data['from_street'],
                city=data['from_city'],
                state=data['from_state'],
                zip=data['from_zip'],
                country="US"
            ),
            address_to=Address(
                name=data['to_name'],
                street1=data['to_street'],
                city=data['to_city'],
                state=data['to_state'],
                zip=data['to_zip'],
                country="US"
            ),
            parcel=Parcel(
                length=5,
                width=5,
                height=5,
                weight=2,
                distance_unit="in",
                mass_unit="lb"
            ),
            amount=data['amount']
        )
        
        order_dict = order.model_dump()
        order_dict['created_at'] = order_dict['created_at'].isoformat()
        await db.orders.insert_one(order_dict)
        
        # Create crypto payment invoice
        if crypto:
            invoice = await crypto.create_invoice(
                asset="USDT",
                amount=data['amount']
            )
            
            pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'mini_app_invoice_url', None)
            
            payment = Payment(
                order_id=order.id,
                amount=data['amount'],
                invoice_id=invoice.invoice_id,
                pay_url=pay_url
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            await db.payments.insert_one(payment_dict)
            
            # Send payment link
            keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"""✅ Заказ создан!

💰 Оплатите {data['amount']} USDT:
{pay_url}

После оплаты мы автоматически создадим shipping label и отправим вам tracking number.""",
                reply_markup=reply_markup
            )
        else:
            keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                "✅ Заказ создан, но система оплаты не настроена.",
                reply_markup=reply_markup
            )
        
        # Clear user data
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        await query.message.reply_text(f"❌ Ошибка при создании заказа: {str(e)}")
        return ConversationHandler.END

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
                    
                    # Update order
                    await db.orders.update_one(
                        {"id": payment['order_id']},
                        {"$set": {"payment_status": "paid"}}
                    )
                    
                    # Auto-create shipping label
                    try:
                        await create_shipping_label(payment['order_id'])
                    except Exception as e:
                        logging.error(f"Failed to create label: {e}")
        
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return {"status": "error"}

@api_router.get("/users")
async def get_users():
    users = await db.users.find({}, {"_id": 0}).to_list(100)
    return users

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
                    AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_amount)],
                    FROM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_name)],
                    FROM_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_address)],
                    FROM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_city)],
                    FROM_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_state)],
                    FROM_ZIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_zip)],
                    TO_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_name)],
                    TO_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_address)],
                    TO_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_city)],
                    TO_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_state)],
                    TO_ZIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_to_zip)],
                    CONFIRM: [CallbackQueryHandler(confirm_order, pattern='^(confirm_order|cancel_order)$')]
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