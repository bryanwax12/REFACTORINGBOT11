from fastapi import FastAPI, APIRouter, HTTPException, Request, Header, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from bot_protection import BotProtection, get_copyright_footer, PROTECTED_BADGE, VERSION_WATERMARK
from telegram_safety import TelegramSafetySystem, TelegramBestPractices
from middleware.security import SecurityMiddleware, security_manager, audit_logger
import os
import logging
import random
import httpx
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import time
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
import telegram.error
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import asyncio
import hashlib
import hmac
import warnings

# Suppress PTBUserWarning about per_message settings (expected behavior)
try:
    from telegram.warnings import PTBUserWarning
    warnings.filterwarnings("ignore", category=PTBUserWarning)
except ImportError:
    # Fallback if PTBUserWarning not available
    warnings.filterwarnings("ignore", message=".*per_message.*")

# Performance monitoring
from utils.performance import profile_db_query, profile_api_call, QueryTimer

# API Services
from services.api_services import (
    create_oxapay_invoice,
    check_oxapay_payment,
    check_shipstation_balance,
    get_shipstation_carrier_ids,
    validate_address_with_shipstation
)

# Business Logic Services
from services import payment_service, template_service
from services.shipping_service import (
    display_shipping_rates as display_rates_service,
    validate_shipping_address,
    validate_parcel_data
)

# Common handlers (start, help, faq, button routing)
from handlers.common_handlers import (
    start_command,
    help_command,
    faq_command,
    button_callback,
    mark_message_as_selected,
    safe_telegram_call,
    check_user_blocked,
    send_blocked_message,
    check_maintenance_mode
)

# Admin handlers
from handlers.admin_handlers import (
    verify_admin_key,
    notify_admin_error,
    get_stats_data,
    get_expense_stats_data
)

# Webhook handlers
from handlers.webhook_handlers import (
    handle_oxapay_webhook,
    handle_telegram_webhook
)

# Order flow handlers
from handlers.order_flow import (
    # FROM address handlers
    order_from_name, order_from_address, order_from_city,
    order_from_state, order_from_zip, order_from_phone,
    # TO address handlers
    order_to_name, order_to_address, order_to_city,
    order_to_state, order_to_zip, order_to_phone,
    # Parcel handlers
    order_parcel_weight, order_parcel_length,
    order_parcel_width, order_parcel_height,
    # Skip handlers (NEW - refactored)
    skip_from_address2, skip_to_address2,
    skip_from_phone, skip_to_phone
)

# Import address2 handlers directly since they're not in __init__.py yet
from handlers.order_flow.from_address import order_from_address2
from handlers.order_flow.to_address import order_to_address2

# Profiled DB operations (most frequently used)
@profile_db_query("find_user_by_telegram_id")
async def find_user_by_telegram_id(telegram_id: int, projection: dict = None):
    """
    Профилируемый поиск пользователя по telegram_id
    
    Args:
        telegram_id: Telegram user ID
        projection: Optional projection dict (default: {"_id": 0})
    
    Returns:
        User document or None
    """
    if projection is None:
        projection = {"_id": 0}
    return await db.users.find_one({"telegram_id": telegram_id}, projection)

@profile_db_query("find_order_by_id")
async def find_order_by_id(order_id: str, projection: dict = None):
    """Профилируемый поиск заказа по ID"""
    if projection is None:
        projection = {"_id": 0}
    return await db.orders.find_one({"id": order_id}, projection)

@profile_db_query("find_template_by_id")
async def find_template_by_id(template_id: str, projection: dict = None):
    """Профилируемый поиск шаблона по ID"""
    if projection is None:
        projection = {"_id": 0}
    return await db.templates.find_one({"id": template_id}, projection)

# Additional profiled DB operations for performance monitoring
@profile_db_query("find_payment_by_invoice")
async def find_payment_by_invoice(invoice_id: int, projection: dict = None):
    """Профилируемый поиск платежа по invoice_id"""
    if projection is None:
        projection = {"_id": 0}
    return await db.payments.find_one({"invoice_id": invoice_id}, projection)

@profile_db_query("find_pending_order")
async def find_pending_order(telegram_id: int, projection: dict = None):
    """Профилируемый поиск незавершенного заказа"""
    if projection is None:
        projection = {"_id": 0}
    return await db.pending_orders.find_one({"telegram_id": telegram_id}, projection)

@profile_db_query("count_user_templates")
async def count_user_templates(telegram_id: int):
    """Профилируемый подсчет шаблонов пользователя"""
    return await db.templates.count_documents({"telegram_id": telegram_id})

@profile_db_query("find_user_templates")
async def find_user_templates(telegram_id: int, limit: int = 10):
    """Профилируемый поиск шаблонов пользователя"""
    return await db.templates.find({"telegram_id": telegram_id}).sort("created_at", -1).to_list(limit)

@profile_db_query("update_order")
async def update_order(order_id: str, update_data: dict):
    """Профилируемое обновление заказа"""
    return await db.orders.update_one({"id": order_id}, {"$set": update_data})

@profile_db_query("insert_payment")
async def insert_payment(payment_dict: dict):
    """Профилируемая вставка платежа"""
    return await db.payments.insert_one(payment_dict)

@profile_db_query("insert_pending_order")
async def insert_pending_order(order_dict: dict):
    """Профилируемая вставка незавершенного заказа"""
    return await db.pending_orders.insert_one(order_dict)

@profile_db_query("delete_pending_order")
async def delete_pending_order(telegram_id: int):
    """Профилируемое удаление незавершенного заказа"""
    return await db.pending_orders.delete_one({"telegram_id": telegram_id})

@profile_db_query("insert_template")
async def insert_template(template_dict: dict):
    """Профилируемая вставка шаблона"""
    return await db.templates.insert_one(template_dict)

@profile_db_query("update_template")
async def update_template(template_id: str, update_data: dict):
    """Профилируемое обновление шаблона"""
    return await db.templates.update_one({"id": template_id}, {"$set": update_data})

@profile_db_query("delete_template")
async def delete_template(template_id: str):
    """Профилируемое удаление шаблона"""
    return await db.templates.delete_one({"id": template_id})

# Debug logging removed - was causing startup issues

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection with connection pooling for high load
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=20,  # Optimized for Preview environment (was 200)
    minPoolSize=2,   # Lower minimum for resource efficiency (was 10)
    maxIdleTimeMS=30000,  # Close idle connections faster (was 45000)
    waitQueueTimeoutMS=3000,  # Shorter wait time (was 5000)
    serverSelectionTimeoutMS=3000,  # Faster timeout (was 5000)
    connectTimeoutMS=3000  # Add connection timeout
)

# Auto-select database name based on environment
webhook_base_url_for_db = os.environ.get('WEBHOOK_BASE_URL', '')
if 'crypto-shipping.emergent.host' in webhook_base_url_for_db:
    # Production environment
    db_name = os.environ.get('DB_NAME_PRODUCTION', 'async-tg-bot-telegram_shipping_bot')
    print(f"🟢 PRODUCTION DATABASE: {db_name}")
else:
    # Preview environment
    db_name = os.environ.get('DB_NAME_PREVIEW', os.environ.get('DB_NAME', 'telegram_shipping_bot'))
    print(f"🔵 PREVIEW DATABASE: {db_name}")

db = client[db_name]

# Initialize Session Manager for state management
from session_manager import SessionManager
session_manager = SessionManager(db)

# Initialize Repository Manager for data access layer
from repositories import init_repositories, get_repositories
repository_manager = init_repositories(db)
print("📦 Repository Manager initialized successfully")

# In-memory cache for frequently accessed data
from functools import lru_cache

user_balance_cache = {}  # Cache user balances
cache_ttl = 60  # Cache TTL in seconds

# ============================================================
# API CONFIGURATION (Refactored with APIConfigManager)
# ============================================================
from utils.api_config import get_api_config, init_api_config

# Инициализировать API Config Manager
# Окружение определяется автоматически на основе api_mode из БД (см. startup)
api_config_manager = init_api_config('production')

# Legacy переменные для обратной совместимости
# Получаются из APIConfigManager
SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY', '')
SHIPSTATION_CARRIER_IDS = []  # Cache for carrier IDs

# Admin API Key for protecting endpoints
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', '')

# Admin notifications
ADMIN_TELEGRAM_ID = os.environ.get('ADMIN_TELEGRAM_ID', '')

# Channel invite link and ID
CHANNEL_INVITE_LINK = os.environ.get('CHANNEL_INVITE_LINK', '')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '')

# ============================================================
# TELEGRAM BOT CONFIGURATION (Refactored)
# ============================================================
from utils.bot_config import (
    get_bot_config,
    get_bot_token,
    get_bot_username,
    is_webhook_mode,
    is_production_environment
)

# Получить конфигурацию бота
bot_config = get_bot_config()
TELEGRAM_BOT_TOKEN = get_bot_token()

# Вывести информацию о выбранном боте
config_summary = bot_config.get_config_summary()
env_icon = "🟢" if config_summary['is_production'] else "🔵"
mode_icon = "🌐" if config_summary['webhook_enabled'] else "🔄"

print(f"{env_icon} BOT CONFIGURATION:")
print(f"   Environment: {config_summary['environment'].upper()}")
print(f"   Mode: {mode_icon} {config_summary['mode'].upper()}")
print(f"   Active Bot: @{config_summary['bot_username']}")
if config_summary['webhook_enabled'] and config_summary['webhook_url']:
    print(f"   Webhook URL: {config_summary['webhook_url']}")

# Legacy поддержка: создать bot_instance для старого кода
bot_instance = None
application = None  # Global Telegram Application instance for webhook
if TELEGRAM_BOT_TOKEN:
    bot_instance = Bot(token=TELEGRAM_BOT_TOKEN)
    print(f"✅ Bot instance created: @{get_bot_username()}")

# Simple in-memory cache for frequently accessed settings
# Cache moved to utils/cache.py
from utils.cache import SETTINGS_CACHE, CACHE_TTL, get_api_mode_cached


# Button click debouncing - prevent multiple rapid clicks
button_click_tracker = {}  # {user_id: {button_data: last_click_timestamp}}
BUTTON_DEBOUNCE_SECONDS = 0.1  # Максимально быстрый: 100ms между нажатиями

# Rate limiting для защиты от Telegram бана
# Telegram API limits: 30 msg/sec per chat, burst of 20
from collections import defaultdict

class RateLimiter:
    """Smart rate limiter: fast responses, prevents Telegram bans"""
    def __init__(self):
        self.locks = defaultdict(asyncio.Lock)
        self.last_call = defaultdict(float)
        self.min_interval = 0.01  # 10ms minimum between calls (allows 100 msg/sec - максимум)
    
    async def acquire(self, chat_id: int):
        """Acquire lock with minimal delay for fast responses"""
        async with self.locks[chat_id]:
            now = time.time()
            elapsed = now - self.last_call[chat_id]
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_call[chat_id] = time.time()

rate_limiter = RateLimiter()

# Helper function for session management
async def save_to_session(user_id: int, next_step: str, data: dict, context: ContextTypes.DEFAULT_TYPE):
    """Save data to both context.user_data and session manager (V2 - atomic)"""
    context.user_data.update(data)
    await session_manager.update_session_atomic(user_id, step=next_step, data=data)

async def handle_critical_api_error(user_id: int, error_message: str, current_step: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle critical API errors with option to revert to previous step
    
    Shows user a message with options to retry, edit data, or cancel
    """
    # Log to session
    await session_manager.update_session_atomic(user_id, data={
        'last_error': error_message,
        'error_step': current_step,
        'error_timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    keyboard = [
        [InlineKeyboardButton("🔄 Попробовать снова", callback_data='continue_order')],
        [InlineKeyboardButton("✏️ Редактировать данные", callback_data='edit_data')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Show error message with options
    query = update.callback_query
    if query:
        await safe_telegram_call(query.message.reply_text(
            f"❌ Произошла ошибка:\n{error_message}\n\nВыберите действие:",
            reply_markup=reply_markup
        ))
    
    return current_step  # Stay on same step for retry


async def handle_step_error(user_id: int, error: Exception, current_step: str, context: ContextTypes.DEFAULT_TYPE, allow_revert: bool = False):
    """
    Handle errors during step processing
    
    Args:
        user_id: User ID
        error: Exception that occurred
        current_step: Current conversation step
        context: Telegram context
        allow_revert: If True, revert to previous step; if False, retry from same step
    
    Returns:
        int: State to return to (current or previous)
    """
    logger.error(f"❌ Error at step {current_step} for user {user_id}: {error}")
    
    # Save error info to session for debugging
    error_data = {
        'last_error': str(error),
        'error_step': current_step,
        'error_timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if allow_revert:
        # Revert to previous step
        previous_step = await session_manager.revert_to_previous_step(user_id, current_step, str(error))
        if previous_step:
            logger.info(f"🔙 Reverted user {user_id} from {current_step} to {previous_step}")
            # Map step names to ConversationHandler states
            step_to_state = {
                "START": FROM_NAME,
                "FROM_NAME": FROM_NAME,
                "FROM_ADDRESS": FROM_NAME,
                "FROM_ADDRESS2": FROM_ADDRESS,
                "FROM_CITY": FROM_ADDRESS2,
                "FROM_STATE": FROM_CITY,
                "FROM_ZIP": FROM_STATE,
                "FROM_PHONE": FROM_ZIP,
                "TO_NAME": FROM_PHONE,
                "TO_ADDRESS": TO_NAME,
                "TO_ADDRESS2": TO_ADDRESS,
                "TO_CITY": TO_ADDRESS2,
                "TO_STATE": TO_CITY,
                "TO_ZIP": TO_STATE,
                "TO_PHONE": TO_ZIP,
                "PARCEL_WEIGHT": TO_PHONE,
                "PARCEL_LENGTH": PARCEL_WEIGHT,
                "PARCEL_WIDTH": PARCEL_LENGTH,
                "PARCEL_HEIGHT": PARCEL_WIDTH,
                "CONFIRM_DATA": PARCEL_HEIGHT,
                "CARRIER_SELECTION": CONFIRM_DATA,
                "PAYMENT_METHOD": SELECT_CARRIER
            }
            return step_to_state.get(previous_step, current_step)
    else:
        # Save error but stay on same step (retry)
        await session_manager.update_session_atomic(user_id, data=error_data)
    
    # Don't change step - let user retry from same step
    return current_step

def is_button_click_allowed(user_id: int, button_data: str) -> bool:
    """Check if button click is allowed (debouncing)"""
    current_time = datetime.now(timezone.utc).timestamp()
    
    if user_id not in button_click_tracker:
        button_click_tracker[user_id] = {}
    
    last_click = button_click_tracker[user_id].get(button_data, 0)
    
    if current_time - last_click < BUTTON_DEBOUNCE_SECONDS:
        logger.warning(f"Button click blocked for user {user_id}, button {button_data} - too fast")
        return False
    
    button_click_tracker[user_id][button_data] = current_time
    return True

# Oxapay - Cryptocurrency Payment Gateway
OXAPAY_API_KEY = os.environ.get('OXAPAY_API_KEY', '')
OXAPAY_API_URL = 'https://api.oxapay.com'

# Oxapay helper functions - imported from services/api_services.py

def generate_random_phone():
    """Generate a random valid US phone number"""
    # Generate random US phone number in format +1XXXXXXXXXX
    area_code = random.randint(200, 999)  # Valid area codes start from 200
    exchange = random.randint(200, 999)   # Valid exchanges start from 200
    number = random.randint(1000, 9999)   # Last 4 digits
    return f"+1{area_code}{exchange}{number}"

def clear_settings_cache():
    """Clear settings cache when settings are updated"""
    SETTINGS_CACHE['api_mode'] = None
    SETTINGS_CACHE['api_mode_timestamp'] = None
    SETTINGS_CACHE['maintenance_mode'] = None
    SETTINGS_CACHE['maintenance_timestamp'] = None

# check_shipstation_balance - imported from services/api_services.py

async def generate_thank_you_message():
    """Generate a unique thank you message using AI"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        emergent_key = os.environ.get('EMERGENT_LLM_KEY')
        if not emergent_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment")
        
        # Generate unique session ID
        session_id = f"thanks_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        
        # Initialize chat with model
        chat = LlmChat(
            api_key=emergent_key,
            session_id=session_id,
            system_message="Ты помощник, который создает теплые и дружелюбные слова благодарности на русском языке для клиентов, которые воспользовались сервисом доставки."
        )
        chat = chat.with_model("openai", "gpt-4o")
        
        # Create user message
        user_message = UserMessage(
            text="Создай короткое теплое сообщение благодарности (2-3 предложения) клиенту за использование нашего сервиса доставки. Дружелюбный тон, только текст без эмодзи. Каждый раз создавай РАЗНОЕ уникальное сообщение."
        )
        
        # Get response
        response = await chat.send_message(user_message)
        
        if response and len(response.strip()) > 10:
            logger.info(f"Generated thank you message: {response[:50]}...")
            return response.strip()
        else:
            raise ValueError("Empty or invalid response from AI")
            
    except Exception as e:
        logger.error(f"Error generating thank you message: {e}")
        # Use varied fallback messages
        fallback_messages = [
            "Спасибо за использование нашего сервиса! Желаем вам приятной доставки.",
            "Благодарим вас за доверие! Надеемся, что наш сервис оправдал ваши ожидания.",
            "Спасибо, что выбрали нас! Мы ценим ваше время и доверие.",
            "Благодарим за заказ! Желаем, чтобы ваша посылка прибыла быстро и в целости.",
            "Спасибо за сотрудничество! Будем рады видеть вас снова."
        ]
        return random.choice(fallback_messages)

app = FastAPI(title="Telegram Shipping Bot")
api_router = APIRouter(prefix="/api")

# ==================== SECURITY ====================

# Input Sanitization
import re
import html

def sanitize_string(text: str, max_length: int = 200) -> str:
    """Sanitize input string to prevent injection attacks"""
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Escape HTML
    text = html.escape(text)
    
    # Remove potentially dangerous characters
    text = re.sub(r'[<>"\']', '', text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()

# sanitize_address and sanitize_phone removed - unused functions

# Security Logging
class SecurityLogger:
    @staticmethod
    async def log_action(action: str, user_id: Optional[int], details: dict, status: str = "success"):
        """Log security-relevant actions"""
        try:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "user_id": user_id,
                "details": details,
                "status": status
            }
            
            # Log to MongoDB
            await db.security_logs.insert_one(log_entry)
            
            # Also log to file for critical actions
            if status == "failure" or action in ["refund", "balance_change", "discount_set"]:
                logging.warning(f"SECURITY: {action} - User: {user_id} - Status: {status} - Details: {details}")
                
        except Exception as e:
            logging.error(f"Failed to log security action: {e}")

# Admin API Key Dependency

# verify_admin_key moved to handlers/admin_handlers.py

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests for security monitoring"""
    start_time = datetime.now(timezone.utc)
    
    # Log request
    if request.url.path.startswith("/api/"):
        logging.info(f"REQUEST: {request.method} {request.url.path} - IP: {request.client.host}")
    
    response = await call_next(request)
    
    # Log response time
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    if duration > 5:  # Log slow requests
        logging.warning(f"SLOW REQUEST: {request.method} {request.url.path} - Duration: {duration}s")
    
    return response

# ==================== END SECURITY ====================


# Models
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    balance: float = 0.0
    blocked: bool = False
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
    label_id: Optional[str] = None  # ShipStation label ID for voiding
    shipment_id: Optional[str] = None  # ShipStation shipment ID
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
    order_id: str  # Unique tracking ID for user display (e.g., "ORD-20251114-a3f8d2b4")
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

class Template(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    telegram_id: int
    name: str  # User-defined template name
    # From address
    from_name: str
    from_street1: str
    from_street2: Optional[str] = None
    from_city: str
    from_state: str
    from_zip: str
    from_phone: Optional[str] = None
    # To address
    to_name: str
    to_street1: str
    to_street2: Optional[str] = None
    to_city: str
    to_state: str
    to_zip: str
    to_phone: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Telegram Bot Handlers
async def test_error_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test command to show error message with admin contact button"""
    user_message = """😔 К сожалению, в данный момент мы не можем сгенерировать shipping label.

Пожалуйста, свяжитесь с администратором.

Приносим извинения за неудобства!"""
    
    # Add button to contact admin
    keyboard = []
    if ADMIN_TELEGRAM_ID:
        keyboard.append([InlineKeyboardButton("💬 Связаться с администратором", url=f"tg://user?id={ADMIN_TELEGRAM_ID}")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(update.message.reply_text(user_message, reply_markup=reply_markup))

# Helper function to check if user is blocked
# check_user_blocked and send_blocked_message moved to handlers/common_handlers.py

async def handle_orphaned_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses that are not caught by any active handler (orphaned buttons)"""
    query = update.callback_query
    
    # Ignore menu buttons (start, help, etc)
    if query.data in ['start', 'help', 'contact_admin', 'my_templates']:
        return
    
    logger.info(f"Orphaned button detected: {query.data} from user {update.effective_user.id}")
    
    await safe_telegram_call(query.answer("⚠️ Этот заказ уже завершён"))
    await safe_telegram_call(query.message.reply_text(
        "⚠️ *Этот заказ уже завершён или отменён.*\n\n"
        "Для создания нового заказа используйте меню в нижней части экрана.",
        parse_mode='Markdown'
    ))

async def check_stale_interaction(query, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if button press is from an old/completed interaction"""
    logger.info(f"check_stale_interaction called - user_data keys: {list(context.user_data.keys())}")
    
    # Check for rapid multiple clicks (debouncing)
    user_id = query.from_user.id
    button_data = query.data
    
    if not is_button_click_allowed(user_id, button_data):
        await safe_telegram_call(query.answer("⚠️ Пожалуйста, подождите..."))
        return True  # Block this interaction
    
    # If user_data is empty or doesn't have active order data, it's likely stale
    if not context.user_data or len(context.user_data) == 0:
        logger.info("Stale interaction detected - empty user_data")
        await safe_telegram_call(query.answer("⚠️ Этот заказ уже завершён"))
        await safe_telegram_call(query.message.reply_text(
            "⚠️ *Этот заказ уже завершён или отменён.*\n\n"
            "Для создания нового заказа используйте меню в нижней части экрана.",
            parse_mode='Markdown'
        ))
        return True
    
    # Check if order was already completed (has order_completed flag)
    if context.user_data.get('order_completed'):
        logger.info("Stale interaction detected - order_completed flag set")
        await safe_telegram_call(query.answer("⚠️ Этот заказ уже завершён"))
        await safe_telegram_call(query.message.reply_text(
            "⚠️ *Этот заказ уже завершён.*\n\n"
            "Для создания нового заказа используйте меню в нижней части экрана.",
            parse_mode='Markdown'
        ))
        return True
    
    logger.info("Interaction is valid - proceeding")
    return False

# mark_message_as_selected_nonblocking removed - unused function (mark_message_as_selected is called directly)

# safe_telegram_call moved to handlers/common_handlers.py

# mark_message_as_selected moved to handlers/common_handlers.py

# check_maintenance_mode moved to handlers/common_handlers.py

# start_command and help_command moved to handlers/common_handlers.py


# faq_command moved to handlers/common_handlers.py



async def handle_create_label_request(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str):
    """Handle request to create/recreate shipping label for existing paid order"""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    # Get order details
    order = await db.orders.find_one({"id": order_id, "telegram_id": telegram_id}, {"_id": 0})
    
    if not order:
        await safe_telegram_call(query.message.reply_text("❌ Заказ не найден."))
        return
    
    if order['payment_status'] != 'paid':
        await safe_telegram_call(query.message.reply_text("❌ Заказ не оплачен. Создание лейбла невозможно."))
        return
    
    # Show confirmation message
    if order['shipping_status'] == 'label_created':
        await safe_telegram_call(query.message.reply_text(f"""⏳ Пересоздаю shipping label для заказа #{order_id[:8]}...)
    
Это может занять несколько секунд."""))
    else:
        await safe_telegram_call(query.message.reply_text(f"""⏳ Создаю shipping label для заказа #{order_id[:8]}...)
    
Это может занять несколько секунд."""))
    
    # Try to create label
    label_created = await create_and_send_label(order_id, telegram_id, query.message)
    
    if label_created:
        # Update order payment status to paid (if it was failed before)
        await update_order(order_id, {"payment_status": "paid"})
        
        keyboard = [[
            InlineKeyboardButton("🔙 Главное меню", callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            "✅ Shipping label успешно создан!",
            reply_markup=reply_markup
        ))
    else:
        keyboard = [[
            InlineKeyboardButton("🔙 Главное меню", callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            "❌ Не удалось создать shipping label. Пожалуйста, свяжитесь с администратором.",
            reply_markup=reply_markup
        ))

# button_callback moved to handlers/common_handlers.py

async def my_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        telegram_id = query.from_user.id
        
        # Load message context from database if this is a callback from payment screen
        payment_record = await db.payments.find_one(
            {"telegram_id": telegram_id, "type": "topup", "status": "pending"},
            {"_id": 0},
            sort=[("created_at", -1)]  # Get latest pending payment
        )
        
        logger.info(f"Payment record found: {payment_record is not None}")
        if payment_record and payment_record.get('payment_message_id'):
            logger.info(f"Payment message_id: {payment_record.get('payment_message_id')}")
            context.user_data['last_bot_message_id'] = payment_record['payment_message_id']
            context.user_data['last_bot_message_text'] = payment_record.get('payment_message_text', '')
        
        logger.info(f"Context before mark_message_as_selected: last_bot_message_id={context.user_data.get('last_bot_message_id')}")
        
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        
        send_method = query.message.reply_text
    else:
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        telegram_id = update.effective_user.id
        send_method = update.message.reply_text
    
    # Check if user is blocked
    if await check_user_blocked(telegram_id):
        await send_blocked_message(update)
        return
    
    # Get balance using Repository Pattern
    from repositories import get_user_repo
    user_repo = get_user_repo()
    balance = await user_repo.get_balance(telegram_id)
    
    from utils.ui_utils import PaymentFlowUI
    message = PaymentFlowUI.balance_screen(balance)
    reply_markup = PaymentFlowUI.build_balance_keyboard()
    
    # Set state to wait for amount input
    context.user_data['awaiting_topup_amount'] = True
    
    # Send message and save context for mark_message_as_selected
    bot_message = await send_method(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Always save message context for button protection
    context.user_data['last_bot_message_id'] = bot_message.message_id
    context.user_data['last_bot_message_text'] = message

async def handle_topup_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom topup amount input"""
    if not context.user_data.get('awaiting_topup_amount'):
        return
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    try:
        amount = float(update.message.text.strip())
        
        from utils.ui_utils import PaymentFlowUI
        if amount < 10:
            await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_amount_too_small(), parse_mode='Markdown'))
            return
        
        if amount > 10000:
            await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_amount_too_large(), parse_mode='Markdown'))
            return
        
        # Clear the waiting flag
        context.user_data['awaiting_topup_amount'] = False
        
        telegram_id = update.effective_user.id
        
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            await safe_telegram_call(update.message.reply_text("❌ Пользователь не найден"))
            return
        
        # Create Oxapay invoice (order_id must be <= 50 chars)
        # Generate short order_id: "top_" (4) + timestamp (10) + "_" (1) + random (8) = 23 chars
        order_id = f"top_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        invoice_result = await create_oxapay_invoice(
            amount=amount,
            order_id=order_id,
            description=f"Balance Top-up ${amount}"
        )
        
        if invoice_result.get('success'):
            track_id = invoice_result['trackId']
            pay_link = invoice_result['payLink']
            
            # Save top-up payment with topup input message_id for button removal
            topup_input_message_id = context.user_data.get('last_bot_message_id')  # Message with "Назад" buttons
            
            payment = Payment(
                order_id=f"topup_{user['id']}",
                amount=amount,
                invoice_id=track_id,
                pay_url=pay_link,
                status="pending"
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            payment_dict['telegram_id'] = telegram_id
            payment_dict['type'] = 'topup'
            payment_dict['topup_input_message_id'] = topup_input_message_id  # Save for later button removal
            await insert_payment(payment_dict)
            
            keyboard = [
                [InlineKeyboardButton("💳 Оплатить", url=pay_link)],
                [InlineKeyboardButton("◀️ Назад", callback_data='my_balance')],
                [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""*✅ Счёт на пополнение создан!*

*💵 Сумма: ${amount}*
*🪙 Криптовалюта: Любая из доступных*

*Нажмите кнопку "Оплатить" для перехода на страницу оплаты.*
*На платежной странице вы сможете выбрать удобную криптовалюту.*

⚠️❗️❗️ *ВАЖНО: Оплатите точно ${amount}!* ❗️❗️⚠️
_Если вы оплатите другую сумму, деньги не поступят на баланс._

*После успешной оплаты баланс будет автоматически пополнен.*"""
            
            bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
            
            # Save last bot message context for button protection
            if bot_msg:
                context.user_data['last_bot_message_id'] = bot_msg.message_id
                context.user_data['last_bot_message_text'] = message_text
        else:
            from utils.ui_utils import PaymentFlowUI
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_invoice_error(error_msg), parse_mode='Markdown'))
            
    except ValueError:
        from utils.ui_utils import PaymentFlowUI
        await safe_telegram_call(update.message.reply_text(PaymentFlowUI.topup_invalid_format(), parse_mode='Markdown'))

# Conversation states for order creation
FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, FROM_STATE, FROM_ZIP, FROM_PHONE, TO_NAME, TO_ADDRESS, TO_ADDRESS2, TO_CITY, TO_STATE, TO_ZIP, TO_PHONE, PARCEL_WEIGHT, PARCEL_LENGTH, PARCEL_WIDTH, PARCEL_HEIGHT, CONFIRM_DATA, EDIT_MENU, SELECT_CARRIER, PAYMENT_METHOD, TOPUP_AMOUNT, TEMPLATE_NAME, TEMPLATE_LIST, TEMPLATE_VIEW, TEMPLATE_RENAME, TEMPLATE_LOADED = range(28)

# State names mapping for consistent string-based state storage
STATE_NAMES = {
    FROM_NAME: "FROM_NAME",
    FROM_ADDRESS: "FROM_ADDRESS",
    FROM_ADDRESS2: "FROM_ADDRESS2",
    FROM_CITY: "FROM_CITY",
    FROM_STATE: "FROM_STATE",
    FROM_ZIP: "FROM_ZIP",
    FROM_PHONE: "FROM_PHONE",
    TO_NAME: "TO_NAME",
    TO_ADDRESS: "TO_ADDRESS",
    TO_ADDRESS2: "TO_ADDRESS2",
    TO_CITY: "TO_CITY",
    TO_STATE: "TO_STATE",
    TO_ZIP: "TO_ZIP",
    TO_PHONE: "TO_PHONE",
    PARCEL_WEIGHT: "PARCEL_WEIGHT",
    PARCEL_LENGTH: "PARCEL_LENGTH",
    PARCEL_WIDTH: "PARCEL_WIDTH",
    PARCEL_HEIGHT: "PARCEL_HEIGHT",
    CONFIRM_DATA: "CONFIRM_DATA",
    EDIT_MENU: "EDIT_MENU",
    SELECT_CARRIER: "SELECT_CARRIER",
    PAYMENT_METHOD: "PAYMENT_METHOD",
    TOPUP_AMOUNT: "TOPUP_AMOUNT",
    TEMPLATE_NAME: "TEMPLATE_NAME",
    TEMPLATE_LIST: "TEMPLATE_LIST",
    TEMPLATE_VIEW: "TEMPLATE_VIEW",
    TEMPLATE_RENAME: "TEMPLATE_RENAME",
    TEMPLATE_LOADED: "TEMPLATE_LOADED"
}

async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        # INSTANT feedback: answer immediately without wrapper
        try:
            await query.answer()
        except Exception:
            pass
        
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        
        telegram_id = query.from_user.id
        send_method = query.message.reply_text
    else:
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        telegram_id = update.effective_user.id
        send_method = update.message.reply_text
    logger.info(f"📝 User {telegram_id} starting new order flow")
    
    # STEP 2: Get or create session (V2 - atomic with TTL)
    user_id = update.effective_user.id
    
    # Атомарно получить существующую сессию или создать новую
    # TTL индекс автоматически удаляет сессии старше 15 минут
    session = await session_manager.get_or_create_session(user_id, initial_data={})
    
    if session:
        current_step = session.get('current_step', 'START')
        temp_data = session.get('temp_data', {})
        
        if current_step != 'START' and temp_data:
            # Есть незавершенная сессия - продолжить
            logger.info(f"🔄 Resuming session for user {user_id} from step {current_step}")
            context.user_data.update(temp_data)
        else:
            # Новая сессия
            logger.info(f"🆕 New session for user {user_id}")
            context.user_data.clear()
    else:
        logger.error(f"❌ Failed to get/create session for user {user_id}")
        context.user_data.clear()
    
    # Check if bot is in maintenance mode
    from utils.ui_utils import MessageTemplates
    if await check_maintenance_mode(update):
        await safe_telegram_call(send_method(
            MessageTemplates.maintenance_mode(),
            parse_mode='Markdown'
        ))
        return ConversationHandler.END
    
    # Check if user is blocked
    if await check_user_blocked(telegram_id):
        await send_blocked_message(update)
        return ConversationHandler.END
    
    # Check if user has templates
    templates_count = await count_user_templates(telegram_id)
    
    from utils.ui_utils import get_new_order_choice_keyboard, get_cancel_keyboard, OrderFlowMessages
    
    if templates_count > 0:
        # Show choice: New order or From template
        reply_markup = get_new_order_choice_keyboard()
        
        await safe_telegram_call(send_method(
            OrderFlowMessages.create_order_choice(),
            reply_markup=reply_markup
        ))
        return FROM_NAME  # Waiting for choice
    else:
        # No templates, go straight to new order
        reply_markup = get_cancel_keyboard()
        
        message_text = OrderFlowMessages.new_order_start()
        bot_msg = await safe_telegram_call(send_method(
            message_text,
            reply_markup=reply_markup
        ))
        
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
            context.user_data['last_state'] = STATE_NAMES[FROM_NAME]
        return FROM_NAME


# Skip handlers moved to handlers/order_flow/skip_handlers.py


async def show_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show summary of entered data with edit option"""
    from utils.ui_utils import DataConfirmationUI
    
    data = context.user_data
    
    # Format the summary message using UI utils
    message = DataConfirmationUI.confirmation_header()
    message += DataConfirmationUI.format_address_section("Отправитель", data, "from")
    message += DataConfirmationUI.format_address_section("Получатель", data, "to")
    message += DataConfirmationUI.format_parcel_section(data)
    
    # Build keyboard using UI utils
    reply_markup = DataConfirmationUI.build_confirmation_keyboard()
    
    # Check if it's a message or callback query
    if hasattr(update, 'callback_query') and update.callback_query:
        bot_msg = await safe_telegram_call(update.callback_query.message.reply_text(message, reply_markup=reply_markup))
    else:
        bot_msg = await safe_telegram_call(update.message.reply_text(message, reply_markup=reply_markup))
    
    # Save last bot message context for button protection
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
        context.user_data['last_state'] = STATE_NAMES[CONFIRM_DATA]  # Save state for cancel return
    return CONFIRM_DATA

async def handle_data_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's choice on data confirmation"""
    query = update.callback_query
    
    # Check for stale interaction
    if await check_stale_interaction(query, context):
        return ConversationHandler.END
    
    await safe_telegram_call(query.answer())
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    # Mark previous message as selected (remove buttons)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    if query.data == 'confirm_data':
        # User confirmed data, proceed to fetch rates
        return await fetch_shipping_rates(update, context)
    
    if query.data == 'save_template':
        # Save current order data as template
        await safe_telegram_call(query.message.reply_text(
            """💾 Сохранить как шаблон,
            Введите название для шаблона (до 30 символов):,
            *Например:* "Склад NY", "Доставка маме", "Офис",
            _Шаблон сохранит оба адреса для быстрого использования в будущем._""",
            parse_mode='Markdown',
        ))
        return TEMPLATE_NAME
    
    if query.data == 'edit_data':
        # Show edit menu
        return await show_edit_menu(update, context)
    
    if query.data == 'edit_addresses_error':
        # Show edit menu after rate error
        return await show_edit_menu(update, context)
    
    if query.data == 'edit_from_address':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit from address
        context.user_data['editing_from_address'] = True
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📤 Редактирование адреса отправителя\n\nШаг 1/6: Имя отправителя\nНапример: John Smith",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = STATE_NAMES[FROM_NAME]
        return FROM_NAME
    
    if query.data == 'edit_to_address':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit to address
        context.user_data['editing_to_address'] = True
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📥 Редактирование адреса получателя\n\nШаг 1/6: Имя получателя\nНапример: Jane Doe",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = STATE_NAMES[TO_NAME]
        return TO_NAME
    
    if query.data == 'edit_parcel':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit parcel dimensions
        context.user_data['editing_parcel'] = True
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📦 Редактирование посылки\n\nВведите вес посылки в фунтах:\nНапример: 5 или 2.5",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = STATE_NAMES[PARCEL_WEIGHT]
        return PARCEL_WEIGHT
    
    if query.data == 'back_to_confirmation':
        # Return to confirmation screen
        return await show_data_confirmation(update, context)

async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu to select what to edit"""
    from utils.ui_utils import DataConfirmationUI
    
    query = update.callback_query
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    message = "✏️ Что вы хотите изменить?"
    
    # Build keyboard using UI utils
    reply_markup = DataConfirmationUI.build_edit_menu_keyboard()
    
    await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup))
    return EDIT_MENU

# Template Management Functions
async def save_template_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save template with user-provided name"""
    template_name = update.message.text.strip()[:30]  # Limit to 30 chars
    
    if not template_name:
        await safe_telegram_call(update.message.reply_text("❌ Название не может быть пустым. Попробуйте еще раз:"))
        return TEMPLATE_NAME
    
    telegram_id = update.effective_user.id
    
    # Check if template with this name already exists
    existing = await db.templates.find_one({
        "telegram_id": telegram_id,
        "name": template_name
    })
    
    if existing:
        # Ask to update or use new name
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить существующий", callback_data=f'template_update_{existing["id"]}')],
            [InlineKeyboardButton("📝 Ввести другое название", callback_data='template_new_name')],
            [InlineKeyboardButton("❌ Отмена", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        bot_msg = await safe_telegram_call(update.message.reply_text(
            f"""⚠️ Шаблон с названием "{template_name}" уже существует.

Что делать?""",
            reply_markup=reply_markup
        ))
        # Don't clear last_bot_message here - we need it for mark_message_as_selected
        context.user_data['pending_template_name'] = template_name
        return TEMPLATE_NAME
    
    # Create template using template service
    success, template_id, error = await template_service.create_template(
        telegram_id=telegram_id,
        template_name=template_name,
        order_data=context.user_data,
        insert_template_func=insert_template,
        count_user_templates_func=count_user_templates,
        max_templates=10
    )
    
    if not success:
        await safe_telegram_call(update.message.reply_text(
            f"""❌ *Ошибка сохранения шаблона*

{error}""",
            parse_mode='Markdown'
        ))
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("📦 Продолжить создание заказа", callback_data='continue_order')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"""✅ *Шаблон "{template_name}" сохранен!*

Теперь вы можете использовать его для быстрого создания заказов.

*Продолжить создание этого заказа?*"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    ))
    
    # Save last bot message context for button protection
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
    
    # Save template name for potential continuation
    context.user_data['saved_template_name'] = template_name
    

async def handle_template_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update existing template with current order data"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    template_id = query.data.replace('template_update_', '')
    telegram_id = query.from_user.id
    
    # Get user using Repository Pattern
    from repositories import get_user_repo
    user_repo = get_user_repo()
    user = await user_repo.find_by_telegram_id(telegram_id)
    if not user:
        await safe_telegram_call(query.message.reply_text("❌ Ошибка: пользователь не найден"))
        return ConversationHandler.END
    
    # Update template
    update_data = {
        "from_name": context.user_data.get('from_name', ''),
        "from_street1": context.user_data.get('from_street', ''),
        "from_street2": context.user_data.get('from_street2', ''),
        "from_city": context.user_data.get('from_city', ''),
        "from_state": context.user_data.get('from_state', ''),
        "from_zip": context.user_data.get('from_zip', ''),
        "from_phone": context.user_data.get('from_phone', ''),
        "to_name": context.user_data.get('to_name', ''),
        "to_street1": context.user_data.get('to_street', ''),
        "to_street2": context.user_data.get('to_street2', ''),
        "to_city": context.user_data.get('to_city', ''),
        "to_state": context.user_data.get('to_state', ''),
        "to_zip": context.user_data.get('to_zip', ''),
        "to_phone": context.user_data.get('to_phone', ''),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Note: update_template only supports template_id filter, manual query needed for telegram_id check
    result = await db.templates.update_one(
        {"id": template_id, "telegram_id": telegram_id},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        template_name = context.user_data.get('pending_template_name', 'шаблон')
        keyboard = [
            [InlineKeyboardButton("📦 Продолжить создание заказа", callback_data='continue_order')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"""✅ *Шаблон "{template_name}" обновлен!*

Данные шаблона обновлены текущими адресами.

*Продолжить создание этого заказа?*"""
        
        bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
        
        # Save last bot message context for button protection
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['saved_template_name'] = template_name
    else:
        await safe_telegram_call(query.message.reply_text("❌ Не удалось обновить шаблон"))
        return ConversationHandler.END


async def handle_template_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user to enter a new template name"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    await safe_telegram_call(query.message.reply_text(
        """📝 Введите новое название для шаблона:

Например: Доставка маме 2, Офис NY"""
    ))
    # Clear last_bot_message to prevent interfering with text input
    context.user_data.pop('last_bot_message_id', None)
    context.user_data.pop('last_bot_message_text', None)
    return TEMPLATE_NAME


async def continue_order_after_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Continue order creation after saving template - return to data confirmation"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Since template was saved from CONFIRM_DATA screen, we have all data including weight/dimensions
    # Return to data confirmation screen
    return await show_data_confirmation(update, context)

async def my_templates_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's templates list"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons from choice menu)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    
    # Get user templates
    templates = await find_user_templates(telegram_id, limit=10)
    logger.info(f"📋 my_templates_menu: user {telegram_id} has {len(templates)} templates")
    
    if not templates:
        from utils.ui_utils import TemplateManagementUI
        reply_markup = TemplateManagementUI.build_no_templates_keyboard()
        
        await safe_telegram_call(query.message.reply_text(
            TemplateManagementUI.no_templates_message(),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
        return ConversationHandler.END
    
    # Build template list message
    from utils.ui_utils import TemplateManagementUI
    message = TemplateManagementUI.templates_list_header()
    
    keyboard = []
    for i, template in enumerate(templates, 1):
        # Add compact template info to message
        message += TemplateManagementUI.format_template_item(i, template)
        
        # Create button with just number and name
        keyboard.append([InlineKeyboardButton(
            f"{i}. {template['name']}", 
            callback_data=f'template_view_{template["id"]}'
        )])
    
    # Add main menu button at the bottom
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    bot_msg = await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown'))
    # Save last message context for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message
    # Don't return state - working outside ConversationHandler

async def view_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific template details"""
    query = update.callback_query
    template_id = query.data.replace('template_view_', '')
    
    # Execute in parallel: answer query, mark selected, fetch template
    await safe_telegram_call(query.answer())
    asyncio.create_task(mark_message_as_selected(update, context))
    template = await find_template_by_id(template_id)
    
    if not template:
        await safe_telegram_call(query.message.reply_text("❌ Шаблон не найден"))
        return ConversationHandler.END
    
    # Format template details
    message = f"""📋 *Шаблон: "{template['name']}"*

📤 *Отправитель:*
{template.get('from_name', '')}
{template.get('from_street1', '')}
{template.get('from_street2', '') + ', ' if template.get('from_street2') else ''}{template.get('from_city', '')}, {template.get('from_state', '')} {template.get('from_zip', '')}
{('📞 ' + template.get('from_phone', '')) if template.get('from_phone') else ''}

📥 *Получатель:*
{template.get('to_name', '')}
{template.get('to_street1', '')}
{template.get('to_street2', '') + ', ' if template.get('to_street2') else ''}{template.get('to_city', '')}, {template.get('to_state', '')} {template.get('to_zip', '')}
{('📞 ' + template.get('to_phone', '')) if template.get('to_phone') else ''}"""
    
    keyboard = [
        [InlineKeyboardButton("📦 Использовать шаблон", callback_data=f'template_use_{template_id}')],
        [InlineKeyboardButton("✏️ Переименовать", callback_data=f'template_rename_{template_id}')],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f'template_delete_{template_id}')],
        [InlineKeyboardButton("🔙 К списку шаблонов", callback_data='my_templates')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    bot_msg = await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown'))
    # Save last message context for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message
    # Don't return state - working outside ConversationHandler

async def use_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Load template data into context and start order via ConversationHandler"""
    query = update.callback_query
    template_id = query.data.replace('template_use_', '')
    
    # Execute in parallel: answer query and fetch template
    await safe_telegram_call(query.answer())
    template = await find_template_by_id(template_id)
    
    if not template:
        await safe_telegram_call(query.message.reply_text("❌ Шаблон не найден"))
        return
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Load template data into context (use correct keys for rate fetching)
    context.user_data['from_name'] = template.get('from_name', '')
    context.user_data['from_street'] = template.get('from_street1', '')  # Use 'from_street' not 'from_address'
    context.user_data['from_street2'] = template.get('from_street2', '')
    context.user_data['from_city'] = template.get('from_city', '')
    context.user_data['from_state'] = template.get('from_state', '')
    context.user_data['from_zip'] = template.get('from_zip', '')
    context.user_data['from_phone'] = template.get('from_phone', '')
    context.user_data['to_name'] = template.get('to_name', '')
    context.user_data['to_street'] = template.get('to_street1', '')  # Use 'to_street' not 'to_address'
    context.user_data['to_street2'] = template.get('to_street2', '')
    context.user_data['to_city'] = template.get('to_city', '')
    context.user_data['to_state'] = template.get('to_state', '')
    context.user_data['to_zip'] = template.get('to_zip', '')
    context.user_data['to_phone'] = template.get('to_phone', '')
    context.user_data['using_template'] = True
    context.user_data['template_name'] = template['name']
    
    # Instead of staying outside ConversationHandler, show confirmation with button to start
    keyboard = [
        [InlineKeyboardButton("📦 Продолжить создание заказа", callback_data='start_order_with_template')],
        [InlineKeyboardButton("🔙 К списку шаблонов", callback_data='my_templates')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"""✅ *Шаблон "{template['name']}" загружен!*

📤 От: {template.get('from_name')} ({template.get('from_city')}, {template.get('from_state')})
📥 Кому: {template.get('to_name')} ({template.get('to_city')}, {template.get('to_state')})

Нажмите кнопку для продолжения создания заказа."""
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    
    # Stay in conversation - go to TEMPLATE_LOADED state
    return TEMPLATE_LOADED

async def start_order_with_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start order creation with pre-loaded template data"""
    query = update.callback_query
    
    # Clear topup flag to prevent conflict with parcel weight input
    context.user_data['awaiting_topup_amount'] = False
    
    # Template data already loaded in context.user_data
    # Ask for parcel weight (first thing not in template)
    from utils.ui_utils import get_cancel_keyboard
    reply_markup = get_cancel_keyboard()
    
    template_name = context.user_data.get('template_name', 'шаблон')
    
    message_text = f"""📦 Создание заказа по шаблону "{template_name}"

Теперь введите данные посылки:

*Вес посылки в фунтах (lb)*
Например: 5.5"""
    
    # Execute answer and mark selected, then send new message
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Send new message immediately without waiting for mark_message_as_selected
    bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    
    context.user_data['last_state'] = STATE_NAMES[PARCEL_WEIGHT]
    return PARCEL_WEIGHT

async def confirm_delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and delete template"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    template_id = query.data.replace('template_confirm_delete_', '')
    telegram_id = query.from_user.id
    
    # Use template service
    success, template_name, error = await template_service.delete_template(
        template_id=template_id,
        telegram_id=telegram_id,
        find_template_func=find_template_by_id,
        delete_template_func=delete_template
    )
    
    if success:
        from utils.ui_utils import TemplateManagementUI
        keyboard = [[InlineKeyboardButton("🔙 К списку шаблонов", callback_data='my_templates')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            TemplateManagementUI.template_deleted_success(template_name),
            reply_markup=reply_markup
        ))
    else:
        await safe_telegram_call(query.message.reply_text(f"❌ {error}"))
    # Don't return state - deleted successfully

async def rename_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start template rename process"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    template_id = query.data.replace('template_rename_', '')
    context.user_data['renaming_template_id'] = template_id
    
    await safe_telegram_call(query.message.reply_text(
            """✏️ Введите новое название для шаблона (до 30 символов):""",
        ))
    # Clear last_bot_message to not interfere with text input
    context.user_data.pop('last_bot_message_id', None)
    context.user_data.pop('last_bot_message_text', None)
    return TEMPLATE_RENAME

async def rename_template_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save new template name"""
    new_name = update.message.text.strip()[:30]
    
    if not new_name:
        await safe_telegram_call(update.message.reply_text("❌ Название не может быть пустым. Попробуйте еще раз:"))
        return TEMPLATE_RENAME
    
    template_id = context.user_data.get('renaming_template_id')
    
    # Use template service
    success, error = await template_service.update_template_name(
        template_id=template_id,
        new_name=new_name,
        update_template_func=update_template
    )
    
    if success:
        keyboard = [[InlineKeyboardButton("👁️ Просмотреть", callback_data=f'template_view_{template_id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(update.message.reply_text(
                f"""✅ Шаблон переименован в "{new_name}" """,
                reply_markup=reply_markup
            ))
    else:
        await safe_telegram_call(update.message.reply_text(f"❌ {error}"))
    
    return ConversationHandler.END

async def order_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new order (without template)"""
    from utils.ui_utils import get_cancel_keyboard, OrderFlowMessages
    
    logger.info(f"order_new called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Clear topup flag to prevent conflict with order input
    context.user_data['awaiting_topup_amount'] = False
    
    # Mark previous message as selected (remove buttons from choice screen)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    reply_markup = get_cancel_keyboard()
    message_text = OrderFlowMessages.new_order_start()
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = STATE_NAMES[FROM_NAME]
    logger.info("order_new returning FROM_NAME state")
    return FROM_NAME

async def order_from_template_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show template list for order creation"""
    from utils.ui_utils import get_template_selection_keyboard, OrderFlowMessages
    
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    templates = await find_user_templates(telegram_id, limit=10)
    
    if not templates:
        await safe_telegram_call(query.message.reply_text(OrderFlowMessages.no_templates_error()))
        return ConversationHandler.END
    
    message = OrderFlowMessages.select_template()
    
    for i, template in enumerate(templates, 1):
        message += OrderFlowMessages.template_item(i, template)
    
    reply_markup = get_template_selection_keyboard(templates)
    
    bot_msg = await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown'))
    
    # Save last bot message context for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message
    
    return TEMPLATE_LIST

async def skip_address_validation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip address validation and continue with rate fetching"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Set flag to skip validation
    context.user_data['skip_address_validation'] = True
    
    await safe_telegram_call(query.message.reply_text("⚠️ Пропускаю валидацию адреса...\n⏳ Получаю доступные курьерские службы и тарифы..."))
    
    # Call fetch_shipping_rates which will now skip validation
    return await fetch_shipping_rates(update, context)

async def display_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE, rates: list) -> int:
    """
    Display shipping rates to user (reusable for both cached and fresh rates)
    
    Args:
        update: Telegram update
        context: Telegram context
        rates: List of rate dictionaries
    
    Returns:
        int: SELECT_CARRIER state
    """
    from utils.ui_utils import ShippingRatesUI
    
    query = update.callback_query
    
    # Get user balance using Repository Pattern
    telegram_id = query.from_user.id
    from repositories import get_user_repo
    user_repo = get_user_repo()
    user_balance = await user_repo.get_balance(telegram_id)
    
    # Format message and keyboard using UI utils
    message = ShippingRatesUI.format_rates_message(rates, user_balance)
    reply_markup = ShippingRatesUI.build_rates_keyboard(rates)
    
    # Save state
    context.user_data['last_state'] = STATE_NAMES[SELECT_CARRIER]
    
    # Send message
    bot_msg = await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML'))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
    
    return SELECT_CARRIER


async def fetch_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch shipping rates from ShipStation with caching"""
    query = update.callback_query
    
    # Import cache
    from services.shipstation_cache import shipstation_cache
    
    data = context.user_data
    
    # Check cache first (before showing progress message)
    cached_rates = shipstation_cache.get(
        from_zip=data['from_zip'],
        to_zip=data['to_zip'],
        weight=data['weight'],
        length=data.get('length', 10),
        width=data.get('width', 10),
        height=data.get('height', 10)
    )
    
    if cached_rates:
        # Cache HIT - используем закэшированные тарифы
        logger.info(f"✅ Using cached rates for {data['from_zip']} → {data['to_zip']}")
        
        # Immediately show rates (no API call needed)
        from utils.ui_utils import ShippingRatesUI
        await safe_telegram_call(query.answer(ShippingRatesUI.cache_hit_message()))
        
        # Prepare rate data
        context.user_data['rates'] = cached_rates
        
        # Save to session
        user_id = update.effective_user.id
        await save_to_session(user_id, "CARRIER_SELECTION", {
            'rates': cached_rates,
            'cached': True,
            'cache_timestamp': datetime.now(timezone.utc).isoformat()
        }, context)
        
        # Display rates (reuse display logic)
        return await display_shipping_rates(update, context, cached_rates)
    
    # Cache MISS - need to fetch from API
    # Send initial progress message
    from utils.ui_utils import ShippingRatesUI
    progress_msg = await safe_telegram_call(query.message.reply_text(ShippingRatesUI.progress_message(0)))
    
    try:
        import requests
        import asyncio
        
        # Validate order data using service
        from services.shipping_service import validate_order_data_for_rates
        is_valid, missing_fields = await validate_order_data_for_rates(data)
        
        if not is_valid:
            logger.error(f"Missing or invalid required fields: {missing_fields}")
            logger.error(f"Current user_data: {data}")
            
            # Log error to session for debugging
            user_id = update.effective_user.id
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'Missing required fields: {", ".join(missing_fields)}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            from utils.ui_utils import get_edit_data_keyboard
            reply_markup = get_edit_data_keyboard()
            await safe_telegram_call(query.message.reply_text(
                f"❌ Отсутствуют обязательные данные: {', '.join(missing_fields)}\n\nПожалуйста, заполните все поля.",
                reply_markup=reply_markup
            ))
            return CONFIRM_DATA
        
        # Get carrier IDs
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        carrier_ids = await get_shipstation_carrier_ids()
        if not carrier_ids:
            from utils.ui_utils import get_edit_addresses_keyboard
            reply_markup = get_edit_addresses_keyboard()
            await safe_telegram_call(query.message.reply_text(
            "❌ Ошибка: не удалось загрузить список курьеров.\n\nПожалуйста, попробуйте позже.",
            reply_markup=reply_markup,
        ))
            return CONFIRM_DATA
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Build rate request using service
        from services.shipping_service import build_shipstation_rates_request
        rate_request = build_shipstation_rates_request(data, carrier_ids)
        
        # Log the request for debugging
        logger.info(f"ShipStation rate request: {rate_request}")
        
        # Get rates from ShipStation with progress updates
        async def update_progress():
            """Update progress message every 5 seconds"""
            start_time = datetime.now(timezone.utc)
            while True:
                await asyncio.sleep(5)
                elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds())
                try:
                    await safe_telegram_call(progress_msg.edit_text(
                        ShippingRatesUI.progress_message(elapsed)
                    ))
                except Exception:
                    break  # Stop if message was deleted or can't be edited
        
        # Start progress update task
        progress_task = asyncio.create_task(update_progress())
        
        # Fetch rates from ShipStation using service
        from services.shipping_service import fetch_rates_from_shipstation
        
        api_start_time = time.perf_counter()
        success, all_rates, error_msg = await fetch_rates_from_shipstation(
            rate_request=rate_request,
            headers=headers,
            api_url='https://api.shipstation.com/v2/rates',
            timeout=30
        )
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        logger.info(f"⚡ ShipStation /rates API took {api_duration_ms:.2f}ms")
        
        if not success and "timeout" in error_msg.lower():
            # Handle timeout error
            logger.error(f"ShipStation rate request failed: {error_msg}")
            
            # Log error to session
            user_id = update.effective_user.id
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'ShipStation API error: {error_msg}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Stop progress task
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            # Delete progress message
            try:
                await safe_telegram_call(progress_msg.delete())
            except Exception:
                pass
            
            from utils.ui_utils import get_retry_edit_cancel_keyboard
            reply_markup = get_retry_edit_cancel_keyboard()
            
            await safe_telegram_call(query.message.reply_text(
                f"❌ {error_msg}\n\nПопробуйте еще раз или проверьте правильность адресов.",
                reply_markup=reply_markup
            ))
            return CONFIRM_DATA
        
        if not success:
            # Handle other API errors
            logger.error(f"ShipStation rate request failed: {error_msg}")
            
            # Log error to session
            user_id = update.effective_user.id
            await session_manager.update_session_atomic(user_id, data={
                'last_error': f'ShipStation API error: {error_msg}',
                'error_step': 'FETCH_RATES',
                'error_timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Delete progress message
            try:
                await safe_telegram_call(progress_msg.delete())
            except Exception:
                pass
            
            from utils.ui_utils import get_edit_addresses_keyboard, ShippingRatesUI
            reply_markup = get_edit_addresses_keyboard()
            
            await safe_telegram_call(query.message.reply_text(
                ShippingRatesUI.api_error_message(error_msg),
                reply_markup=reply_markup,
            ))
            
            # Stop progress task
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            return CONFIRM_DATA
        
        # Stop progress updates on success
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass
        
        # Filter and format rates using service
        from services.shipping_service import filter_and_sort_rates
        
        # First apply basic exclusion
        excluded_carriers = ['globalpost']
        filtered_rates = [
            rate for rate in all_rates
            if rate.get('carrier_code', '').lower() not in excluded_carriers
        ]
        all_rates = filtered_rates
        
        # Apply service filter using service
        from services.shipping_service import apply_service_filter
        all_rates = apply_service_filter(all_rates)
        
        if not all_rates or len(all_rates) == 0:
            # Delete progress message
            try:
                await safe_telegram_call(progress_msg.delete())
            except Exception:
                pass
            
            from utils.ui_utils import get_edit_addresses_keyboard, ShippingRatesUI
            reply_markup = get_edit_addresses_keyboard()
            
            await safe_telegram_call(query.message.reply_text(
            ShippingRatesUI.no_rates_found(),
            reply_markup=reply_markup,
        ))
            return CONFIRM_DATA  # Stay to handle callback
        
        # Log carriers
        carriers = set([r.get('carrier_friendly_name', 'Unknown') for r in all_rates])
        logger.info(f"Got {len(all_rates)} rates from carriers: {carriers}")
        
        # Balance and deduplicate rates using service
        from services.shipping_service import balance_and_deduplicate_rates
        context.user_data['rates'] = balance_and_deduplicate_rates(all_rates, max_per_carrier=5)[:15]
        
        # Save to cache and session using service
        from services.shipping_service import save_rates_to_cache_and_session
        user_id = update.effective_user.id
        await save_rates_to_cache_and_session(
            rates=context.user_data['rates'],
            order_data=data,
            user_id=user_id,
            context=context,
            shipstation_cache=shipstation_cache,
            session_manager=session_manager
        )
        
        # Delete progress message
        try:
            await safe_telegram_call(progress_msg.delete())
        except Exception:
            pass
        
        # Display rates using reusable function
        return await display_shipping_rates(update, context, context.user_data['rates'])
        
    except Exception as e:
        logger.error(f"Error getting rates: {e}", exc_info=True)
        
        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Notify admin about rate fetch error
        telegram_id = query.from_user.id
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        if user:
            await notify_admin_error(
                user_info=user,
                error_type="Rate Fetch Failed",
                error_details=f"Exception: {str(e)}\n\nAddresses:\nFrom: {data.get('from_city')}, {data.get('from_state')}\nTo: {data.get('to_city')}, {data.get('to_state')}"
            )
        
        await safe_telegram_call(query.message.reply_text(
            f"❌ Ошибка при получении тарифов:\n{str(e)}\n\nПроверьте корректность адресов и попробуйте снова.",
            reply_markup=reply_markup
        ))
        return CONFIRM_DATA  # Stay to handle callback

async def select_carrier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Check for stale interaction
    if await check_stale_interaction(query, context):
        return ConversationHandler.END
    
    await safe_telegram_call(query.answer())
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    if query.data == 'check_data':
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        # Return to data confirmation screen
        return await check_data_from_cancel(update, context)
    
    if query.data == 'refresh_rates':
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        # Refresh shipping rates
        return await fetch_shipping_rates(update, context)
    
    # Mark previous message as selected (remove buttons)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Get selected carrier index
    carrier_idx = int(query.data.split('_')[-1])
    selected_rate = context.user_data['rates'][carrier_idx]
    context.user_data['selected_rate'] = selected_rate
    context.user_data['last_state'] = STATE_NAMES[PAYMENT_METHOD]  # Save state for cancel return
    
    # Get user balance using Repository Pattern
    telegram_id = query.from_user.id
    from repositories import get_user_repo
    user_repo = get_user_repo()
    user = await user_repo.find_by_telegram_id(telegram_id)
    balance = user.get('balance', 0.0) if user else 0.0
    user_discount = user.get('discount', 0.0) if user else 0.0  # Get user discount percentage
    
    # Show payment options
    amount = selected_rate['amount']
    
    # Apply discount if user has one
    discount_amount = 0
    if user_discount > 0:
        discount_amount = amount * (user_discount / 100)
        amount = amount - discount_amount  # Apply discount to final amount
    
    # Save discount info in context for later use
    context.user_data['user_discount'] = user_discount
    context.user_data['discount_amount'] = discount_amount
    context.user_data['final_amount'] = amount  # Save final amount after discount
    
    data = context.user_data
    
    # Build confirmation text with full details
    confirmation_text = f"""✅ Выбрано: {selected_rate['carrier']} - {selected_rate['service']}

📦 Детали заказа:

📤 *Отправитель:*
{data['from_name']}
{data['from_street']}{', ' + data.get('from_street2', '') if data.get('from_street2') else ''}
{data['from_city']}, {data['from_state']} {data['from_zip']}
📞 {data.get('from_phone', 'Не указан')}

📥 *Получатель:*
{data['to_name']}
{data['to_street']}{', ' + data.get('to_street2', '') if data.get('to_street2') else ''}
{data['to_city']}, {data['to_state']} {data['to_zip']}
📞 {data.get('to_phone', 'Не указан')}

📏 *Посылка:*
⚖️ Вес: {data['weight']} lb
📦 Размеры: {data.get('length', 0)} x {data.get('width', 0)} x {data.get('height', 0)} inches

💰 Стоимость: ${selected_rate['amount']:.2f}"""
    
    if user_discount > 0:
        confirmation_text += f"""
🎉 Скидка ({user_discount}%): -${discount_amount:.2f}
💵 Итого к оплате: ${amount:.2f}"""
    else:
        confirmation_text += f"""
💵 К оплате: ${amount:.2f}"""
    
    confirmation_text += f"""

💳 Ваш баланс: ${balance:.2f}
"""
    
    from utils.ui_utils import get_payment_keyboard
    
    if balance >= amount:
        # Достаточно денег
        confirmation_text += "\n✅ У вас достаточно средств на балансе!"
    else:
        # Недостаточно денег
        shortage = amount - balance
        confirmation_text += f"\n⚠️ Недостаточно средств. Необходимо: ${shortage:.2f}"
    
    reply_markup = get_payment_keyboard(balance, amount)
    bot_msg = await safe_telegram_call(query.message.reply_text(confirmation_text, reply_markup=reply_markup))
    # Save last bot message context for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = confirmation_text
    
    return PAYMENT_METHOD

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Check for stale interaction
    if await check_stale_interaction(query, context):
        return ConversationHandler.END
    
    await safe_telegram_call(query.answer())
    
    if query.data == 'cancel_order':
        return await cancel_order(update, context)
    
    if query.data == 'confirm_cancel':
        return await confirm_cancel_order(update, context)
    
    if query.data == 'return_to_order':
        return await return_to_order(update, context)
    
    # Handle back to rates
    if query.data == 'back_to_rates':
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        # Return to rate selection - call fetch_shipping_rates again
        return await fetch_shipping_rates(update, context)
    
    # Mark previous message as selected (remove buttons)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    from repositories import get_user_repo
    user_repo = get_user_repo()
    user = await user_repo.find_by_telegram_id(telegram_id)
    data = context.user_data
    selected_rate = data['selected_rate']
    amount = context.user_data.get('final_amount', selected_rate['amount'])  # Use discounted amount
    
    # Get user discount (should be already calculated and stored in context)
    user_discount = context.user_data.get('user_discount', 0)
    discount_amount = context.user_data.get('discount_amount', 0)
    
    try:
        if query.data == 'pay_from_balance':
            # Pay from balance
            from utils.ui_utils import PaymentFlowUI
            if user.get('balance', 0) < amount:
                await safe_telegram_call(query.message.reply_text(PaymentFlowUI.insufficient_balance_error()))
                return ConversationHandler.END
            
            # Create order
            order = await create_order_in_db(user, data, selected_rate, amount, user_discount, discount_amount)
            
            # Try to create shipping label first
            label_created = await create_and_send_label(order['id'], telegram_id, query.message)
            
            if label_created:
                # Only deduct balance if label was created successfully using payment service
                success, new_balance, error = await payment_service.process_balance_payment(
                    telegram_id=telegram_id,
                    amount=amount,
                    order_id=order['id'],
                    db=db,
                    find_user_func=find_user_by_telegram_id,
                    update_order_func=update_order
                )
                
                if not success:
                    logger.error(f"Failed to process payment: {error}")
                    # This shouldn't happen as we checked balance earlier
                    await safe_telegram_call(query.message.reply_text(f"❌ Ошибка обработки платежа: {error}"))
                    return ConversationHandler.END
                
                from utils.ui_utils import PaymentFlowUI
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(query.message.reply_text(
                    PaymentFlowUI.payment_success_balance(amount, new_balance, order.get('order_id')),
                    reply_markup=reply_markup
                ))
                
                # Mark order as completed to prevent stale button interactions
                context.user_data.clear()
                context.user_data['order_completed'] = True
            else:
                # Label creation failed - don't charge user
                await db.orders.update_one(
                    {"id": order['id']},
                    {"$set": {"payment_status": "failed", "shipping_status": "failed"}}
                )
                
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(query.message.reply_text(
            """❌ Не удалось создать shipping label.
            Оплата не списана. Ваш баланс не изменился.
            Пожалуйста, свяжитесь с администратором.""",
            reply_markup=reply_markup
        ))
                
                # Mark order as completed to prevent stale button interactions
                context.user_data.clear()
                context.user_data['order_completed'] = True
            
        elif query.data == 'pay_with_crypto':
            # Create order
            order = await create_order_in_db(user, data, selected_rate, amount, user_discount, discount_amount)
            
            # Create Oxapay invoice
            invoice_result = await create_oxapay_invoice(
                amount=amount,
                order_id=order['id'],
                description=f"Shipping Label - Order {order['id'][:8]}"
            )
            
            if invoice_result.get('success'):
                track_id = invoice_result['trackId']
                pay_link = invoice_result['payLink']
                
                payment = Payment(
                    order_id=order['id'],
                    amount=amount,
                    invoice_id=track_id,
                    pay_url=pay_link
                )
                payment_dict = payment.model_dump()
                payment_dict['created_at'] = payment_dict['created_at'].isoformat()
                await insert_payment(payment_dict)
                
                keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)],
                           [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Get order_id from session for display
                from utils.order_utils import format_order_id_for_display
                session = await session_manager.get_session(telegram_id)
                order_id_display = ""
                if session and session.get('order_id'):
                    display_id = format_order_id_for_display(session['order_id'])
                    order_id_display = f"\n📦 Номер заказа: #{display_id}\n"
                
                await safe_telegram_call(query.message.reply_text(
                    f"""✅ Заказ создан!{order_id_display}

💰 Сумма к оплате: ${amount}
🪙 Криптовалюта: BTC, ETH, USDT, USDC и др.

Нажмите кнопку "Оплатить" для перехода на страницу оплаты.

После успешной оплаты мы автоматически создадим shipping label.""",
                    reply_markup=reply_markup
                ))
            else:
                error_msg = invoice_result.get('error', 'Unknown error')
                await safe_telegram_call(query.message.reply_text(f"❌ Ошибка создания инвойса: {error_msg}"))
        elif query.data == 'top_up_balance':
            # Save order data to database before top-up so user can return to payment after
            pending_order = {
                'telegram_id': telegram_id,
                'selected_rate': data.get('selected_rate'),
                'final_amount': context.user_data.get('final_amount'),
                'user_discount': context.user_data.get('user_discount', 0),
                'discount_amount': context.user_data.get('discount_amount', 0),
                'from_name': data.get('from_name'),
                'from_street': data.get('from_street'),
                'from_street2': data.get('from_street2'),
                'from_city': data.get('from_city'),
                'from_state': data.get('from_state'),
                'from_zip': data.get('from_zip'),
                'from_phone': data.get('from_phone'),
                'to_name': data.get('to_name'),
                'to_street': data.get('to_street'),
                'to_street2': data.get('to_street2'),
                'to_city': data.get('to_city'),
                'to_state': data.get('to_state'),
                'to_zip': data.get('to_zip'),
                'to_phone': data.get('to_phone'),
                'parcel_weight': data.get('parcel_weight'),
                'parcel_length': data.get('parcel_length'),
                'parcel_width': data.get('parcel_width'),
                'parcel_height': data.get('parcel_height'),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Delete any existing pending order for this user
            await db.pending_orders.delete_many({"telegram_id": telegram_id})
            # Save new pending order
            await insert_pending_order(pending_order)
            
            context.user_data['last_state'] = STATE_NAMES[TOPUP_AMOUNT]  # Save state for cancel return
            
        from utils.ui_utils import get_cancel_keyboard
        reply_markup = get_cancel_keyboard()
        
        message_text = """💵 Пополнение баланса

Введите сумму пополнения в долларах США (USD):

Например: 50

Минимальная сумма: $5
Максимальная сумма: $1000"""
        
        bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
        
        # Save message context for button protection
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        
        return TOPUP_AMOUNT
    
    except Exception as e:
        logger.error(f"Payment error: {e}")
        await safe_telegram_call(query.message.reply_text(f"❌ Ошибка при оплате: {str(e)}"))
        return ConversationHandler.END

async def return_to_payment_after_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return user to payment screen after topping up balance"""
    logger.info(f"return_to_payment_after_topup called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    telegram_id = query.from_user.id
    
    # Get pending order data from database to load message context
    pending_order = await find_pending_order(telegram_id)
    logger.info(f"Pending order data found: {pending_order is not None}")
    
    # Load message context for button protection
    if pending_order:
        context.user_data['last_bot_message_id'] = pending_order.get('topup_success_message_id')
        context.user_data['last_bot_message_text'] = pending_order.get('topup_success_message_text')
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    if not pending_order or not pending_order.get('selected_rate'):
        await safe_telegram_call(query.message.reply_text(
            "❌ Не найдены данные незавершенного заказа.\n\nПожалуйста, создайте новый заказ."
        ))
        return ConversationHandler.END
    
    # Restore order data to context
    context.user_data.update(pending_order)
    
    # Get user balance using Repository Pattern
    from repositories import get_user_repo
    user_repo = get_user_repo()
    user_balance = await user_repo.get_balance(telegram_id)
    
    selected_rate = pending_order['selected_rate']
    logger.info(f"Selected rate keys: {selected_rate.keys()}")
    amount = pending_order.get('final_amount', selected_rate.get('amount', selected_rate.get('totalAmount', 0)))
    
    # Handle different rate structures - use correct keys
    carrier_name = selected_rate.get('carrier') or selected_rate.get('carrier_name') or selected_rate.get('carrierName', 'Unknown Carrier')
    service_type = selected_rate.get('service') or selected_rate.get('service_type') or selected_rate.get('serviceType', 'Standard Service')
    
    user_discount = pending_order.get('user_discount', 0)
    discount_text = f"\n🎉 *Ваша скидка:* {user_discount}%" if user_discount > 0 else ""
    
    # Show payment options - only balance payment if sufficient
    keyboard = []
    
    if user_balance >= amount:
        # User has enough balance, only show balance payment option
        keyboard.append([InlineKeyboardButton(f"💰 Оплатить с баланса (${user_balance:.2f})", callback_data='pay_from_balance')])
        
        message_text = f"""💳 *Оплата заказа*

📦 *Выбранный тариф:* {carrier_name} - {service_type}
💰 *Стоимость:* ${amount:.2f}{discount_text}
💵 *Ваш баланс:* ${user_balance:.2f}"""
    else:
        # Not enough balance
        keyboard.append([InlineKeyboardButton("🪙 Оплатить криптовалютой", callback_data='pay_with_crypto')])
        keyboard.append([InlineKeyboardButton("💵 Пополнить баланс", callback_data='top_up_balance')])
        
        message_text = f"""💳 *Выберите способ оплаты*

📦 *Выбранный тариф:* {carrier_name} - {service_type}
💰 *Стоимость:* ${amount:.2f}{discount_text}
💵 *Ваш баланс:* ${user_balance:.2f}

Выберите способ оплаты:"""
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к тарифам", callback_data='back_to_rates')])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
    
    # Delete pending order after restoring
    await delete_pending_order(telegram_id)
    
    return PAYMENT_METHOD

async def handle_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom top-up amount input and create Oxapay invoice directly"""
    # Mark previous message as selected (remove "Отмена" button)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    try:
        amount_text = update.message.text.strip()
        
        # Validate amount
        try:
            topup_amount = float(amount_text)
        except ValueError:
            await safe_telegram_call(update.message.reply_text(
                "❌ Неверный формат суммы. Введите число, например: 50"
            ))
            return TOPUP_AMOUNT
        
        # Check limits
        if topup_amount < 10:
            await safe_telegram_call(update.message.reply_text(
                "❌ Минимальная сумма пополнения: $10"
            ))
            return TOPUP_AMOUNT
        
        if topup_amount > 10000:
            await safe_telegram_call(update.message.reply_text(
                "❌ Максимальная сумма пополнения: $10,000"
            ))
            return TOPUP_AMOUNT
        
        telegram_id = update.effective_user.id
        
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            await safe_telegram_call(update.message.reply_text("❌ Пользователь не найден"))
            return ConversationHandler.END
        
        # Create Oxapay invoice directly (order_id must be <= 50 chars)
        # Generate short order_id: "top_" (4) + timestamp (10) + "_" (1) + random (8) = 23 chars
        order_id = f"top_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        invoice_result = await create_oxapay_invoice(
            amount=topup_amount,
            order_id=order_id,
            description=f"Balance Top-up ${topup_amount}"
        )
        
        if invoice_result.get('success'):
            track_id = invoice_result['trackId']
            pay_link = invoice_result['payLink']
            
            # Save top-up payment
            payment = Payment(
                order_id=f"topup_{user['id']}",
                amount=topup_amount,
                invoice_id=track_id,
                pay_url=pay_link,
                status="pending"
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            payment_dict['telegram_id'] = telegram_id
            payment_dict['type'] = 'topup'
            await insert_payment(payment_dict)
            
            keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"""✅ *Счёт на пополнение создан!*

💵 *Сумма: ${topup_amount}*
🪙 *Криптовалюта: Любая из доступных*

*Нажмите кнопку "Оплатить" для перехода на страницу оплаты.*
*На платежной странице вы сможете выбрать удобную криптовалюту.*

⚠️❗️❗️ *ВАЖНО: Оплатите точно ${topup_amount}!* ❗️❗️⚠️
_Если вы оплатите другую сумму, деньги НЕ поступят на баланс!_

*После успешной оплаты баланс будет автоматически пополнен.*"""
            
            bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
            
            # Save message_id in payment for later removal of button
            await db.payments.update_one(
                {"invoice_id": track_id},
                {"$set": {
                    "payment_message_id": bot_msg.message_id,
                    "payment_message_text": message_text
                }}
            )
            
            # Also save in context for immediate use
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
            
            return ConversationHandler.END
        else:
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(update.message.reply_text(f"❌ *Ошибка создания инвойса:* {error_msg}", parse_mode='Markdown'))
            return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Top-up amount handling error: {e}")
        await safe_telegram_call(update.message.reply_text(f"❌ Ошибка: {str(e)}"))
        return ConversationHandler.END

async def handle_topup_crypto_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cryptocurrency selection for top-up"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
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
            await safe_telegram_call(query.message.reply_text("❌ Ошибка: сумма не найдена. Начните заново."))
            return ConversationHandler.END
        
        telegram_id = query.from_user.id
        
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        
        if not user:
            await safe_telegram_call(query.message.reply_text("❌ Пользователь не найден"))
            return ConversationHandler.END
        
        # Create Oxapay invoice for top-up (order_id must be <= 50 chars)
        # Generate short order_id: "top_" (4) + timestamp (10) + "_" (1) + random (8) = 23 chars
        order_id = f"top_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        invoice_result = await create_oxapay_invoice(
            amount=topup_amount,
            order_id=order_id,
            description=f"Balance Top-up ${topup_amount}"
        )
        
        if invoice_result.get('success'):
            track_id = invoice_result['trackId']
            pay_link = invoice_result['payLink']
            
            # Save top-up payment
            payment = Payment(
                order_id=f"topup_{user['id']}",
                amount=topup_amount,
                invoice_id=track_id,
                pay_url=pay_link,
                currency=crypto_asset,
                status="pending"
            )
            payment_dict = payment.model_dump()
            payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            payment_dict['telegram_id'] = telegram_id
            payment_dict['type'] = 'topup'
            await insert_payment(payment_dict)
            
            keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await safe_telegram_call(query.message.reply_text(
                f"""✅ *Счёт на пополнение создан!*

💵 *Сумма: ${topup_amount}*
🪙 *Криптовалюта: Любая из доступных*

*Нажмите кнопку "Оплатить" для перехода на страницу оплаты.*
*На платежной странице вы сможете выбрать удобную криптовалюту.*

⚠️❗️❗️ *ВАЖНО: Оплатите точно ${topup_amount}!* ❗️❗️⚠️
_Если вы оплатите другую сумму, деньги НЕ поступят на баланс!_

*После успешной оплаты баланс будет автоматически пополнен.*""",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            ))
        else:
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(query.message.reply_text(f"❌ Ошибка создания инвойса: {error_msg}"))
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Crypto selection handling error: {e}")
        await safe_telegram_call(query.message.reply_text(f"❌ Ошибка: {str(e)}"))
        return ConversationHandler.END

async def create_order_in_db(user, data, selected_rate, amount, discount_percent=0, discount_amount=0):
    # Get order_id from session or generate new one
    from utils.order_utils import generate_order_id
    order_id = data.get('order_id') or generate_order_id(telegram_id=user['telegram_id'])
    
    order = Order(
        user_id=user['id'],
        order_id=order_id,  # Add unique order_id
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
            length=data.get('length', 10),
            width=data.get('width', 10),
            height=data.get('height', 10),
            weight=data['weight'],
            distance_unit="in",
            mass_unit="lb"
        ),
        amount=amount  # This is the amount with markup (and discount applied) that user pays
    )
    
    order_dict = order.model_dump()
    order_dict['created_at'] = order_dict['created_at'].isoformat()
    order_dict['selected_carrier'] = selected_rate['carrier']
    order_dict['selected_service'] = selected_rate['service']
    order_dict['selected_service_code'] = selected_rate.get('service_code', '')  # Add service_code
    order_dict['rate_id'] = selected_rate['rate_id']
    order_dict['original_amount'] = selected_rate['original_amount']  # Store original GoShippo price
    order_dict['markup'] = selected_rate['amount'] - selected_rate['original_amount']  # Store markup amount before discount
    order_dict['discount_percent'] = discount_percent  # Store discount percentage
    order_dict['discount_amount'] = discount_amount  # Store discount amount
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
        
        # Prepare order data in expected format
        from_phone = order['address_from'].get('phone', generate_random_phone())
        from_phone = from_phone.strip() if from_phone else generate_random_phone()
        to_phone = order['address_to'].get('phone', generate_random_phone())
        to_phone = to_phone.strip() if to_phone else generate_random_phone()
        
        logger.info(f"Sending phones to ShipStation - from: '{from_phone}', to: '{to_phone}'")
        
        # Format order for label request
        formatted_order = {
            'from_name': order['address_from']['name'],
            'from_phone': from_phone,
            'from_street': order['address_from']['street1'],
            'from_street2': order['address_from'].get('street2', ''),
            'from_city': order['address_from']['city'],
            'from_state': order['address_from']['state'],
            'from_zip': order['address_from']['zip'],
            'to_name': order['address_to']['name'],
            'to_phone': to_phone,
            'to_street': order['address_to']['street1'],
            'to_street2': order['address_to'].get('street2', ''),
            'to_city': order['address_to']['city'],
            'to_state': order['address_to']['state'],
            'to_zip': order['address_to']['zip'],
            'weight': order['parcel']['weight'],
            'length': order['parcel'].get('length', 10),
            'width': order['parcel'].get('width', 10),
            'height': order['parcel'].get('height', 10)
        }
        
        selected_rate = {
            'service_code': order.get('selected_service_code', order.get('service_code', '')),
            'carrier_id': order.get('carrier_id'),
            'rate_id': order.get('rate_id')
        }
        
        # Build label request using service (simplified - maintaining backward compatibility)
        label_request = {
            'label_layout': 'letter',
            'label_format': 'pdf',
            'shipment': {
                'ship_to': {
                    'name': formatted_order['to_name'],
                    'phone': formatted_order['to_phone'],
                    'address_line1': formatted_order['to_street'],
                    'address_line2': formatted_order['to_street2'],
                    'city_locality': formatted_order['to_city'],
                    'state_province': formatted_order['to_state'],
                    'postal_code': formatted_order['to_zip'],
                    'country_code': 'US'
                },
                'ship_from': {
                    'name': formatted_order['from_name'],
                    'company_name': '-',
                    'phone': formatted_order['from_phone'],
                    'address_line1': formatted_order['from_street'],
                    'address_line2': formatted_order['from_street2'],
                    'city_locality': formatted_order['from_city'],
                    'state_province': formatted_order['from_state'],
                    'postal_code': formatted_order['from_zip'],
                    'country_code': 'US',
                    'address_residential_indicator': 'yes'
                },
                'packages': [{
                    'weight': {'value': formatted_order['weight'], 'unit': 'pound'},
                    'dimensions': {
                        'length': formatted_order['length'],
                        'width': formatted_order['width'],
                        'height': formatted_order['height'],
                        'unit': 'inch'
                    }
                }],
                'service_code': selected_rate['service_code']
            },
            'rate_id': selected_rate['rate_id']
        }
        
        logger.info(f"Purchasing label with rate_id: {selected_rate['rate_id']}")
        
        # Profile label creation API call (now truly async!)
        api_start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.shipstation.com/v2/labels',
                headers=headers,
                json=label_request
            )
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        logger.info(f"⚡ ShipStation create label API took {api_duration_ms:.2f}ms")
        
        # ShipStation API returns 200 or 201 for success
        if response.status_code not in [200, 201]:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('message', f'Status code: {response.status_code}')
            logger.error(f"Label creation failed: {error_msg}")
            logger.error(f"Response: {response.text}")
            
            # Log error to session for debugging
            await session_manager.update_session_atomic(telegram_id, data={
                'last_error': f'ShipStation label API error: {error_msg}',
                'error_step': 'CREATE_LABEL_API',
                'error_timestamp': datetime.now(timezone.utc).isoformat(),
                'error_response': response.text[:500]
            })
            
            # Notify admin about label creation error
            from repositories import get_user_repo
            user_repo = get_user_repo()
            user = await user_repo.find_by_telegram_id(telegram_id)
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
        label_id = label_response.get('label_id', '')  # ShipStation label ID
        shipment_id = label_response.get('shipment_id', '')  # ShipStation shipment ID
        tracking_number = label_response.get('tracking_number', '')
        label_download_url = label_response.get('label_download', {}).get('pdf', '')
        
        # Ensure .pdf extension is present
        if label_download_url and not label_download_url.endswith('.pdf'):
            label_download_url = label_download_url + '.pdf'
        
        logger.info(f"Label created: label_id={label_id}, tracking={tracking_number}, label_url={label_download_url}")
        
        # Save label
        label = ShippingLabel(
            order_id=order_id,
            label_id=label_id,
            shipment_id=shipment_id,
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
            try:
                # Download label PDF using service
                from services.shipping_service import download_label_pdf
                success, pdf_bytes, error = await download_label_pdf(label_download_url, timeout=30)
                
                if success:
                    # Generate AI thank you message
                    try:
                        thank_you_msg = await generate_thank_you_message()
                    except Exception as e:
                        logger.error(f"Error generating thank you message: {e}")
                        thank_you_msg = "Спасибо за использование нашего сервиса!"
                    
                    # Send label using service
                    from services.shipping_service import send_label_to_user
                    success, error = await send_label_to_user(
                        bot_instance=bot_instance,
                        telegram_id=telegram_id,
                        pdf_bytes=pdf_bytes,
                        order_id=order_id,
                        tracking_number=tracking_number,
                        carrier=order['selected_carrier'].upper(),
                        safe_telegram_call_func=safe_telegram_call
                    )
                    
                    if success:
                        # Send tracking info
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=telegram_id,
                            text=f"🔗 Трекинг номер:\n\n`{tracking_number}`",
                            parse_mode='Markdown'
                        ))
                        
                        # Send thank you message
                        logger.info(f"Sending thank you message to user {telegram_id}")
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=telegram_id,
                            text=thank_you_msg
                        ))
                        logger.info(f"Label sent successfully to user {telegram_id}")
                    else:
                        logger.error(f"Failed to send label: {error}")
                        raise Exception(error)
                else:
                    # Fallback if PDF download fails
                    logger.error(f"Failed to download PDF: {error}")
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=f"""📦 Shipping label создан!

Tracking: {tracking_number}
Carrier: {order['selected_carrier']}
Service: {order['selected_service']}

Label PDF: {label_download_url}

Вы оплатили: ${order['amount']:.2f}"""
                    ))
                    logger.warning("Could not download label PDF, sent URL instead")
                    
            except Exception as e:
                logger.error(f"Error sending label to user: {e}")
            
            # STEP 4: Save completed label and clear session
            await session_manager.save_completed_label(telegram_id, {
                'order_id': order_id,
                'tracking_number': tracking_number,
                'carrier': order['selected_carrier'],
                'label_url': label_download_url,
                'amount': order['amount']
            })
            logger.info(f"✅ Label saved and session cleared for user {telegram_id}")
                
        # Send notification to admin about new label
        if ADMIN_TELEGRAM_ID:
            try:
                # Get user info
                user = await find_user_by_telegram_id(telegram_id)
                user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
                username = user.get('username', '') if user else ''
                user_display = f"{user_name}" + (f" (@{username})" if username else f" (ID: {telegram_id})")
                
                # Format admin notification
                admin_message = f"""📦 *Новый лейбл создан!*

👤 *Пользователь:* {user_display}

📤 *От:* {order['address_from']['name']}
   {order['address_from']['street1']}, {order['address_from']['city']}, {order['address_from']['state']} {order['address_from']['zip']}

📥 *Кому:* {order['address_to']['name']}  
   {order['address_to']['street1']}, {order['address_to']['city']}, {order['address_to']['state']} {order['address_to']['zip']}

🚚 *Перевозчик:* {order['selected_carrier']} - {order['selected_service']}
📋 *Трекинг:* `{tracking_number}`
💰 *Цена:* ${order['amount']:.2f}
⚖️ *Вес:* {order['parcel']['weight']} lb

🕐 *Время:* {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}"""

                # Send to admin
                if 'application' in globals() and hasattr(application, 'bot'):
                    admin_bot = application.bot
                else:
                    from telegram import Bot
                    admin_bot = Bot(TELEGRAM_BOT_TOKEN)
                
                await safe_telegram_call(admin_bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                ))
                logger.info(f"Label creation notification sent to admin {ADMIN_TELEGRAM_ID}")
            except Exception as e:
                logger.error(f"Failed to send label notification to admin: {e}")
        
        # Check ShipStation balance after label creation
        asyncio.create_task(check_shipstation_balance())
        
        logger.info(f"Label created successfully for order {order_id}")
        return True  # Success
        
    except Exception as e:
        logger.error(f"Error creating label: {e}", exc_info=True)
        
        # Log error to session for debugging
        await session_manager.update_session_atomic(telegram_id, data={
            'last_error': f'Label creation failed: {str(e)[:200]}',
            'error_step': 'CREATE_LABEL',
            'error_timestamp': datetime.now(timezone.utc).isoformat(),
            'error_order_id': order_id
        })
        
        # Notify admin about error
        user = await find_user_by_telegram_id(telegram_id)
        if user:
            await notify_admin_error(
                user_info=user,
                error_type="Label Creation Exception",
                error_details=str(e),
                order_id=order_id
            )
        
        # Send polite message to user with admin contact button
        user_message = """😔 К сожалению, в данный момент мы не можем сгенерировать shipping label.

Пожалуйста, свяжитесь с администратором.

Приносим извинения за неудобства!"""
        
        # Add button to contact admin
        keyboard = []
        if ADMIN_TELEGRAM_ID:
            keyboard.append([InlineKeyboardButton("💬 Связаться с администратором", url=f"tg://user?id={ADMIN_TELEGRAM_ID}")])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if message:
            await safe_telegram_call(message.reply_text(user_message, reply_markup=reply_markup))
        elif bot_instance:
            await safe_telegram_call(bot_instance.send_message(
                chat_id=telegram_id,
                text=user_message,
                reply_markup=reply_markup
            ))
        
        return False  # Failed

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Check if we're on shipping rates screen
    last_state = context.user_data.get('last_state')
    
    # Add "Check Data" button only if on shipping rates selection screen
    if last_state == STATE_NAMES[SELECT_CARRIER]:
        keyboard = [
            [InlineKeyboardButton("📋 Проверить данные", callback_data='check_data')],
            [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='return_to_order')],
            [InlineKeyboardButton("✅ Да, отменить заказ", callback_data='confirm_cancel')]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("↩️ Вернуться к заказу", callback_data='return_to_order')],
            [InlineKeyboardButton("✅ Да, отменить заказ", callback_data='confirm_cancel')]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "⚠️ Вы уверены, что хотите отменить создание заказа?\n\nВсе введённые данные будут потеряны."
    
    bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    # Save last bot message context for button protection
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
    
    # Return the state we were in before cancel
    return context.user_data.get('last_state', PAYMENT_METHOD)

async def confirm_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm order cancellation"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Clear session and context data
    user_id = update.effective_user.id
    await session_manager.clear_session(user_id)
    context.user_data.clear()
    logger.info(f"🗑️ Session cleared after order cancellation for user {user_id}")
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(query.message.reply_text("❌ Создание заказа отменено.", reply_markup=reply_markup))
    return ConversationHandler.END

async def check_data_from_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to data confirmation screen from cancel dialog"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Go back to data confirmation screen
    return await show_data_confirmation(update, context)

async def return_to_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to order after cancel button - restore exact screen"""
    from utils.ui_utils import OrderStepMessages, get_cancel_keyboard
    
    logger.info(f"return_to_order called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Get the state we were in when cancel was pressed
    last_state = context.user_data.get('last_state')
    
    logger.info(f"return_to_order: last_state = {last_state}, type = {type(last_state)}")
    logger.info(f"return_to_order: user_data keys = {list(context.user_data.keys())}")
    
    # If no last_state - just continue
    if last_state is None:
        logger.warning("return_to_order: No last_state found!")
        await safe_telegram_call(query.message.reply_text("Продолжаем оформление заказа..."))
        return FROM_NAME
    
    # If last_state is a number (state constant), we need the string name
    # Check if it's a string (state name) or int (state constant)
    if isinstance(last_state, int):
        # It's a state constant - return it directly
        keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(str(last_state))
        logger.warning(f"return_to_order: last_state is int ({last_state}), should be string!")
        
        # Show next step
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text if message_text else "Продолжаем оформление заказа...",
            reply_markup=reply_markup
        ))
        
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text if message_text else "Продолжаем..."
        
        return last_state
    
    # last_state is a string (state name like "FROM_CITY")
    keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(last_state)
    
    # Send message with or without keyboard
    if keyboard:
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=keyboard))
    else:
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
    
    # Save context
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
    
    # Return the state constant
    return globals().get(last_state, FROM_NAME)
async def root():
    return {"message": "Telegram Shipping Bot API", "status": "running"}


# Debug endpoints removed - were causing startup issues and memory_handler references

@api_router.post("/orders", response_model=dict)
async def create_order(order_data: OrderCreate):
    try:
        # Check user exists using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(order_data.telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found. Please /start the bot first.")
        
        # Generate unique order_id
        from utils.order_utils import generate_order_id
        order_id = generate_order_id(telegram_id=order_data.telegram_id)
        
        # Create order
        order = Order(
            user_id=user['id'],
            order_id=order_id,
            telegram_id=order_data.telegram_id,
            address_from=order_data.address_from,
            address_to=order_data.address_to,
            parcel=order_data.parcel,
            amount=order_data.amount
        )
        
        order_dict = order.model_dump()
        order_dict['created_at'] = order_dict['created_at'].isoformat()
        await db.orders.insert_one(order_dict)
        
        # Create crypto payment invoice - DISABLED (crypto variable not defined, legacy code)
        # if crypto:
        #     invoice = await crypto.create_invoice(
        #         asset="USDT",
        #         amount=order_data.amount
        #     )
            
            # Get payment URL from bot_invoice_url or mini_app_invoice_url
            # pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'mini_app_invoice_url', None)
            # 
            # payment = Payment(
            #     order_id=order.id,
            #     amount=order_data.amount,
            #     invoice_id=invoice.invoice_id,
            #     pay_url=pay_url
            # )
            # payment_dict = payment.model_dump()
            # payment_dict['created_at'] = payment_dict['created_at'].isoformat()
            # await insert_payment(payment_dict)
            # 
            # # Send payment link to user
            # if bot_instance and pay_url:
            #     await safe_telegram_call(bot_instance.send_message(
            #         chat_id=order_data.telegram_id,
            #         text=f"""✅ Заказ создан!
            # 
            # 💰 Оплатите {order_data.amount} USDT:
            # {pay_url}
            # 
            # После оплаты мы автоматически создадим shipping label."""
            #     ))
            # 
            # return {
            #     "order_id": order.id,
            #     "payment_url": pay_url,
            #     "amount": order_data.amount,
            #     "currency": "USDT"
            # }
        
        return {
            "order_id": order.id,
            "message": "Order created successfully"
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/orders/search")
async def search_orders(
    query: Optional[str] = None,
    payment_status: Optional[str] = None,
    shipping_status: Optional[str] = None,
    limit: int = 100
):
    """
    Search orders by tracking number, order ID, or other fields
    """
    try:
        search_filter = {}
        
        # Search by tracking number or order ID
        if query:
            # Get labels with matching tracking number
            labels = await db.shipping_labels.find(
                {"tracking_number": {"$regex": query, "$options": "i"}},
                {"_id": 0, "order_id": 1}
            ).to_list(100)
            
            matching_order_ids = [label['order_id'] for label in labels]
            
            # Search in orders by ID or matching tracking numbers
            search_filter["$or"] = [
                {"id": {"$regex": query, "$options": "i"}},
                {"id": {"$in": matching_order_ids}}
            ]
        
        # Filter by payment status
        if payment_status:
            search_filter["payment_status"] = payment_status
        
        # Filter by shipping status
        if shipping_status:
            search_filter["shipping_status"] = shipping_status
        
        # Get orders
        orders = await db.orders.find(search_filter, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        
        result = []
        
        # For each order, create separate rows for each label
        for order in orders:
            # Get ALL labels for this order
            labels = await db.shipping_labels.find(
                {"order_id": order['id']},
                {"_id": 0}
            ).sort("created_at", -1).to_list(100)
            
            # Get user info once
            user = await find_user_by_telegram_id(order["telegram_id"])
            user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
            user_username = user.get('username', '') if user else ''
            
            if labels:
                # Create a row for each label
                for label in labels:
                    order_row = order.copy()
                    order_row['tracking_number'] = label.get('tracking_number', '')
                    order_row['label_url'] = label.get('label_url', '')
                    order_row['carrier'] = label.get('carrier', '')
                    order_row['label_id'] = label.get('label_id', '')
                    order_row['label_created_at'] = label.get('created_at', '')
                    order_row['user_name'] = user_name
                    order_row['user_username'] = user_username
                    result.append(order_row)
            else:
                # No labels - add order without label info
                order['tracking_number'] = ''
                order['label_url'] = ''
                order['carrier'] = ''
                order['label_id'] = ''
                order['label_created_at'] = ''
                order['user_name'] = user_name
                order['user_username'] = user_username
                result.append(order)
        
        return result
    except Exception as e:
        logger.error(f"Error searching orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/orders/export/csv")
async def export_orders_csv(
    payment_status: Optional[str] = None,
    shipping_status: Optional[str] = None
):
    """
    Export orders to CSV format
    """
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    try:
        # Build query
        query = {}
        if payment_status:
            query["payment_status"] = payment_status
        if shipping_status:
            query["shipping_status"] = shipping_status
        
        # Get all orders
        orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
        
        # Enrich with tracking info
        for order in orders:
            # Get LATEST label (in case of multiple labels per order)
            labels = await db.shipping_labels.find(
                {"order_id": order['id']},
                {"_id": 0}
            ).sort("created_at", -1).limit(1).to_list(1)
            
            if labels:
                label = labels[0]
                order['tracking_number'] = label.get('tracking_number', '')
                order['carrier'] = label.get('carrier', '')
            else:
                order['tracking_number'] = ''
                order['carrier'] = ''
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Order ID',
            'Telegram ID',
            'Amount',
            'Payment Status',
            'Shipping Status',
            'Tracking Number',
            'Carrier',
            'From Name',
            'From City',
            'From State',
            'From ZIP',
            'To Name',
            'To City',
            'To State',
            'To ZIP',
            'Weight (lb)',
            'Created At',
            'Refund Status'
        ])
        
        # Write data
        for order in orders:
            writer.writerow([
                order['id'],
                order['telegram_id'],
                order['amount'],
                order['payment_status'],
                order['shipping_status'],
                order.get('tracking_number', ''),
                order.get('carrier', ''),
                order['address_from']['name'],
                order['address_from']['city'],
                order['address_from']['state'],
                order['address_from']['zip'],
                order['address_to']['name'],
                order['address_to']['city'],
                order['address_to']['state'],
                order['address_to']['zip'],
                order['parcel']['weight'],
                order['created_at'],
                order.get('refund_status', 'none')
            ])
        
        # Return CSV file
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/orders", response_model=List[dict])
async def get_orders(telegram_id: Optional[int] = None):
    query = {"telegram_id": telegram_id} if telegram_id else {}
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    result = []
    
    # For each order, create separate rows for each label
    for order in orders:
        # Get ALL labels for this order
        labels = await db.shipping_labels.find(
            {"order_id": order['id']},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        # Get user info once
        user = await find_user_by_telegram_id(order["telegram_id"])
        user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
        user_username = user.get('username', '') if user else ''
        
        if labels:
            # Create a row for each label
            for label in labels:
                order_row = order.copy()
                order_row['tracking_number'] = label.get('tracking_number', '')
                order_row['label_url'] = label.get('label_url', '')
                order_row['carrier'] = label.get('carrier', '')
                order_row['label_id'] = label.get('label_id', '')
                order_row['label_created_at'] = label.get('created_at', '')
                order_row['user_name'] = user_name
                order_row['user_username'] = user_username
                result.append(order_row)
        else:
            # No labels - add order without label info
            order['tracking_number'] = ''
            order['label_url'] = ''
            order['carrier'] = ''
            order['label_id'] = ''
            order['label_created_at'] = ''
            order['user_name'] = user_name
            order['user_username'] = user_username
            result.append(order)
    
    return result

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
    """
    Get detailed tracking information with progress status
    """
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # ShipStation V2 tracking endpoint (async)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f'https://api.shipstation.com/v2/tracking?tracking_number={tracking_number}&carrier_code={carrier}',
                headers=headers
            )
        
        if response.status_code == 200:
            tracking_data = response.json()
            status_code = tracking_data.get('status_code', 'UNKNOWN')
            
            # Map status to progress percentage
            status_map = {
                'NY': {'name': 'Not Yet Shipped', 'progress': 0, 'color': 'gray'},
                'IT': {'name': 'In Transit', 'progress': 50, 'color': 'blue'},
                'DE': {'name': 'Delivered', 'progress': 100, 'color': 'green'},
                'EX': {'name': 'Exception', 'progress': 25, 'color': 'red'},
                'UN': {'name': 'Unknown', 'progress': 0, 'color': 'gray'},
                'AT': {'name': 'Attempted Delivery', 'progress': 75, 'color': 'orange'},
            }
            
            status_info = status_map.get(status_code, {'name': 'Unknown', 'progress': 0, 'color': 'gray'})
            
            return {
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status_code": status_code,
                "status_name": status_info['name'],
                "progress": status_info['progress'],
                "progress_color": status_info['color'],
                "estimated_delivery": tracking_data.get('estimated_delivery_date'),
                "actual_delivery": tracking_data.get('actual_delivery_date'),
                "tracking_events": tracking_data.get('events', [])[:5],  # Last 5 events
                "carrier_status_description": tracking_data.get('status_description', '')
            }
        else:
            return {
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status_code": "UN",
                "status_name": "Unknown",
                "progress": 0,
                "progress_color": "gray",
                "message": "Tracking information not available"
            }
    except Exception as e:
        logger.error(f"Error tracking shipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/labels/{label_id}/download")
async def download_label(label_id: str):
    """
    Proxy endpoint to download label PDF from ShipStation with authentication
    """
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        # Find label in database
        label = await db.shipping_labels.find_one({"label_id": label_id}, {"_id": 0})
        if not label:
            raise HTTPException(status_code=404, detail="Label not found")
        
        label_url = label.get('label_url')
        if not label_url:
            raise HTTPException(status_code=404, detail="Label URL not available")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY
        }
        
        # Download label from ShipStation (async)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                label_url,
                headers=headers
            )
        
        if response.status_code == 200:
            from fastapi.responses import Response
            
            # Return PDF with proper headers
            return Response(
                content=response.content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=label_{label_id}.pdf"
                }
            )
        else:
            logger.error(f"Failed to download label: {response.status_code}")
            raise HTTPException(status_code=502, detail="Failed to download label from ShipStation")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/orders/{order_id}/refund")
async def refund_order(order_id: str, refund_reason: Optional[str] = None):
    """
    Refund an order - void label on ShipStation and return money to user balance
    """
    try:
        # Find order
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Check if already refunded
        if order.get('refund_status') == 'refunded':
            raise HTTPException(status_code=400, detail="Order already refunded")
        
        # Check if paid
        if order['payment_status'] != 'paid':
            raise HTTPException(status_code=400, detail="Cannot refund unpaid order")
        
        # Get label for voiding
        label = await db.shipping_labels.find_one({"order_id": order_id}, {"_id": 0})
        void_success = False
        void_message = ""
        
        # Try to void label on ShipStation if label exists
        if label and label.get('label_id') and SHIPSTATION_API_KEY:
            try:
                headers = {
                    'API-Key': SHIPSTATION_API_KEY,
                    'Content-Type': 'application/json'
                }
                
                # Void label on ShipStation V2 (async)
                async with httpx.AsyncClient(timeout=10.0) as client:
                    void_response = await client.put(
                        f'https://api.shipstation.com/v2/labels/{label["label_id"]}/void',
                        headers=headers
                    )
                
                if void_response.status_code == 200:
                    void_data = void_response.json()
                    void_success = void_data.get('approved', False)
                    void_message = void_data.get('message', 'Label voided successfully')
                    logger.info(f"Label voided: {label['label_id']}, approved={void_success}")
                else:
                    logger.warning(f"Failed to void label: {void_response.status_code} - {void_response.text}")
                    void_message = "Could not void label on carrier"
                    
            except Exception as e:
                logger.error(f"Error voiding label: {e}")
                void_message = f"Error voiding label: {str(e)}"
        
        # Update ALL labels for this order to "refunded" status (removes from profit calculation)
        await db.shipping_labels.update_many(
            {"order_id": order_id},
            {"$set": {"status": "refunded"}}
        )
        logger.info(f"Updated all labels for order {order_id} to status='refunded'")
        
        # Get user
        user = await find_user_by_telegram_id(order["telegram_id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Return amount to user balance
        refund_amount = order['amount']
        new_balance = user.get('balance', 0) + refund_amount
        
        await db.users.update_one(
            {"telegram_id": order['telegram_id']},
            {"$set": {"balance": new_balance}}
        )
        
        # Update order status
        await db.orders.update_one(
            {"id": order_id},
            {
                "$set": {
                    "refund_status": "refunded",
                    "refund_amount": refund_amount,
                    "refund_reason": refund_reason or "Admin refund",
                    "refund_date": datetime.now(timezone.utc).isoformat(),
                    "shipping_status": "cancelled",
                    "void_status": "voided" if void_success else "void_failed",
                    "void_message": void_message
                }
            }
        )
        
        # Notify user via Telegram
        if bot_instance:
            try:
                void_status_text = "✅ Этикетка отменена" if void_success else "⚠️ Этикетка не отменена"
                message = f"""💰 Возврат средств

Заказ #{order_id[:8]} был отменён.

Возвращено на баланс: ${refund_amount:.2f}
Новый баланс: ${new_balance:.2f}

{void_status_text}
Причина: {refund_reason or 'Возврат администратором'}"""
                
                # Add main menu button
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=order['telegram_id'],
                    text=message,
                    reply_markup=reply_markup
                ))
            except Exception as e:
                logger.error(f"Failed to send refund notification: {e}")
        
        return {
            "order_id": order_id,
            "refund_amount": refund_amount,
            "new_balance": new_balance,
            "void_success": void_success,
            "void_message": void_message,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refunding order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/admin/create-label/{order_id}", dependencies=[Depends(verify_admin_key)])
async def create_label_manually(order_id: str):
    """
    Manually create shipping label for paid order (admin function)
    """
    try:
        # Find order
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Check if paid
        if order['payment_status'] != 'paid':
            raise HTTPException(status_code=400, detail="Order must be paid to create label")
        
        # If label already exists, we'll recreate it (void old one first if possible)
        recreating = bool(order.get('label_id'))
        if recreating:
            logger.info(f"Recreating label for order {order_id} (old label_id: {order.get('label_id')})")
        
        # Prepare ShipStation API request
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API key not configured")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Build shipment data from order
        shipment_data = {
            'shipment': {
                'service_code': order.get('selected_service_code', order.get('service_code', '')),
                'ship_to': {
                    'name': order['address_to']['name'],
                    'phone': order['address_to'].get('phone', ''),
                    'company_name': '-',
                    'address_line1': order['address_to']['street'],
                    'address_line2': order['address_to'].get('street2', ''),
                    'city_locality': order['address_to']['city'],
                    'state_province': order['address_to']['state'],
                    'postal_code': order['address_to']['zip'],
                    'country_code': 'US'
                },
                'ship_from': {
                    'name': order['address_from']['name'],
                    'phone': order['address_from'].get('phone', ''),
                    'company_name': '-',
                    'address_line1': order['address_from']['street'],
                    'address_line2': order['address_from'].get('street2', ''),
                    'city_locality': order['address_from']['city'],
                    'state_province': order['address_from']['state'],
                    'postal_code': order['address_from']['zip'],
                    'country_code': 'US'
                },
                'packages': [{
                    'weight': {
                        'value': order['parcel'].get('weight', 1),
                        'unit': 'pound'
                    },
                    'dimensions': {
                        'length': order['parcel'].get('length', 10),
                        'width': order['parcel'].get('width', 10),
                        'height': order['parcel'].get('height', 10),
                        'unit': 'inch'
                    }
                }]
            }
        }
        
        logger.info(f"Creating label manually for order {order_id}")
        
        # Create label via ShipStation (async)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.shipstation.com/v2/labels',
                headers=headers,
                json=shipment_data
            )
        
        if response.status_code != 200:
            error_msg = response.text
            logger.error(f"ShipStation label creation failed: {error_msg}")
            raise HTTPException(status_code=response.status_code, detail=f"ShipStation error: {error_msg}")
        
        label_response = response.json()
        label_data = label_response.get('label', {})
        
        # Extract label info
        label_id = label_data.get('label_id')
        tracking_number = label_data.get('tracking_number')
        carrier_code = label_data.get('carrier_code', '').lower()
        label_download_url = label_data.get('label_download', {}).get('pdf')
        
        if not label_id or not tracking_number:
            raise HTTPException(status_code=500, detail="Failed to get label info from ShipStation")
        
        # Save label to database
        label_doc = {
            'label_id': label_id,
            'order_id': order_id,
            'tracking_number': tracking_number,
            'carrier': carrier_code,
            'label_url': label_download_url,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'created'
        }
        await db.shipping_labels.insert_one({**label_doc, '_id': label_id})
        
        # Update order with label info
        await db.orders.update_one(
            {'id': order_id},
            {
                '$set': {
                    'label_id': label_id,
                    'tracking_number': tracking_number,
                    'carrier': carrier_code,
                    'shipping_status': 'label_created',
                    'label_created_at': datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        logger.info(f"Label created manually for order {order_id}: {label_id}")
        
        # Try to send notification to user via Telegram
        try:
            if bot_instance:
                telegram_id = order.get('telegram_id')
                if telegram_id:
                    message = f"""✅ Ваша shipping label создана!

📦 Order ID: {order_id[:8]}
📋 Tracking #: {tracking_number}
🚚 Carrier: {carrier_code.upper()}

Вы можете отслеживать посылку по номеру отслеживания."""
                    
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=message
                    ))
        except Exception as e:
            logger.error(f"Failed to send label notification: {e}")
        
        return {
            "status": "success",
            "order_id": order_id,
            "label_id": label_id,
            "tracking_number": tracking_number,
            "carrier": carrier_code,
            "message": "Label created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating label manually: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/admin/create-label-manual", dependencies=[Depends(verify_admin_key)])
async def create_label_manual_form(request: Request):
    """
    Create shipping label from manual form input (admin function)
    """
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ['from_address', 'to_address', 'parcel', 'service_code']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Prepare ShipStation API request
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API key not configured")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Build shipment data
        shipment_data = {
            'shipment': {
                'service_code': data['service_code'],
                'ship_to': {
                    'name': data['to_address']['name'],
                    'phone': data['to_address'].get('phone', ''),
                    'company_name': '-',
                    'address_line1': data['to_address']['street'],
                    'address_line2': data['to_address'].get('street2', ''),
                    'city_locality': data['to_address']['city'],
                    'state_province': data['to_address']['state'],
                    'postal_code': data['to_address']['zip'],
                    'country_code': 'US'
                },
                'ship_from': {
                    'name': data['from_address']['name'],
                    'phone': data['from_address'].get('phone', ''),
                    'company_name': '-',
                    'address_line1': data['from_address']['street'],
                    'address_line2': data['from_address'].get('street2', ''),
                    'city_locality': data['from_address']['city'],
                    'state_province': data['from_address']['state'],
                    'postal_code': data['from_address']['zip'],
                    'country_code': 'US'
                },
                'packages': [{
                    'weight': {
                        'value': data['parcel']['weight'],
                        'unit': 'pound'
                    },
                    'dimensions': {
                        'length': data['parcel']['length'],
                        'width': data['parcel']['width'],
                        'height': data['parcel']['height'],
                        'unit': 'inch'
                    }
                }]
            }
        }
        
        logger.info("Creating label manually from form")
        
        # Create label via ShipStation (async)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.shipstation.com/v2/labels',
                headers=headers,
                json=shipment_data
            )
        
        if response.status_code != 200:
            error_msg = response.text
            logger.error(f"ShipStation label creation failed: {error_msg}")
            raise HTTPException(status_code=response.status_code, detail=f"ShipStation error: {error_msg}")
        
        label_response = response.json()
        label_data = label_response.get('label', {})
        
        # Extract label info
        label_id = label_data.get('label_id')
        tracking_number = label_data.get('tracking_number')
        carrier_code = label_data.get('carrier_code', '').lower()
        label_download_url = label_data.get('label_download', {}).get('pdf')
        
        if not label_id or not tracking_number:
            raise HTTPException(status_code=500, detail="Failed to get label info from ShipStation")
        
        # Generate order ID
        order_id = str(uuid.uuid4())
        
        # Save label to database
        label_doc = {
            'label_id': label_id,
            'order_id': order_id,
            'tracking_number': tracking_number,
            'carrier': carrier_code,
            'label_url': label_download_url,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'created',
            'manual_creation': True
        }
        await db.shipping_labels.insert_one({**label_doc, '_id': label_id})
        
        # Create order record
        order_doc = {
            'id': order_id,
            'telegram_id': 'manual',
            'user_name': 'Manual Creation',
            'address_from': data['from_address'],
            'address_to': data['to_address'],
            'parcel': data['parcel'],
            'label_id': label_id,
            'tracking_number': tracking_number,
            'carrier': carrier_code,
            'service_code': data['service_code'],
            'amount': 0,
            'payment_status': 'manual',
            'shipping_status': 'label_created',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'label_created_at': datetime.now(timezone.utc).isoformat(),
            'manual_creation': True
        }
        await db.orders.insert_one({**order_doc, '_id': order_id})
        
        logger.info(f"Label created manually from form: {label_id}")
        
        return {
            "status": "success",
            "order_id": order_id,
            "label_id": label_id,
            "tracking_number": tracking_number,
            "carrier": carrier_code,
            "download_url": f"/api/labels/{label_id}/download",
            "message": "Label created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating label from form: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/oxapay/webhook")
async def oxapay_webhook(request: Request):
    """Handle Oxapay payment webhooks"""
    return await handle_oxapay_webhook(
        request, 
        db, 
        bot_instance, 
        safe_telegram_call, 
        find_user_by_telegram_id, 
        find_pending_order, 
        create_and_send_label
    )

# get_users moved to routers/admin_router.py


@api_router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    return await handle_telegram_webhook(request, application)


@api_router.get("/debug/logs")
async def get_debug_logs(lines: int = 200, filter: str = ""):
    """Get recent backend logs for debugging (NO AUTH)
    
    Usage:
    - /api/debug/logs?lines=200 - get last 200 lines
    - /api/debug/logs?filter=PERSISTENCE - filter by keyword
    - /api/debug/logs?lines=500&filter=ERROR - get 500 lines with ERROR
    """
    try:
        import subprocess
        import os
        
        # Try multiple log locations
        log_files = [
            "/var/log/supervisor/backend.err.log",
            "/var/log/supervisor/backend.out.log",
            "/var/log/backend.log",
            "/app/backend.log",
            "backend.log"
        ]
        
        all_logs = []
        found_files = []
        
        for log_file in log_files:
            if os.path.exists(log_file):
                found_files.append(log_file)
                try:
                    cmd = f"tail -n {lines} {log_file}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                    if result.stdout:
                        all_logs.extend([f"[{log_file}] {line}" for line in result.stdout.split('\n') if line])
                except Exception as e:
                    logger.warning(f"Error reading log file {log_file}: {e}")
                    pass
        
        # Filter if requested
        if filter:
            all_logs = [line for line in all_logs if filter.upper() in line.upper()]
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_lines": len(all_logs),
            "filter": filter or "none",
            "log_files_checked": log_files,
            "log_files_found": found_files,
            "logs": all_logs[-100:]  # Return max 100 lines for readability
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@api_router.get("/debug/clear-all-conversations")
async def clear_all_conversations():
    """EMERGENCY: Clear all conversation states (NO AUTH) - Use GET for easy browser access"""
    try:
        # Delete all conversation documents
        result = await db.bot_persistence.delete_many({"_id": {"$regex": "^conversation_"}})
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deleted_count": result.deleted_count,
            "message": "All conversation states cleared successfully! Users can now start fresh."
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@api_router.get("/debug/active-conversations")
async def debug_active_conversations():
    """Check active conversations in memory (NO AUTH)"""
    try:
        if not application or not application.persistence:
            return {"error": "Application or persistence not initialized"}
        
        # Get conversations from persistence
        order_convs = await application.persistence.get_conversations("order_conv_handler")
        template_convs = await application.persistence.get_conversations("template_rename_handler")
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_conversations": {
                "count": len(order_convs),
                "data": {str(k): v for k, v in order_convs.items()}
            },
            "template_conversations": {
                "count": len(template_convs),
                "data": {str(k): v for k, v in template_convs.items()}
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@api_router.get("/debug/persistence")
async def debug_persistence():
    """Check MongoDB persistence state (NO AUTH)"""
    try:
        # Get all persistence data from MongoDB
        persistence_docs = await db.bot_persistence.find({}).to_list(100)
        
        # Convert ObjectId to string for JSON serialization
        for doc in persistence_docs:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            if 'updated_at' in doc:
                doc['updated_at'] = doc['updated_at'].isoformat() if hasattr(doc['updated_at'], 'isoformat') else str(doc['updated_at'])
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_documents": len(persistence_docs),
            "documents": persistence_docs
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@api_router.get("/telegram/status")
async def telegram_status():
    """Check Telegram bot application status (NO AUTH REQUIRED FOR DEBUG)"""
    webhook_url = os.environ.get('WEBHOOK_URL', '')
    webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
    
    # Determine bot mode
    bot_mode = "UNKNOWN"
    if webhook_url or (webhook_base_url and 'preview' not in webhook_base_url.lower()):
        bot_mode = "WEBHOOK"
    else:
        bot_mode = "POLLING"
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "application_initialized": application is not None,
        "application_running": application.running if application else False,
        "bot_instance": bot_instance is not None,
        "telegram_token_set": bool(TELEGRAM_BOT_TOKEN),
        "webhook_url_env": webhook_url or 'Not set',
        "webhook_base_url_env": webhook_base_url or 'Not set',
        "bot_mode": bot_mode,
        "mode_description": "WEBHOOK mode eliminates double message bug. POLLING mode may cause conflicts.",
        "persistence": {
            "type": type(application.persistence).__name__ if application and application.persistence else "None",
            "store_data": str(application.persistence.store_data) if application and application.persistence else "None"
        },
        "conversation_handlers": [
            {
                "name": getattr(h, 'name', 'unnamed'),
                "persistent": getattr(h, 'persistent', False)
            }
            for h in (application.handlers.get(0, []) if application else [])
            if hasattr(h, '__class__') and 'ConversationHandler' in h.__class__.__name__
        ]
    }



@api_router.get("/users/{telegram_id}/details")
async def get_user_details(telegram_id: int):
    try:
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
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

@api_router.post("/users/{telegram_id}/block")
async def block_user(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Block a user from using the bot"""
    try:
        # Block user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        
        # Check if user exists
        user = await user_repo.find_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Block user
        result = await user_repo.block_user(telegram_id)
        
        if result:
            # Notify user via Telegram
            if bot_instance:
                try:
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text="⛔️ *Вы были заблокированы администратором.*\n\nДоступ к боту ограничен.",
                        parse_mode='Markdown'
                    ))
                except Exception as e:
                    logger.error(f"Failed to send block notification: {e}")
            
            return {"success": True, "message": "User blocked successfully"}
        else:
            return {"success": False, "message": "User already blocked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/{telegram_id}/unblock")
async def unblock_user(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Unblock a user to allow bot usage"""
    try:
        # Unblock user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        
        # Check if user exists
        user = await user_repo.find_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Unblock user
        result = await user_repo.unblock_user(telegram_id)
        
        if result:
            # Notify user via Telegram
            if bot_instance:
                try:
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text="✅ *Вы были разблокированы!*\n\nТеперь вы можете снова использовать бот.",
                        parse_mode='Markdown'
                    ))
                except Exception as e:
                    logger.error(f"Failed to send unblock notification: {e}")
            
            return {"success": True, "message": "User unblocked successfully"}
        else:
            return {"success": False, "message": "User already unblocked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unblocking user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/{telegram_id}/invite-channel")
async def invite_user_to_channel(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Send channel invitation to a specific user"""
    try:
        # Get user using Repository Pattern
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user is blocked
        if user.get('blocked', False):
            raise HTTPException(status_code=400, detail="Cannot send invitation to blocked user")
        
        if not CHANNEL_INVITE_LINK:
            raise HTTPException(status_code=500, detail="Channel invite link not configured")
        
        if not bot_instance:
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        # Send invitation message with inline button for channel
        inline_keyboard = [[InlineKeyboardButton("📣 Присоединиться к каналу", url=CHANNEL_INVITE_LINK)]]
        inline_markup = InlineKeyboardMarkup(inline_keyboard)
        
        message = """🎉 *Приглашение в наш канал!*

Присоединяйтесь к нашему каналу и получайте:

📦 Актуальные тарифы доставки
💰 Специальные предложения и скидки
🔔 Новости и обновления сервиса
⚡️ Эксклюзивные акции для подписчиков

👇 Нажмите кнопку ниже, чтобы присоединиться:"""
        
        try:
            await safe_telegram_call(bot_instance.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=inline_markup
            ))
            
            # Update user record to track invitation
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {"channel_invite_sent": True, "channel_invite_sent_at": datetime.now(timezone.utc).isoformat()}}
            )
            
            return {"success": True, "message": "Channel invitation sent successfully"}
        except Exception as e:
            logger.error(f"Failed to send channel invitation: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send invitation: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending channel invitation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/invite-all-channel")
async def invite_all_users_to_channel(authenticated: bool = Depends(verify_admin_key)):
    """Send channel invitation to all users"""
    try:
        if not CHANNEL_INVITE_LINK:
            raise HTTPException(status_code=500, detail="Channel invite link not configured")
        
        if not bot_instance:
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        # Get all users
        users = await db.users.find({}).to_list(None)
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        failed_users = []
        skipped_users = []
        
        keyboard = [[InlineKeyboardButton("📣 Присоединиться к каналу", url=CHANNEL_INVITE_LINK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = """🎉 *Приглашение в наш канал!*

Присоединяйтесь к нашему каналу и получайте:

📦 Актуальные тарифы доставки
💰 Специальные предложения и скидки
🔔 Новости и обновления сервиса
⚡️ Эксклюзивные акции для подписчиков

👇 Нажмите кнопку ниже, чтобы присоединиться:"""
        
        for user in users:
            # Skip blocked users
            if user.get('blocked', False):
                skipped_count += 1
                skipped_users.append(user['telegram_id'])
                logger.info(f"Skipping user {user['telegram_id']} - user is blocked")
                continue
            
            # Skip users who blocked the bot
            if user.get('bot_blocked_by_user', False):
                skipped_count += 1
                skipped_users.append(user['telegram_id'])
                logger.info(f"Skipping user {user['telegram_id']} - user blocked the bot")
                continue
            
            # Skip users who are already channel members
            if user.get('is_channel_member', False):
                skipped_count += 1
                skipped_users.append(user['telegram_id'])
                logger.info(f"Skipping user {user['telegram_id']} - already in channel")
                continue
            
            try:
                # Send invitation with inline button
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=user['telegram_id'],
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                ))
                
                # Update user record
                await db.users.update_one(
                    {"telegram_id": user['telegram_id']},
                    {"$set": {"channel_invite_sent": True, "channel_invite_sent_at": datetime.now(timezone.utc).isoformat()}}
                )
                
                success_count += 1
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.02)
            except Exception as e:
                logger.error(f"Failed to send invitation to user {user['telegram_id']}: {e}")
                failed_count += 1
                failed_users.append(user['telegram_id'])
        
        return {
            "success": True,
            "message": f"Invitations sent to {success_count} users, skipped {skipped_count} already in channel",
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "failed_users": failed_users,
            "skipped_users": skipped_users
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending mass channel invitations: {e}")
        raise HTTPException(status_code=500, detail=str(e))



class BroadcastRequest(BaseModel):
    message: str
    image_url: Optional[str] = None
    file_id: Optional[str] = None  # Telegram file_id from upload

@api_router.post("/broadcast")
async def broadcast_message(
    request: BroadcastRequest,
    authenticated: bool = Depends(verify_admin_key)
):
    """Send broadcast message to all users"""
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message is required")
        
        message = request.message
        image_url = request.image_url
        file_id = request.file_id
        
        if not bot_instance:
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        # Get all users
        users = await db.users.find({}).to_list(None)
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        failed_users = []
        skipped_users = []
        
        for user in users:
            # Skip admin-blocked users
            if user.get('blocked', False):
                skipped_count += 1
                skipped_users.append(user['telegram_id'])
                logger.info(f"Skipping broadcast to user {user['telegram_id']} - user is blocked by admin")
                continue
            
            # Skip users who blocked the bot
            if user.get('bot_blocked_by_user', False):
                skipped_count += 1
                skipped_users.append(user['telegram_id'])
                logger.info(f"Skipping broadcast to user {user['telegram_id']} - user blocked the bot")
                continue
            
            try:
                # Send broadcast message (with image if provided)
                if file_id:
                    # Use Telegram file_id (faster and more reliable)
                    await safe_telegram_call(bot_instance.send_photo(
                        chat_id=user['telegram_id'],
                        photo=file_id,
                        caption=message,
                        parse_mode='Markdown'
                    ))
                elif image_url:
                    # Use URL
                    await safe_telegram_call(bot_instance.send_photo(
                        chat_id=user['telegram_id'],
                        photo=image_url,
                        caption=message,
                        parse_mode='Markdown'
                    ))
                else:
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=user['telegram_id'],
                        text=message,
                        parse_mode='Markdown'
                    ))
                
                success_count += 1
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.02)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to send broadcast to user {user['telegram_id']}: {e}")
                
                # Check if user blocked the bot
                if "bot was blocked by the user" in error_msg.lower() or "forbidden" in error_msg.lower():
                    logger.warning(f"User {user['telegram_id']} has blocked the bot")
                    await db.users.update_one(
                        {"telegram_id": user['telegram_id']},
                        {"$set": {"bot_blocked_by_user": True, "bot_blocked_at": datetime.now(timezone.utc).isoformat()}}
                    )
                
                failed_count += 1
                failed_users.append(user['telegram_id'])
        
        return {
            "success": True,
            "message": f"Broadcast sent to {success_count} users, skipped {skipped_count} blocked users",
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "failed_users": failed_users,
            "skipped_users": skipped_users
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/maintenance/status")
async def get_maintenance_status(authenticated: bool = Depends(verify_admin_key)):
    """Get current maintenance mode status"""
    try:
        settings = await db.settings.find_one({"key": "maintenance_mode"})
        is_maintenance = settings.get("value", False) if settings else False
        
        return {
            "maintenance_mode": is_maintenance
        }
    except Exception as e:
        logger.error(f"Error getting maintenance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/maintenance/enable")
async def enable_maintenance_mode(authenticated: bool = Depends(verify_admin_key)):
    """Enable maintenance mode - notify all users and admin"""
    try:
        # Set maintenance mode in database
        await db.settings.update_one(
            {"key": "maintenance_mode"},
            {"$set": {"value": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        # Send message to all users
        users = await db.users.find({"blocked": {"$ne": True}}).to_list(length=None)
        
        maintenance_message = """🔧 *Бот находится на техническом обслуживании.*

Пожалуйста, попробуйте позже.

Приносим извинения за неудобства."""
        
        success_count = 0
        failed_count = 0
        
        for user in users:
            try:
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=user['telegram_id'],
                    text=maintenance_message,
                    parse_mode='Markdown'
                ))
                success_count += 1
                await asyncio.sleep(0.02)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to send maintenance message to {user['telegram_id']}: {e}")
                failed_count += 1
        
        # Send confirmation to admin
        if ADMIN_TELEGRAM_ID:
            admin_message = f"""✅ *Режим технического обслуживания включён*

📊 Уведомлений отправлено: {success_count}
❌ Ошибок: {failed_count}

Вы можете продолжать работу с ботом для тестирования и исправлений."""
            
            try:
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                ))
            except Exception as e:
                logger.error(f"Failed to send confirmation to admin: {e}")
        
        return {
            "status": "success",
            "maintenance_mode": True,
            "users_notified": success_count,
            "failed": failed_count
        }
        
    except Exception as e:
        logger.error(f"Error enabling maintenance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/maintenance/disable")
async def disable_maintenance_mode(authenticated: bool = Depends(verify_admin_key)):
    """Disable maintenance mode - notify all users"""
    try:
        # Disable maintenance mode in database
        await db.settings.update_one(
            {"key": "maintenance_mode"},
            {"$set": {"value": False, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        # Send message to all users that bot is back online
        users = await db.users.find({"blocked": {"$ne": True}}).to_list(length=None)
        
        back_online_message = """✅ *Бот снова работает!*

Техническое обслуживание завершено. Вы можете продолжать пользоваться ботом.

Спасибо за ожидание! 🚀"""
        
        success_count = 0
        failed_count = 0
        
        for user in users:
            try:
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=user['telegram_id'],
                    text=back_online_message,
                    parse_mode='Markdown'
                ))
                success_count += 1
                await asyncio.sleep(0.02)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to send back online message to {user['telegram_id']}: {e}")
                failed_count += 1
        
        # Send confirmation to admin
        if ADMIN_TELEGRAM_ID:
            admin_message = f"""✅ *Режим технического обслуживания выключен*

📊 Уведомлений отправлено: {success_count}
❌ Ошибок: {failed_count}

Бот снова доступен для всех пользователей."""
            
            try:
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                ))
            except Exception as e:
                logger.error(f"Failed to send confirmation to admin: {e}")
        
        return {
            "status": "success",
            "maintenance_mode": False,
            "users_notified": success_count,
            "failed": failed_count
        }
        
    except Exception as e:
        logger.error(f"Error disabling maintenance mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def delayed_restart():
    """Restart backend after a short delay to allow response to be sent"""
    logger.info("Scheduling bot restart...")
    import subprocess
    
    # Run restart script in background - it will wait 2 seconds then restart
    # Using nohup to detach from current process
    subprocess.Popen(
        ['nohup', '/tmp/restart_bot.sh'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    logger.info("Restart script launched in background")

@api_router.post("/bot/restart")
async def restart_bot(
    background_tasks: BackgroundTasks, 
    authenticated: bool = Depends(verify_admin_key)
):
    """Restart the Telegram bot backend service"""
    try:
        logger.info("Bot restart requested by admin")
        
        # Schedule restart in background after response is sent
        background_tasks.add_task(delayed_restart)
        
        logger.info("Bot restart scheduled successfully")
        return {
            "status": "success",
            "message": "Бот будет перезагружен через 2 секунды...",
            "note": "Подождите 10-15 секунд для завершения перезагрузки"
        }
            
    except Exception as e:
        logger.error(f"Error scheduling bot restart: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/settings/api-mode")
async def get_api_mode(authenticated: bool = Depends(verify_admin_key)):
    """Get current API mode (test or production)"""
    try:
        setting = await db.settings.find_one({"key": "api_mode"})
        mode = setting.get("value", "production") if setting else "production"
        return {"mode": mode}
    except Exception as e:
        logger.error(f"Error getting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/settings/api-mode")
async def set_api_mode(request: dict, authenticated: bool = Depends(verify_admin_key)):
    """Set API mode (test or production)"""
    try:
        mode = request.get("mode")
        if mode not in ["test", "production"]:
            raise HTTPException(status_code=400, detail="Mode must be 'test' or 'production'")
        
        # Save to database
        await db.settings.update_one(
            {"key": "api_mode"},
            {"$set": {"value": mode, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        # Update environment variable in-memory (will revert on restart)
        global SHIPSTATION_API_KEY, SHIPSTATION_CARRIER_IDS
        if mode == "test":
            SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY_TEST', SHIPSTATION_API_KEY)
            mode_text = "🧪 Тестовый"
            api_key_display = SHIPSTATION_API_KEY[:20] + "..." if len(SHIPSTATION_API_KEY) > 20 else SHIPSTATION_API_KEY
        else:
            SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY_PROD', SHIPSTATION_API_KEY)
            mode_text = "🚀 Продакшн"
            api_key_display = SHIPSTATION_API_KEY[:20] + "..." if len(SHIPSTATION_API_KEY) > 20 else SHIPSTATION_API_KEY
        
        # Clear carrier IDs cache when switching modes
        SHIPSTATION_CARRIER_IDS = []
        logger.info(f"Cleared carrier IDs cache after switching to {mode} mode")
        
        # Clear settings cache
        clear_settings_cache()
        logger.info("Cleared settings cache")
        
        # Send notification to admin via Telegram
        if ADMIN_TELEGRAM_ID and bot_instance:
            try:
                notification_message = f"""🔄 *API режим переключен*

Новый режим: *{mode_text}*
API Key: `{api_key_display}`

ShipStation API: https://ssapi.shipstation.com/

⏰ Время: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"""
                
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=notification_message,
                    parse_mode='Markdown'
                ))
                logger.info(f"API mode notification sent to admin {ADMIN_TELEGRAM_ID}")
            except Exception as e:
                logger.error(f"Failed to send API mode notification to admin: {e}")
        
        logger.info(f"API mode switched to: {mode}")
        return {"status": "success", "mode": mode}
    except Exception as e:
        logger.error(f"Error setting API mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bot/health")
async def get_bot_health(authenticated: bool = Depends(verify_admin_key)):
    """Get bot health statistics and safety metrics"""
    try:
        # Check if Telegram bot is actually running
        bot_is_running = False
        try:
            if 'bot_instance' in globals() and bot_instance is not None:
                # Bot instance exists, check if we can interact with it
                bot_is_running = True
        except Exception as e:
            logger.debug(f"Bot check failed: {e}")
        
        if not bot_is_running:
            return {
                "status": "unhealthy",
                "message": "Telegram bot is not running",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        safety_stats = telegram_safety.get_statistics()
        best_practices = TelegramBestPractices.get_guidelines()
        protection_info = bot_protection.get_instance_info()
        
        # Get database stats
        total_users = await db.users.count_documents({})
        total_orders = await db.orders.count_documents({})
        blocked_users_db = await db.users.count_documents({"blocked": True})
        
        # Get API mode
        api_mode_setting = await db.settings.find_one({"key": "api_mode"})
        api_mode = api_mode_setting.get("value", "production") if api_mode_setting else "production"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": "N/A",  # Can be calculated from startup time
            "safety_statistics": safety_stats,
            "best_practices_active": len(best_practices),
            "guidelines": best_practices,
            "protection": {
                "rate_limiting": "active",
                "anti_spam": "active",
                "error_handling": "active",
                "blocked_users_tracking": "active",
                "instance_id": protection_info["instance_id"][:8],
                "bot_name": protection_info["bot_name"]
            },
            "database_stats": {
                "total_users": total_users,
                "total_orders": total_orders,
                "blocked_users": blocked_users_db
            },
            "api_config": {
                "mode": api_mode,
                "shipstation": "configured",
                "oxapay": "configured",
                "openai": "configured"
            }
        }
    except Exception as e:
        logger.error(f"Error getting bot health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bot/logs")
async def get_bot_logs(authenticated: bool = Depends(verify_admin_key), limit: int = 100):
    """Get recent bot logs"""
    try:
        import subprocess
        
        # Read last N lines from backend log
        result = subprocess.run(
            ["tail", "-n", str(limit), "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True
        )
        
        logs = result.stdout.split('\n')
        
        # Parse and categorize logs
        parsed_logs = []
        for log_line in logs:
            if not log_line.strip():
                continue
                
            log_entry = {
                "timestamp": "N/A",
                "level": "INFO",
                "message": log_line,
                "category": "general"
            }
            
            # Parse log level
            if "ERROR" in log_line:
                log_entry["level"] = "ERROR"
                log_entry["category"] = "error"
            elif "WARNING" in log_line:
                log_entry["level"] = "WARNING"
                log_entry["category"] = "warning"
            elif "INFO" in log_line:
                log_entry["level"] = "INFO"
            
            # Categorize by keywords
            if "SUSPICIOUS" in log_line:
                log_entry["category"] = "security"
            elif "rate limit" in log_line.lower():
                log_entry["category"] = "rate_limit"
            elif "blocked" in log_line.lower():
                log_entry["category"] = "blocked_user"
            elif "API" in log_line or "switched" in log_line:
                log_entry["category"] = "api"
            
            # Extract timestamp if available
            if log_line.startswith("2025-"):
                parts = log_line.split(" - ", 1)
                if len(parts) >= 1:
                    log_entry["timestamp"] = parts[0]
                    if len(parts) >= 2:
                        log_entry["message"] = parts[1]
            
            parsed_logs.append(log_entry)
        
        return {
            "logs": parsed_logs[-limit:],  # Return last N logs
            "total": len(parsed_logs),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting bot logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bot/metrics")
async def get_bot_metrics(authenticated: bool = Depends(verify_admin_key)):
    """Get bot performance metrics"""
    try:
        # Get order statistics
        total_orders = await db.orders.count_documents({})
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        orders_today = await db.orders.count_documents({
            "created_at": {"$gte": today_start.isoformat()}
        })
        
        # Get user statistics
        total_users = await db.users.count_documents({})
        active_users_today = await db.users.count_documents({
            "last_activity": {"$gte": today_start.isoformat()}
        })
        
        # Get revenue statistics
        pipeline = [
            {"$group": {
                "_id": None,
                "total_revenue": {"$sum": "$amount"},
                "avg_order": {"$avg": "$amount"}
            }}
        ]
        revenue_stats = await db.orders.aggregate(pipeline).to_list(1)
        
        total_revenue = revenue_stats[0]["total_revenue"] if revenue_stats else 0
        avg_order = revenue_stats[0]["avg_order"] if revenue_stats else 0
        
        return {
            "orders": {
                "total": total_orders,
                "today": orders_today,
                "avg_per_day": total_orders / max((datetime.now(timezone.utc) - today_start).days, 1)
            },
            "users": {
                "total": total_users,
                "active_today": active_users_today
            },
            "revenue": {
                "total": round(total_revenue, 2),
                "average_order": round(avg_order, 2)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting bot metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    authenticated: bool = Depends(verify_admin_key)
):
    """Upload image and return URL or file_id"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Check file size (max 10MB for Telegram)
        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size must be less than 10MB")
        
        # Save file temporarily
        upload_dir = Path("/tmp/broadcast_images")
        upload_dir.mkdir(exist_ok=True)
        
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        temp_filename = f"{uuid.uuid4()}.{file_extension}"
        temp_path = upload_dir / temp_filename
        
        with open(temp_path, 'wb') as f:
            f.write(contents)
        
        # Upload to Telegram to get file_id (if bot is available)
        if bot_instance:
            try:
                # Send photo to a test chat (admin) to get file_id
                if ADMIN_TELEGRAM_ID:
                    message = await safe_telegram_call(bot_instance.send_photo(
                        chat_id=int(ADMIN_TELEGRAM_ID),
                        photo=open(temp_path, 'rb'),
                        caption="Uploaded image for broadcast (you can delete this message)"
                    ))
                    file_id = message.photo[-1].file_id  # Get largest photo
                    
                    # Clean up temp file
                    os.remove(temp_path)
                    
                    return {
                        "success": True,
                        "file_id": file_id,
                        "message": "Image uploaded successfully"
                    }
            except Exception as e:
                logger.error(f"Failed to upload to Telegram: {e}")
                # Fall back to serving from disk
        
        # If Telegram upload failed, serve from disk
        static_url = f"/static/broadcast_images/{temp_filename}"
        
        return {
            "success": True,
            "url": static_url,
            "local_path": str(temp_path),
            "message": "Image saved locally"
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/{telegram_id}/check-bot-access")
async def check_bot_access(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Check if bot can send messages to user"""
    try:
        user = await find_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not bot_instance:
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        try:
            # Try to send a test message
            await bot_instance.send_chat_action(
                chat_id=telegram_id,
                action="typing"
            )
            
            # If successful, user hasn't blocked the bot
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {
                    "bot_blocked_by_user": False,
                    "bot_access_checked_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {
                "success": True,
                "bot_accessible": True,
                "message": "Bot can send messages to user"
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if user blocked the bot
            if "bot was blocked by the user" in error_msg.lower() or "forbidden" in error_msg.lower():
                logger.warning(f"User {telegram_id} has blocked the bot")
                
                await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {
                        "bot_blocked_by_user": True,
                        "bot_blocked_at": datetime.now(timezone.utc).isoformat(),
                        "bot_access_checked_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                return {
                    "success": True,
                    "bot_accessible": False,
                    "message": "Bot is blocked by user"
                }
            else:
                # Other error
                logger.error(f"Error checking bot access for user {telegram_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Error checking bot access: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking bot access: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/users/check-all-bot-access")
async def check_all_bot_access(authenticated: bool = Depends(verify_admin_key)):
    """Check bot access for all users"""
    try:
        if not bot_instance:
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        users = await db.users.find({}).to_list(None)
        
        checked_count = 0
        accessible_count = 0
        blocked_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # Try to send typing action (non-intrusive)
                await bot_instance.send_chat_action(
                    chat_id=user['telegram_id'],
                    action="typing"
                )
                
                # If successful, bot is accessible
                await db.users.update_one(
                    {"telegram_id": user['telegram_id']},
                    {"$set": {
                        "bot_blocked_by_user": False,
                        "bot_access_checked_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                checked_count += 1
                accessible_count += 1
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.02)
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if user blocked the bot
                if "bot was blocked by the user" in error_msg.lower() or "forbidden" in error_msg.lower():
                    logger.warning(f"User {user['telegram_id']} has blocked the bot")
                    
                    await db.users.update_one(
                        {"telegram_id": user['telegram_id']},
                        {"$set": {
                            "bot_blocked_by_user": True,
                            "bot_blocked_at": datetime.now(timezone.utc).isoformat(),
                            "bot_access_checked_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    
                    blocked_count += 1
                    checked_count += 1
                else:
                    # Other error
                    logger.error(f"Error checking bot access for user {user['telegram_id']}: {e}")
                    failed_count += 1
        
        return {
            "success": True,
            "message": f"Checked {checked_count} users: {accessible_count} accessible, {blocked_count} blocked",
            "checked_count": checked_count,
            "accessible_count": accessible_count,
            "blocked_count": blocked_count,
            "failed_count": failed_count
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking all bot access: {e}")
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


@api_router.get("/users/{telegram_id}/channel-status")
async def check_user_channel_status(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Check if user is a member of the channel"""
    try:
        if not CHANNEL_ID:
            raise HTTPException(status_code=500, detail="Channel ID not configured")
        
        if not bot_instance:
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        user = await find_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            # Check user status in channel
            chat_member = await bot_instance.get_chat_member(
                chat_id=int(CHANNEL_ID),
                user_id=telegram_id
            )
            
            # Member statuses: "creator", "administrator", "member", "restricted", "left", "kicked"
            is_member = chat_member.status in ["creator", "administrator", "member", "restricted"]
            
            # Update user record
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {
                    "is_channel_member": is_member,
                    "channel_status_checked_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {
                "success": True,
                "is_member": is_member,
                "status": chat_member.status
            }
            
        except Exception as e:
            # User probably left or was never in channel
            logger.error(f"Failed to check channel status for user {telegram_id}: {e}")
            
            # Update as not member
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {
                    "is_channel_member": False,
                    "channel_status_checked_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {
                "success": True,
                "is_member": False,
                "status": "not_found",
                "error": str(e)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking channel status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/users/check-all-channel-status")
async def check_all_users_channel_status(authenticated: bool = Depends(verify_admin_key)):
    """Check channel membership status for all users"""
    try:
        if not CHANNEL_ID:
            raise HTTPException(status_code=500, detail="Channel ID not configured")
        
        if not bot_instance:
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        users = await db.users.find({}).to_list(None)
        
        checked_count = 0
        member_count = 0
        failed_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 5  # Stop if 5 errors in a row (may indicate blocking)
        
        for user in users:
            # Stop if too many consecutive errors (channel may be blocking us)
            if consecutive_errors >= max_consecutive_errors:
                logger.warning(f"Stopped checking after {consecutive_errors} consecutive errors - possible rate limiting")
                break
            
            try:
                chat_member = await bot_instance.get_chat_member(
                    chat_id=int(CHANNEL_ID),
                    user_id=user['telegram_id']
                )
                
                is_member = chat_member.status in ["creator", "administrator", "member", "restricted"]
                
                await db.users.update_one(
                    {"telegram_id": user['telegram_id']},
                    {"$set": {
                        "is_channel_member": is_member,
                        "channel_status_checked_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                checked_count += 1
                if is_member:
                    member_count += 1
                
                # Reset consecutive errors on success
                consecutive_errors = 0
                
                # Delay to avoid rate limiting and channel blocking
                # Telegram allows ~30 requests per second per user
                await asyncio.sleep(0.1)  # Increased from 0.02 to 0.1 (10 checks/sec)
                
            except Exception as e:
                logger.error(f"Failed to check status for user {user['telegram_id']}: {e}")
                consecutive_errors += 1
                failed_count += 1
                
                # Mark as not member (don't block functionality)
                await db.users.update_one(
                    {"telegram_id": user['telegram_id']},
                    {"$set": {
                        "is_channel_member": False,
                        "channel_status_checked_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                # Longer delay after error
                await asyncio.sleep(0.5)
        
        return {
            "success": True,
            "message": f"Checked {checked_count} users",
            "checked_count": checked_count,
            "member_count": member_count,
            "failed_count": failed_count
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking all channel statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/users/{telegram_id}/balance/add")
async def add_balance(telegram_id: int, amount: float):
    try:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        # Use payment service
        success, new_balance, error = await payment_service.add_balance(
            telegram_id=telegram_id,
            amount=amount,
            db=db,
            find_user_func=find_user_by_telegram_id
        )
        
        if not success:
            if error == "User not found":
                raise HTTPException(status_code=404, detail=error)
            raise HTTPException(status_code=500, detail=error)
        
        # Notify user via Telegram
        if bot_instance:
            await safe_telegram_call(bot_instance.send_message(
                chat_id=telegram_id,
                text=f"""💰 Баланс пополнен администратором!

Зачислено: ${amount:.2f}
Новый баланс: ${new_balance:.2f}"""
            ))
        
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
        
        # Use payment service
        success, new_balance, error = await payment_service.deduct_balance(
            telegram_id=telegram_id,
            amount=amount,
            db=db,
            find_user_func=find_user_by_telegram_id
        )
        
        if not success:
            if error == "User not found":
                raise HTTPException(status_code=404, detail=error)
            elif error == "Insufficient balance":
                raise HTTPException(status_code=400, detail=error)
            raise HTTPException(status_code=500, detail=error)
        
        # Notify user via Telegram
        if bot_instance:
            await safe_telegram_call(bot_instance.send_message(
                chat_id=telegram_id,
                text=f"""⚠️ Баланс изменен администратором!

Списано: ${amount:.2f}
Новый баланс: ${new_balance:.2f}"""
            ))
        
        return {"success": True, "new_balance": new_balance, "deducted": amount}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/users/{telegram_id}/discount")
async def set_user_discount(telegram_id: int, discount: float):
    """
    Set discount percentage for a user (e.g., 10 for 10% discount)
    """
    try:
        if discount < 0 or discount > 100:
            raise HTTPException(status_code=400, detail="Discount must be between 0 and 100")
        
        user = await find_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update discount
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"discount": discount}}
        )
        
        # Notify user if bot is available and discount is set
        if bot_instance and discount > 0:
            try:
                keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=telegram_id,
                    text=f"""🎉 Поздравляем!

Вам предоставлена скидка {discount}% на все заказы!

Скидка будет автоматически применена при создании следующих заказов.""",
                    reply_markup=reply_markup
                ))
            except Exception as e:
                logger.error(f"Failed to notify user about discount: {e}")
        
        return {"success": True, "telegram_id": telegram_id, "discount": discount}
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
        
        # Get carrier accounts (async)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                'https://api.shipstation.com/v2/carriers',
                headers=headers
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
                        'length': parcel.get('length', 10),
                        'width': parcel.get('width', 10),
                        'height': parcel.get('height', 10),
                        'unit': 'inch'
                    }
                }]
            }
        }
        
        try:
            # Async HTTP call with timeout protection
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await asyncio.wait_for(
                    client.post(
                        'https://api.shipstation.com/v2/rates',
                        headers=headers,
                        json=rate_request
                    ),
                    timeout=35  # Overall timeout
                )
        except asyncio.TimeoutError:
            logger.error("ShipStation rate request timed out after 35 seconds (API endpoint)")
            raise HTTPException(status_code=504, detail="ShipStation API timeout. Please try again.")
        except httpx.TimeoutException:
            logger.error("httpx timeout during rate request")
            raise HTTPException(status_code=504, detail="ShipStation API timeout. Please try again.")
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('message', f'Status code: {response.status_code}')
            raise HTTPException(status_code=400, detail=f"Failed to get rates: {error_msg}")
        
        rate_response = response.json()
        all_rates = rate_response.get('rate_response', {}).get('rates', [])
        
        # Filter out only GlobalPost rates (keep stamps_com which is USPS)
        excluded_carriers = ['globalpost']
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
            ],
            'stamps_com': [
                'usps_ground_advantage',
                'usps_priority_mail',
                'usps_priority_mail_express',
                'usps_first_class_mail',
                'usps_media_mail'
            ],
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
async def get_stats(authenticated: bool = Depends(verify_admin_key)):
    total_users = await db.users.count_documents({})
    total_orders = await db.orders.count_documents({})
    paid_orders = await db.orders.count_documents({"payment_status": "paid"})
    
    # Calculate total revenue
    total_revenue = await db.orders.aggregate([
        {"$match": {"payment_status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    
    revenue = total_revenue[0]['total'] if total_revenue else 0
    
    # Calculate profit: $10 per created label
    total_labels = await db.shipping_labels.count_documents({"status": "created"})
    total_profit = total_labels * 10.0
    
    # Calculate total user balance (sum of all user balances)
    total_user_balance = await db.users.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]).to_list(1)
    
    user_balance_sum = total_user_balance[0]['total'] if total_user_balance else 0
    
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "total_revenue": revenue,
        "total_profit": total_profit,
        "total_labels": total_labels,
        "total_user_balance": user_balance_sum
    }

@api_router.get("/stats/expenses")
async def get_expense_stats(date_from: Optional[str] = None, date_to: Optional[str] = None):
    """
    Get expenses statistics (money spent on ShipStation labels)
    """
    try:
        # Build query for paid orders with labels
        query = {"payment_status": "paid"}
        
        # Add date filter if provided
        if date_from or date_to:
            date_query = {}
            if date_from:
                date_query["$gte"] = date_from
            if date_to:
                # Add one day to include the end date
                end_date = datetime.fromisoformat(date_to) + timedelta(days=1)
                date_query["$lt"] = end_date.isoformat()
            query["created_at"] = date_query
        
        # Get all paid orders with original_amount (real cost from ShipStation)
        total_spent = await db.orders.aggregate([
            {"$match": query},
            {"$match": {"original_amount": {"$exists": True}}},
            {"$group": {"_id": None, "total": {"$sum": "$original_amount"}}}
        ]).to_list(1)
        
        total_expense = total_spent[0]['total'] if total_spent else 0
        
        # Get count of labels created (without refunded)
        labels_query = {"status": "created"}
        if date_from or date_to:
            date_query = {}
            if date_from:
                date_query["$gte"] = date_from
            if date_to:
                end_date = datetime.fromisoformat(date_to) + timedelta(days=1)
                date_query["$lt"] = end_date.isoformat()
            labels_query["created_at"] = date_query
        
        labels_count = await db.shipping_labels.count_documents(labels_query)
        
        # Get today's expenses
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_query = {
            "payment_status": "paid",
            "original_amount": {"$exists": True},
            "created_at": {"$gte": today_start.isoformat()}
        }
        
        today_spent = await db.orders.aggregate([
            {"$match": today_query},
            {"$group": {"_id": None, "total": {"$sum": "$original_amount"}}}
        ]).to_list(1)
        
        today_expense = today_spent[0]['total'] if today_spent else 0
        
        # Get today's label count
        today_labels = await db.shipping_labels.count_documents({
            "status": "created",
            "created_at": {"$gte": today_start.isoformat()}
        })
        
        return {
            "total_expense": total_expense,
            "labels_count": labels_count,
            "today_expense": today_expense,
            "today_labels": today_labels,
            "date_from": date_from,
            "date_to": date_to
        }
    except Exception as e:
        logger.error(f"Error getting expense stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/topups")
async def get_topups(authenticated: bool = Depends(verify_admin_key)):
    """
    Get all balance top-ups history with user information
    """
    try:
        # Get all top-up payments
        topups = await db.payments.find({"type": "topup"}).sort("created_at", -1).to_list(1000)
        
        # Enrich with user information
        enriched_topups = []
        for topup in topups:
            telegram_id = topup.get('telegram_id')
            if telegram_id:
                user = await find_user_by_telegram_id(telegram_id)
                if user:
                    enriched_topups.append({
                        "id": topup.get('id'),
                        "telegram_id": telegram_id,
                        "first_name": user.get('first_name'),
                        "username": user.get('username'),
                        "amount": topup.get('amount'),
                        "status": topup.get('status'),
                        "invoice_id": topup.get('invoice_id'),
                        "created_at": topup.get('created_at')
                    })
        
        return enriched_topups
    except Exception as e:
        logger.error(f"Error getting topups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(api_router)

# Include admin routers (v1 and v2)
from routers.admin_router import admin_router  # Legacy
from routers.admin import admin_router_v2  # New modular
app.include_router(admin_router)  # Keep for backward compatibility
app.include_router(admin_router_v2)  # New modular admin API

# Include monitoring routers
from api.monitoring import router as monitoring_router_old
from routers.monitoring_router import router as monitoring_router
app.include_router(monitoring_router_old)  # Legacy /api/monitoring
app.include_router(monitoring_router)  # New /monitoring

# Include bot configuration router
from routers.bot_config_router import router as bot_config_router
app.include_router(bot_config_router, prefix="/api")  # /api/bot-config

# Include API configuration router
from routers.api_config_router import router as api_config_router
app.include_router(api_config_router, prefix="/api")  # /api/api-config

# Include alerting router
from api.alerting import router as alerting_router
app.include_router(alerting_router)

# Direct endpoint for clearing conversations (easier access)
@app.get("/clear-conversations")
async def clear_conversations_direct(admin_verified: bool = Depends(verify_admin_key)):
    """Clear all stuck conversation states - Admin only"""
    try:
        result = await db.bot_persistence.delete_many({"_id": {"$regex": "^conversation_"}})
        return {
            "success": True,
            "deleted": result.deleted_count,
            "message": f"Cleared {result.deleted_count} conversation states"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/performance/stats")
async def get_performance_statistics(admin_verified: bool = Depends(verify_admin_key)):
    """
    Get performance statistics - Admin only
    Useful for monitoring and identifying bottlenecks
    """
    try:
        from utils.performance import get_performance_stats
        stats = get_performance_stats()
        return {
            "success": True,
            "stats": stats,
            "threshold_ms": 100,
            "message": "Performance statistics retrieved"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==================== MIDDLEWARE SETUP ====================
# Order matters: SecurityMiddleware first for rate limiting & security headers
app.add_middleware(SecurityMiddleware)

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
    
    # Инициализация мониторинга
    from utils.monitoring import init_sentry
    init_sentry()
    
    # V2: TTL index автоматически очищает сессии старше 15 минут
    # Периодическая очистка больше не нужна
    logger.info("✅ Session cleanup: TTL index (automatic, no manual cleanup needed)")
    
    # ============================================================
    # API Configuration Setup (Refactored)
    # ============================================================
    global SHIPSTATION_API_KEY, api_config_manager
    try:
        # Определить окружение из БД
        api_mode_setting = await db.settings.find_one({"key": "api_mode"})
        api_mode = api_mode_setting.get("value", "production") if api_mode_setting else "production"
        
        # Установить окружение в APIConfigManager
        api_config_manager.set_environment(api_mode)
        
        # Обновить legacy переменную для обратной совместимости
        SHIPSTATION_API_KEY = api_config_manager.get_shipstation_key()
        
        # Логирование
        env_icon = "🧪" if api_mode == "test" else "🚀"
        logger.info(f"{env_icon} API Environment: {api_mode.upper()}")
        logger.info(f"   ShipStation: {api_config_manager._mask_key(SHIPSTATION_API_KEY)}")
        logger.info(f"   Oxapay: {'✅ Configured' if api_config_manager.is_oxapay_configured() else '❌ Not configured'}")
        logger.info(f"   CryptoBot: {'✅ Configured' if api_config_manager.is_cryptobot_configured() else '❌ Not configured'}")
        
        logger.info(f"✅ ShipStation API mode: {api_mode.upper()}")
        
        # Note: Balance check removed from startup to avoid unnecessary API calls
        # Balance is checked after each label creation (in create_and_send_label)
        
    except Exception as e:
        logger.error(f"Error loading API mode from database: {e}")
        logger.info("Using default API key from .env file")
    
    # Initialize Bot Protection System
    global bot_protection, telegram_safety
    bot_protection = BotProtection(
        owner_telegram_id=int(ADMIN_TELEGRAM_ID) if ADMIN_TELEGRAM_ID else 0,
        bot_name="WhiteLabelShippingBot"
    )
    instance_info = bot_protection.get_instance_info()
    logger.info(f"🔒 Bot Protection System initialized: {instance_info}")
    
    # Initialize Telegram Safety System
    telegram_safety = TelegramSafetySystem()
    logger.info("🛡️ Telegram Safety System initialized (Rate Limiting, Anti-Block)")
    logger.info(f"📋 Best Practices: {len(TelegramBestPractices.get_guidelines())} guidelines active")
    
    # Create MongoDB indexes for performance optimization (5000+ users)
    try:
        logger.info("Creating MongoDB indexes for high performance...")
        await db.users.create_index("telegram_id", unique=True)
        await db.users.create_index([("created_at", -1)])
        await db.orders.create_index("telegram_id")
        await db.orders.create_index([("created_at", -1)])
        await db.orders.create_index("order_id", unique=True)
        await db.templates.create_index([("telegram_id", 1), ("created_at", -1)])
        await db.settings.create_index("key", unique=True)
        logger.info("✅ MongoDB indexes created successfully")
    except Exception as e:
        logger.warning(f"Index creation skipped (may already exist): {e}")
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "your_telegram_bot_token_here":
        try:
            global application  # Use global application variable for webhook access
            logger.info("Initializing Telegram Bot...")
            # Build application - using in-memory state (STABLE)
            
            application = (
                Application.builder()
                .token(TELEGRAM_BOT_TOKEN)
                # NO PERSISTENCE - in-memory state for stability
                .concurrent_updates(True)  # Process updates concurrently
                .connect_timeout(10)  # Balanced: fast but stable
                .read_timeout(10)   # Prevents premature timeout
                .write_timeout(10)  # Reliable message delivery
                .pool_timeout(5)    # Connection pool optimization
                .pool_timeout(1)  # Super fast pool acquisition
                # Keep default rate limiter to prevent Telegram ban
                .build()
            )
            
            # Conversation handler for order creation
            # Template rename conversation handler
            template_rename_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(rename_template_start, pattern='^template_rename_')
                ],
                states={
                    TEMPLATE_RENAME: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, rename_template_save)
                    ]
                },
                fallbacks=[
                    CallbackQueryHandler(my_templates_menu, pattern='^my_templates$'),
                    CommandHandler('start', start_command)
                ],
                per_chat=True,
                per_user=True,
                per_message=False,  # False is correct: we use MessageHandler (not only CallbackQueryHandler)
                allow_reentry=True
            )
            
            # Import order conversation handler from modular setup
            from handlers.order_flow.conversation_setup import setup_order_conversation_handler
            order_conv_handler = setup_order_conversation_handler()
            
            # Old conversation handler definition replaced with modular setup above
            # order_conv_handler = ConversationHandler(
            #     entry_points=[
            #         CallbackQueryHandler(new_order_start, pattern='^new_order$'),
            #         CallbackQueryHandler(start_order_with_template, pattern='^start_order_with_template$'),
            #         CallbackQueryHandler(return_to_payment_after_topup, pattern='^return_to_payment$')
            #     ],
            #     states={
            #         FROM_NAME: [
            #             MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_name),
            #             CallbackQueryHandler(order_new, pattern='^order_new$'),
            #             CallbackQueryHandler(order_from_template_list, pattern='^order_from_template$'),
            #             CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
            #             CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
            #         ],
#         FROM_ADDRESS: [
#             MessageHandler(filters.TEXT & ~filters.COMMAND, order_from_address),
#             CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
#             CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
#         ],
#         ... (rest of states commented out - see conversation_setup.py)
#     },
#     fallbacks=[
#         CallbackQueryHandler(cancel_order, pattern='^cancel_order$'),
#         CommandHandler('start', start_command)
#     ],
#     per_chat=True,
#     per_user=True,
#     per_message=False,
#     allow_reentry=True
# )
            
            application.add_handler(template_rename_handler)
            application.add_handler(order_conv_handler)
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("test_error", test_error_message))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CommandHandler("balance", my_balance_command))
            
            # Template handlers (must be before generic button_callback)
            application.add_handler(CallbackQueryHandler(view_template, pattern='^template_view_'))
            application.add_handler(CallbackQueryHandler(use_template, pattern='^template_use_'))
            application.add_handler(CallbackQueryHandler(delete_template, pattern='^template_delete_'))
            application.add_handler(CallbackQueryHandler(confirm_delete_template, pattern='^template_confirm_delete_'))
            # rename_template_start is now handled by template_rename_handler ConversationHandler
            application.add_handler(CallbackQueryHandler(my_templates_menu, pattern='^my_templates$'))
            application.add_handler(CallbackQueryHandler(order_from_template_list, pattern='^order_from_template$'))
            
            # Handler for topup amount input (text messages) - only when not in conversation
            # This handler should NOT interfere with ConversationHandler
            # Removed to fix message processing issue - topup is handled in ConversationHandler
            # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topup_amount_input))
            application.add_handler(CallbackQueryHandler(button_callback))
            
            
            # Global error handler for catching all exceptions
            async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                """Log all errors"""
                logger.error(f"🔥 GLOBAL ERROR HANDLER CAUGHT: {context.error}")
                logger.error(f"Update: {update}")
                logger.error("Traceback:", exc_info=context.error)
                
                # Try to send error message to user
                try:
                    if isinstance(update, Update) and update.effective_message:
                        await safe_telegram_call(update.effective_message.reply_text(
                            "❌ Произошла ошибка. Пожалуйста, попробуйте снова или используйте /start"
                        ))
                except Exception as e:
                    logger.error(f"Failed to send error message to user: {e}")
            
            application.add_error_handler(global_error_handler)

            await application.initialize()
            await application.start()
            
            # Set bot commands for menu button
            commands = [
                BotCommand("start", "🏠 Главное меню"),
                BotCommand("balance", "💰 Мой баланс"),
                BotCommand("help", "❓ Помощь")
            ]
            await application.bot.set_my_commands(commands)
            
            # Set menu button in header (next to attachment icon)
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonCommands()
            )
            
            # ============================================================
            # BOT START: Webhook or Polling (Refactored)
            # ============================================================
            # Используем новую систему конфигурации
            use_webhook = is_webhook_mode()
            webhook_url = bot_config.get_webhook_url() if use_webhook else None
            
            env_icon = "🟢" if is_production_environment() else "🔵"
            mode_icon = "🌐" if use_webhook else "🔄"
            
            logger.info(f"{env_icon} Starting Telegram Bot:")
            logger.info(f"   Environment: {bot_config.environment.upper()}")
            logger.info(f"   Mode: {mode_icon} {bot_config.mode.upper()}")
            logger.info(f"   Bot: @{get_bot_username()}")
            
            if use_webhook and webhook_url:
                # Webhook mode
                logger.info(f"🌐 WEBHOOK MODE: {webhook_url}")
                
                # Удалить старый webhook перед установкой нового
                await application.bot.delete_webhook(drop_pending_updates=True)
                
                # Установить новый webhook
                await application.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=False
                )
                
                logger.info(f"✅ Webhook set successfully: {webhook_url}")
                
            else:
                # Polling mode
                logger.info(f"🔄 POLLING MODE")
                
                # Убедиться что webhook отключен
                try:
                    await application.bot.delete_webhook(drop_pending_updates=True)
                    logger.info("   Webhook disabled")
                except Exception as e:
                    logger.debug(f"   Webhook delete skipped: {e}")
                
                # Запустить polling
                await application.updater.start_polling(
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=False
                )
                
                logger.info("✅ Polling started successfully")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}")
            logger.warning("Application will continue without Telegram Bot")
    else:
        logger.warning("Telegram Bot Token not configured. Bot features will be disabled.")
        logger.info("To enable Telegram Bot, add TELEGRAM_BOT_TOKEN to backend/.env")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()