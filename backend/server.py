from fastapi import FastAPI, APIRouter, HTTPException, Request, Header, Header, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from bot_protection import BotProtection, get_copyright_footer, PROTECTED_BADGE, VERSION_WATERMARK
from telegram_safety import TelegramSafetySystem, TelegramBestPractices
import os
import logging
import random
import requests
import httpx
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import time
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import asyncio
import hashlib
import hmac

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

# In-memory cache for frequently accessed data
from functools import lru_cache
import asyncio

user_balance_cache = {}  # Cache user balances
cache_ttl = 60  # Cache TTL in seconds

# ShipStation API
SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY', '')
SHIPSTATION_CARRIER_IDS = []  # Cache for carrier IDs

# Admin API Key for protecting endpoints
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', '')

# Admin notifications
ADMIN_TELEGRAM_ID = os.environ.get('ADMIN_TELEGRAM_ID', '')

# Channel invite link and ID
CHANNEL_INVITE_LINK = os.environ.get('CHANNEL_INVITE_LINK', '')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '')

# Telegram Bot - Auto-select token based on environment
# Detect environment from WEBHOOK_BASE_URL
webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
is_production_env = 'crypto-shipping.emergent.host' in webhook_base_url

# Choose correct token
if is_production_env:
    # Production: use production bot @whitelabel_shipping_bot
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN_PRODUCTION', '')
    print(f"🟢 PRODUCTION BOT SELECTED: @whitelabel_shipping_bot")
else:
    # Preview: use preview bot @whitelabel_shipping_bot_test_bot
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN_PREVIEW', 
                                       os.environ.get('TELEGRAM_BOT_TOKEN', ''))
    print(f"🔵 PREVIEW BOT SELECTED: @whitelabel_shipping_bot_test_bot")

bot_instance = None
application = None  # Global Telegram Application instance for webhook
if TELEGRAM_BOT_TOKEN:
    bot_instance = Bot(token=TELEGRAM_BOT_TOKEN)

# Simple in-memory cache for frequently accessed settings
SETTINGS_CACHE = {
    'api_mode': None,
    'api_mode_timestamp': None,
    'maintenance_mode': None,
    'maintenance_timestamp': None
}
CACHE_TTL = 60  # Cache TTL in seconds


# Button click debouncing - prevent multiple rapid clicks
button_click_tracker = {}  # {user_id: {button_data: last_click_timestamp}}
BUTTON_DEBOUNCE_SECONDS = 0.5  # Минимальное время между нажатиями одной кнопки (500ms)

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

# Oxapay helper functions
async def create_oxapay_invoice(amount: float, order_id: str, description: str = "Shipping Label Payment"):
    """Create payment invoice via Oxapay"""
    if not OXAPAY_API_KEY:
        raise HTTPException(status_code=500, detail="Oxapay API key not configured")
    
    try:
        # Prepare headers with API key
        headers = {
            "merchant_api_key": OXAPAY_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Prepare payload according to official documentation
        payload = {
            "amount": amount,
            "currency": "USD",
            "lifeTime": 30,  # 30 minutes
            "fee_paid_by_payer": 0,  # Merchant pays fees
            "under_paid_coverage": 2,  # Accept 2% underpayment
            "callback_url": f"{os.environ.get('WEBHOOK_BASE_URL', 'https://telebot-fix-2.preview.emergentagent.com')}/api/oxapay/webhook",
            "return_url": f"https://t.me/{os.environ.get('BOT_USERNAME', '')}",
            "description": description,
            "order_id": order_id
        }
        
        response = await asyncio.to_thread(
            requests.post,
            f"{OXAPAY_API_URL}/v1/payment/invoice",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Check for new API format (status 200 with data object)
            if data.get('status') == 200 and 'data' in data:
                invoice_data = data.get('data', {})
                return {
                    'trackId': invoice_data.get('track_id'),
                    'payLink': invoice_data.get('payment_url'),
                    'success': True
                }
            # Check for old API format (result code 100)
            elif data.get('result') == 100:
                return {
                    'trackId': data.get('trackId'),
                    'payLink': data.get('payLink'),
                    'success': True
                }
        
        logger.error(f"Oxapay invoice creation failed: {response.text}")
        return {'success': False, 'error': response.text}
        
    except Exception as e:
        logger.error(f"Oxapay error: {e}")
        return {'success': False, 'error': str(e)}

async def check_oxapay_payment(track_id: str):
    """Check payment status via Oxapay"""
    try:
        # Prepare headers with API key
        headers = {
            "merchant_api_key": OXAPAY_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "trackId": track_id
        }
        
        response = await asyncio.to_thread(
            requests.post,
            f"{OXAPAY_API_URL}/v1/payment/info",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data
        
        return None
        
    except Exception as e:
        logger.error(f"Oxapay inquiry error: {e}")
        return None

def generate_random_phone():
    """Generate a random valid US phone number"""
    # Generate random US phone number in format +1XXXXXXXXXX
    area_code = random.randint(200, 999)  # Valid area codes start from 200
    exchange = random.randint(200, 999)   # Valid exchanges start from 200
    number = random.randint(1000, 9999)   # Last 4 digits
    return f"+1{area_code}{exchange}{number}"

async def get_api_mode_cached():
    """Get API mode with caching to reduce DB queries"""
    from time import time
    
    current_time = time()
    
    # Check if cache is valid
    if (SETTINGS_CACHE['api_mode'] is not None and 
        SETTINGS_CACHE['api_mode_timestamp'] is not None and
        current_time - SETTINGS_CACHE['api_mode_timestamp'] < CACHE_TTL):
        return SETTINGS_CACHE['api_mode']
    
    # Cache miss or expired - fetch from DB
    try:
        setting = await db.settings.find_one({"key": "api_mode"})
        api_mode = setting.get("value", "production") if setting else "production"
        
        # Update cache
        SETTINGS_CACHE['api_mode'] = api_mode
        SETTINGS_CACHE['api_mode_timestamp'] = current_time
        
        return api_mode
    except Exception as e:
        logger.error(f"Error fetching api_mode: {e}")
        return SETTINGS_CACHE['api_mode'] or "production"

def clear_settings_cache():
    """Clear settings cache when settings are updated"""
    SETTINGS_CACHE['api_mode'] = None
    SETTINGS_CACHE['api_mode_timestamp'] = None
    SETTINGS_CACHE['maintenance_mode'] = None
    SETTINGS_CACHE['maintenance_timestamp'] = None

async def check_shipstation_balance():
    """Check ShipStation carrier balances and notify admin if any balance is below $50"""
    try:
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Get all carriers
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.shipstation.com/v2/carriers",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                carriers_data = response.json()
                
                low_balance_carriers = []
                for carrier in carriers_data.get('carriers', []):
                    # Check if carrier requires funded account and has low balance
                    if carrier.get('requires_funded_account', False):
                        balance = float(carrier.get('balance', 0))
                        carrier_name = carrier.get('friendly_name', carrier.get('name', 'Unknown'))
                        
                        logger.info(f"Carrier {carrier_name} balance: ${balance:.2f}")
                        
                        if balance < 50.0:
                            low_balance_carriers.append({
                                'name': carrier_name,
                                'balance': balance
                            })
                
                # Notify admin if any carrier has low balance
                if low_balance_carriers and ADMIN_TELEGRAM_ID:
                    message = "⚠️ *Внимание! Низкий баланс в ShipStation*\n\n"
                    for carrier in low_balance_carriers:
                        message += f"📦 *{carrier['name']}*: ${carrier['balance']:.2f}\n"
                    message += "\n💰 *Необходимо пополнить баланс для продолжения создания лейблов*"
                    
                    # Send notification to admin
                    try:
                        # Get global bot instance or create new one
                        if 'application' in globals() and hasattr(application, 'bot'):
                            bot_instance = application.bot
                        else:
                            # Import here to avoid circular imports
                            from telegram import Bot
                            bot_instance = Bot(TELEGRAM_BOT_TOKEN)
                        
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=ADMIN_TELEGRAM_ID,
                            text=message,
                            parse_mode='Markdown'
                        ))
                        logger.info(f"Low balance notification sent to admin {ADMIN_TELEGRAM_ID}")
                    except Exception as e:
                        logger.error(f"Failed to send low balance notification: {e}")
                        
                return low_balance_carriers
            else:
                logger.error(f"Failed to check ShipStation balance: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Error checking ShipStation balance: {e}")
        return None

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

def sanitize_address(address: str) -> str:
    """Sanitize address fields"""
    if not address:
        return ""
    # Allow letters, numbers, spaces, common punctuation, & symbol
    sanitized = re.sub(r'[^a-zA-Z0-9\s\.,\-#&/]', '', address)
    return sanitized[:200].strip()

def sanitize_phone(phone: str) -> str:
    """Sanitize phone number"""
    if not phone:
        return ""
    # Allow only digits, +, -, (, ), spaces
    sanitized = re.sub(r'[^\d\+\-\(\)\s]', '', phone)
    return sanitized[:20].strip()

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
from fastapi import Header, HTTPException

async def verify_admin_key(x_api_key: Optional[str] = Header(None)):
    """Verify admin API key for protected endpoints"""
    if not ADMIN_API_KEY:
        # If no admin key is set, allow access (for development)
        logging.warning("ADMIN_API_KEY not set - admin endpoints are unprotected!")
        return True
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    if x_api_key != ADMIN_API_KEY:
        # Log failed authentication
        await SecurityLogger.log_action(
            "admin_auth_failed",
            None,
            {"provided_key": x_api_key[:10] + "..."},
            "failure"
        )
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return True

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
async def check_user_blocked(telegram_id: int) -> bool:
    """Check if user is blocked"""
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0, "blocked": 1})
    return user.get('blocked', False) if user else False

async def send_blocked_message(update: Update):
    """Send blocked message to user"""
    message = """⛔️ *Вы заблокированы*

Ваш доступ к боту был ограничен администратором.

Для получения дополнительной информации, пожалуйста, свяжитесь с администратором."""
    
    if update.message:
        await safe_telegram_call(update.message.reply_text(message, parse_mode='Markdown'))
    elif update.callback_query:
        await safe_telegram_call(update.callback_query.message.reply_text(message, parse_mode='Markdown'))

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

def mark_message_as_selected_nonblocking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Non-blocking wrapper for mark_message_as_selected"""
    asyncio.create_task(mark_message_as_selected(update, context))

async def safe_telegram_call(coro, timeout=10, error_message="❌ Превышено время ожидания. Попробуйте еще раз."):
    """
    Universal wrapper for all Telegram API calls with timeout protection
    Prevents bot from hanging on any Telegram API operation
    
    Usage:
        await safe_telegram_call(update.message.reply_text("Hello"))
        await safe_telegram_call(context.bot.send_message(...), timeout=15)
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Telegram API timeout after {timeout}s")
        return None  # Return None on timeout
    except Exception as e:
        logger.error(f"Telegram API error: {e}")
        return None

async def mark_message_as_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Add checkmark ✅ to selected message and remove buttons
    Runs async - doesn't block bot response
    """
    try:
        # Handle callback query (button press)
        if update.callback_query:
            message = update.callback_query.message
            try:
                # Get current text and add checkmark if not already there
                current_text = message.text or ""
                if not current_text.startswith("✅"):
                    new_text = f"✅ {current_text}"
                    # Edit message with checkmark and remove buttons
                    await message.edit_text(text=new_text, reply_markup=None)
                else:
                    # Just remove buttons if checkmark already exists
                    await message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return
        
        # Handle text input messages
        if update.message and 'last_bot_message_id' in context.user_data:
            last_msg_id = context.user_data.get('last_bot_message_id')
            last_text = context.user_data.get('last_bot_message_text', '')
            
            if not last_msg_id:
                return
            
            try:
                # Add checkmark to last bot message
                if not last_text.startswith("✅"):
                    new_text = f"✅ {last_text}"
                    await safe_telegram_call(context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=last_msg_id,
                        text=new_text,
                        reply_markup=None
                    ))
                else:
                    # Just remove buttons if checkmark already exists
                    await safe_telegram_call(context.bot.edit_message_reply_markup(
                        chat_id=update.effective_chat.id,
                        message_id=last_msg_id,
                        reply_markup=None
                    ))
            except Exception:
                pass
        
    except Exception:
        pass

async def check_maintenance_mode(update: Update) -> bool:
    """Check if bot is in maintenance mode and user is not admin"""
    try:
        settings = await db.settings.find_one({"key": "maintenance_mode"})
        is_maintenance = settings.get("value", False) if settings else False
        
        # Allow admin to use bot even in maintenance mode
        if is_maintenance and str(update.effective_user.id) != ADMIN_TELEGRAM_ID:
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking maintenance mode: {e}")
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        
        telegram_id = query.from_user.id
        username = query.from_user.username
        first_name = query.from_user.first_name
        send_method = query.message.reply_text
    else:
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        send_method = update.message.reply_text
    
    # Check if bot is in maintenance mode
    if await check_maintenance_mode(update):
        await send_method(
            "🔧 *Бот находится на техническом обслуживании.*\n\n"
            "Пожалуйста, попробуйте позже.\n\n"
            "Приносим извинения за неудобства.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Check if user is blocked
    if await check_user_blocked(telegram_id):
        await send_blocked_message(update)
        return ConversationHandler.END
    
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
        user_balance = 0.0
    else:
        user_balance = existing_user.get('balance', 0.0)
        
    welcome_message = f"""*Добро пожаловать, {first_name}! 🚀*

*Я помогу вам создать shipping labels.*

*Выберите действие:*"""
    
    # Create keyboard with buttons
    keyboard = [
        [
            InlineKeyboardButton("📦 Создать заказ", callback_data='new_order')
        ],
        [
            InlineKeyboardButton(f"💳 Мой баланс (${user_balance:.2f})", callback_data='my_balance')
        ],
        [
            InlineKeyboardButton("📋 Мои шаблоны", callback_data='my_templates')
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data='help')
        ],
        [
            InlineKeyboardButton("📖 FAQ", callback_data='faq')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send welcome message with inline keyboard
    bot_msg = await send_method(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Save last bot message context for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = welcome_message

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    help_text = """


*Если у вас возникли вопросы или проблемы, нажмите кнопку ниже:*


"""
    
    keyboard = []
    # Add contact administrator button if ADMIN_TELEGRAM_ID is configured
    if ADMIN_TELEGRAM_ID:
        keyboard.append([InlineKeyboardButton("💬 Связаться с администратором", url=f"tg://user?id={ADMIN_TELEGRAM_ID}")])
    # Add main menu button on separate row at the bottom
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='start')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot_msg = await send_method(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Save message ID and text for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = help_text


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both command and callback
    if update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        # Mark previous message as selected (remove buttons and add "✅ Выбрано")
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = query.message.reply_text
    else:
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        send_method = update.message.reply_text
    
    faq_text = """📦 *White Label Shipping Bot*

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
    
    keyboard = [
        [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot_msg = await send_method(faq_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Save message ID and text for button protection
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = faq_text



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
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"payment_status": "paid"}}
        )
        
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    if query.data == 'start' or query.data == 'main_menu':
        # Check if user has pending order
        telegram_id = query.from_user.id
        pending_order = await db.pending_orders.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        if pending_order and pending_order.get('selected_rate'):
            # Show warning about losing order data
            asyncio.create_task(mark_message_as_selected(update, context))
            
            keyboard = [
                [InlineKeyboardButton("✅ Да, в главное меню", callback_data='confirm_exit_to_menu')],
                [InlineKeyboardButton("❌ Отмена, вернуться", callback_data='return_to_payment')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            warning_text = """⚠️ *Внимание!*

У вас есть неоплаченный заказ.

Если вы перейдете в главное меню, все данные заказа будут удалены и вам придется создавать заказ заново.

Вы уверены?"""
            
            bot_msg = await safe_telegram_call(query.message.reply_text(
                warning_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            ))
            
            # Save message context for button protection
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = warning_text
            return
        
        await start_command(update, context)
    elif query.data == 'my_balance':
        await my_balance_command(update, context)
    elif query.data == 'my_templates':
        await my_templates_menu(update, context)
    elif query.data == 'help':
        await help_command(update, context)
    elif query.data == 'faq':
        await faq_command(update, context)
    elif query.data == 'confirm_exit_to_menu':
        # User confirmed exit to main menu - clear pending order
        asyncio.create_task(mark_message_as_selected(update, context))
        telegram_id = query.from_user.id
        await db.pending_orders.delete_one({"telegram_id": telegram_id})
        context.user_data.clear()
        await start_command(update, context)
    elif query.data == 'new_order':
        # Starting new order - this is intentional, so clear previous data
        context.user_data.clear()
        await new_order_start(update, context)
    elif query.data == 'cancel_order':
        # Check if this is an orphaned cancel button (order already completed)
        if context.user_data.get('order_completed'):
            logger.info(f"Orphaned cancel button detected from user {update.effective_user.id}")
            await safe_telegram_call(query.answer("⚠️ Этот заказ уже завершён"))
            await safe_telegram_call(query.message.reply_text(
                "⚠️ *Этот заказ уже завершён или отменён.*\n\n"
                "Для создания нового заказа используйте меню в нижней части экрана.",
                parse_mode='Markdown'
            ))
        else:
            # Always allow cancel - even if context is empty (user just started)
            await cancel_order(update, context)
    elif query.data.startswith('create_label_'):
        # Handle create label button
        order_id = query.data.replace('create_label_', '')
        await handle_create_label_request(update, context, order_id)

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
    
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    balance = user.get('balance', 0.0) if user else 0.0
    
    message = f"""*💳 Ваш баланс: ${balance:.2f}*

*Вы можете использовать баланс для оплаты заказов.*

*Введите сумму для пополнения (минимум $10):*"""
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data='start')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
        
        if amount < 10:
            await safe_telegram_call(update.message.reply_text("❌ *Минимальная сумма для пополнения: $10*", parse_mode='Markdown'))
            return
        
        if amount > 10000:
            await safe_telegram_call(update.message.reply_text("❌ *Максимальная сумма для пополнения: $10,000*", parse_mode='Markdown'))
            return
        
        # Clear the waiting flag
        context.user_data['awaiting_topup_amount'] = False
        
        telegram_id = update.effective_user.id
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
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
            await db.payments.insert_one(payment_dict)
            
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
            error_msg = invoice_result.get('error', 'Unknown error')
            await safe_telegram_call(update.message.reply_text(f"❌ *Ошибка создания инвойса:* {error_msg}", parse_mode='Markdown'))
            
    except ValueError:
        await safe_telegram_call(update.message.reply_text("❌ *Неверный формат. Введите число (например: 10 или 25.50)*", parse_mode='Markdown'))

# Conversation states for order creation
FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, FROM_STATE, FROM_ZIP, FROM_PHONE, TO_NAME, TO_ADDRESS, TO_ADDRESS2, TO_CITY, TO_STATE, TO_ZIP, TO_PHONE, PARCEL_WEIGHT, PARCEL_LENGTH, PARCEL_WIDTH, PARCEL_HEIGHT, CONFIRM_DATA, EDIT_MENU, SELECT_CARRIER, PAYMENT_METHOD, TOPUP_AMOUNT, TEMPLATE_NAME, TEMPLATE_LIST, TEMPLATE_VIEW, TEMPLATE_RENAME, TEMPLATE_LOADED = range(28)

async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    
    # Clear any previous order data (including order_completed flag)
    context.user_data.clear()
    
    # DON'T set active_order flag here - too early!
    # User is just choosing between "New order" or "From template"
    # Flag will be set when they actually start (order_new or start_order_with_template)
    
    # Check if bot is in maintenance mode
    if await check_maintenance_mode(update):
        await safe_telegram_call(query.message.reply_text(
            "🔧 *Бот находится на техническом обслуживании.*\n\n"
            "Пожалуйста, попробуйте позже.\n\n"
            "Приносим извинения за неудобства.",
            parse_mode='Markdown'
        ))
        return ConversationHandler.END
    
    # Check if user is blocked
    if await check_user_blocked(telegram_id):
        await send_blocked_message(update)
        return ConversationHandler.END
    
    # Check if user has templates
    templates_count = await db.templates.count_documents({"telegram_id": telegram_id})
    
    if templates_count > 0:
        # Show choice: New order or From template
        keyboard = [
            [InlineKeyboardButton("📝 Новый заказ", callback_data='order_new')],
            [InlineKeyboardButton("📋 Из шаблона", callback_data='order_from_template')],
            [InlineKeyboardButton("❌ Отмена", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            """📦 Создать заказ

Выберите способ создания:""",
            reply_markup=reply_markup
        ))
        return FROM_NAME  # Waiting for choice
    else:
        # No templates, go straight to new order
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = """📦 Создание нового заказа

Шаг 1/13: 👤 Имя отправителя
Например: John Smith"""
        bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
        
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
            context.user_data['last_state'] = FROM_NAME
        return FROM_NAME

async def order_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Skip if user is in topup flow
    if context.user_data.get('awaiting_topup_amount'):
        return ConversationHandler.END
    
    name = update.message.text.strip()
    
    # Sanitize input
    name = sanitize_string(name, max_length=50)
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in name):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: John Smith"))
        return FROM_NAME
    
    # Validate name
    if len(name) < 2:
        await safe_telegram_call(update.message.reply_text("❌ Имя слишком короткое. Введите полное имя (минимум 2 символа):"))
        return FROM_NAME
    
    if len(name) > 50:
        await safe_telegram_call(update.message.reply_text("❌ Имя слишком длинное. Максимум 50 символов:"))
        return FROM_NAME
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in name):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки"))
        return FROM_NAME
    
    context.user_data['from_name'] = name
    
    # Log action
    await SecurityLogger.log_action(
        "order_input",
        update.effective_user.id,
        {"field": "from_name", "length": len(name)},
        "success"
    )
    
    # Mark previous message as selected (remove buttons from step 1)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 2/13: 🏠 Адрес отправителя
Например: 215 Clayton St."""
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg is None:
        await safe_telegram_call(update.message.reply_text("❌ Ошибка отправки. Попробуйте еще раз:"))
        return FROM_NAME
    
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text  # Save text for editing
    context.user_data['last_state'] = FROM_ADDRESS  # Save state for next step
    return FROM_ADDRESS

async def order_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🔍 order_from_address CALLED - user_id: {update.effective_user.id}, message_id: {update.message.message_id}")
    logger.info(f"🔍 Text received: '{update.message.text}'")
    logger.info(f"🔍 user_data before: {list(context.user_data.keys())}")
    
    address = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: 215 Clayton St"))
        return FROM_ADDRESS
    
    # Validate address
    if len(address) < 3:
        await safe_telegram_call(update.message.reply_text("❌ Адрес слишком короткий. Введите полный адрес:"))
        return FROM_ADDRESS
    
    if len(address) > 100:
        await safe_telegram_call(update.message.reply_text("❌ Адрес слишком длинный. Максимум 100 символов:"))
        return FROM_ADDRESS
    
    # Only Latin letters, numbers, spaces, and common address symbols
    invalid_chars = [c for c in address if not (ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/&"))]
    if invalid_chars:
        invalid_display = ', '.join([f"'{c}'" for c in set(invalid_chars)])
        logger.warning(f"Invalid characters in address: {invalid_chars} (ords: {[ord(c) for c in invalid_chars]})")
        await safe_telegram_call(update.message.reply_text(
            f"❌ Найдены недопустимые символы: {invalid_display}\n\n"
            f"Используйте только:\n"
            f"• Английские буквы (A-Z, a-z)\n"
            f"• Цифры (0-9)\n"
            f"• Пробелы\n"
            f"• Спецсимволы: . - , ' # / &"
        ))
        return FROM_ADDRESS
    
    context.user_data['from_street'] = address
    
    # Mark previous message as selected (remove buttons from step 2)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_from_address2')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 3/13: 🚪 Квартира/Офис отправителя (необязательно)
Например: Apt 5, Suite 201
Или нажмите "Пропустить" """
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_ADDRESS2
    
    logger.info(f"🔍 order_from_address COMPLETED - returning FROM_ADDRESS2")
    logger.info(f"🔍 user_data after: {list(context.user_data.keys())}")
    return FROM_ADDRESS2

async def order_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        address2 = update.message.text.strip()
        
        # Check for Cyrillic or non-Latin characters
        if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address2):
            await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: Apt 5, Suite 201"))
            return FROM_ADDRESS2
        
        # Only Latin letters, numbers, spaces, and common address symbols
        if not all((ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/")) for c in address2):
            await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы и цифры. Разрешены: буквы, цифры, пробелы, дефисы, точки, запятые"))
            return FROM_ADDRESS2
        
        context.user_data['from_street2'] = address2
    else:
        context.user_data['from_street2'] = None
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 4/13: 🌆 Город отправителя
Например: San Francisco"""
    bot_msg = await safe_telegram_call((update.message or update.callback_query.message).reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = FROM_CITY
    return FROM_CITY

async def skip_from_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_telegram_call(query.answer())
    context.user_data['from_street2'] = None
    return await order_from_address2(update, context)

async def order_from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in city):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: San Francisco"))
        return FROM_CITY
    
    # Validate city
    if len(city) < 2:
        await safe_telegram_call(update.message.reply_text("❌ Название города слишком короткое:"))
        return FROM_CITY
    
    if len(city) > 50:
        await safe_telegram_call(update.message.reply_text("❌ Название города слишком длинное. Максимум 50 символов:"))
        return FROM_CITY
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in city):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки"))
        return FROM_CITY
    
    context.user_data['from_city'] = city
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 5/13: 📍 Штат отправителя (2 буквы)
Например: CA"""
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = FROM_STATE
    return FROM_STATE

async def order_from_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = update.message.text.strip().upper()
    
    # Validate state
    if len(state) != 2:
        await safe_telegram_call(update.message.reply_text("❌ Код штата должен быть ровно 2 буквы. Например: CA, NY, TX:"))
        return FROM_STATE
    
    if not state.isalpha():
        await safe_telegram_call(update.message.reply_text("❌ Код штата должен содержать только буквы:"))
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
        await safe_telegram_call(update.message.reply_text("❌ Неверный код штата. Введите корректный код (например: CA, NY, TX):"))
        return FROM_STATE
    
    context.user_data['from_state'] = state
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 6/13: 📬 ZIP код отправителя
Например: 94117"""
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_ZIP
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
        
        response = await asyncio.to_thread(
            requests.get,
            'https://api.shipstation.com/v2/carriers',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            carriers = data.get('carriers', [])
            
            # Exclude only GlobalPost (Stamps.com is USPS, keep it)
            excluded_carriers = ['globalpost']
            
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
        
        await safe_telegram_call(bot_instance.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=message,
            parse_mode='HTML'
        ))
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")

async def order_from_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zip_code = update.message.text.strip()
    
    # Validate ZIP code
    import re
    # US ZIP format: 5 digits or 5-4 digits
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат ZIP кода. Используйте формат: 12345 или 12345-6789:"))
        return FROM_ZIP
    
    context.user_data['from_zip'] = zip_code
    
    # Check if we're editing from address
    if context.user_data.get('editing_from_address'):
        context.user_data['editing_from_address'] = False
        # Mark previous message as selected before returning to confirmation
        asyncio.create_task(mark_message_as_selected(update, context))
        await safe_telegram_call(update.message.reply_text("✅ Адрес отправителя обновлен!"))
        return await show_data_confirmation(update, context)
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Пропустить", callback_data='skip_from_phone')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 7/13: 📱 Телефон отправителя
Например: +1234567890 или 1234567890"""
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_PHONE
    return FROM_PHONE

async def order_from_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's a callback query (skip phone button)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        if query.data == 'skip_from_phone':
            # Skip phone - generate random phone number
            random_phone = generate_random_phone()
            context.user_data['from_phone'] = random_phone
            logger.info(f"Generated random FROM phone: {random_phone}")
            
            # Mark previous message as selected (non-blocking)
            asyncio.create_task(mark_message_as_selected(update, context))
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = """Шаг 8/13: 👤 Имя получателя
Например: Jane Doe"""
            bot_msg = await safe_telegram_call(query.message.reply_text(
                message_text,
                reply_markup=reply_markup
            ))
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
            context.user_data['last_state'] = TO_NAME
            return TO_NAME
    
    phone = update.message.text.strip()
    
    # Check if phone starts with valid characters (+ or digit)
    if not phone or (phone[0] not in '0123456789+'):
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат телефона. Телефон должен начинаться с + или цифры\nНапример: +1234567890 или 1234567890"))
        return FROM_PHONE
    
    # Validate phone format
    import re
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a valid US phone number (10 or 11 digits)
    if len(digits_only) < 10 or len(digits_only) > 11:
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат телефона. Введите 10 цифр (например: 1234567890):"))
        return FROM_PHONE
    
    # Format phone number
    if len(digits_only) == 11 and digits_only[0] == '1':
        formatted_phone = f"+{digits_only}"
    elif len(digits_only) == 10:
        formatted_phone = f"+1{digits_only}"
    else:
        formatted_phone = f"+{digits_only}"
    
    context.user_data['from_phone'] = formatted_phone
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Шаг 8/13: 👤 Имя получателя
Например: Jane Doe"""
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = TO_NAME
    return TO_NAME

async def order_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in name):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: John Smith"))
        return TO_NAME
    
    # Validate name
    if len(name) < 2:
        await safe_telegram_call(update.message.reply_text("❌ Имя слишком короткое. Введите полное имя (минимум 2 символа):"))
        return TO_NAME
    
    if len(name) > 50:
        await safe_telegram_call(update.message.reply_text("❌ Имя слишком длинное. Максимум 50 символов:"))
        return TO_NAME
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in name):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки"))
        return TO_NAME
    
    context.user_data['to_name'] = name
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        message_text = """Шаг 2/6: Адрес получателя
Например: 123 Main St."""
    else:
        message_text = """Шаг 9/13: 🏠 Адрес получателя
Например: 123 Main St."""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = TO_ADDRESS
    return TO_ADDRESS

async def order_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🔍 order_to_address called - user: {update.effective_user.id}, text: {update.message.text if update.message else 'no message'}")
    address = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: 123 Main St"))
        return TO_ADDRESS
    
    # Validate address
    if len(address) < 3:
        await safe_telegram_call(update.message.reply_text("❌ Адрес слишком короткий. Введите полный адрес:"))
        return TO_ADDRESS
    
    if len(address) > 100:
        await safe_telegram_call(update.message.reply_text("❌ Адрес слишком длинный. Максимум 100 символов:"))
        return TO_ADDRESS
    
    # Only Latin letters, numbers, spaces, and common address symbols
    invalid_chars = [c for c in address if not (ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/&"))]
    if invalid_chars:
        invalid_display = ', '.join([f"'{c}'" for c in set(invalid_chars)])
        await safe_telegram_call(update.message.reply_text(
            f"❌ Найдены недопустимые символы: {invalid_display}\n\n"
            f"Используйте только:\n"
            f"• Английские буквы (A-Z, a-z)\n"
            f"• Цифры (0-9)\n"
            f"• Пробелы\n"
            f"• Спецсимволы: . - , ' # / &"
        ))
        return TO_ADDRESS
    
    context.user_data['to_street'] = address
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [
        [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_to_address2')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        message_text = """Шаг 3/6: Квартира/Офис получателя (необязательно)
Например: Apt 12, Suite 305
Или нажмите "Пропустить" """
    else:
        message_text = """Шаг 10/13: 🚪 Квартира/Офис получателя (необязательно)
Например: Apt 12, Suite 305
Или нажмите "Пропустить" """
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = TO_ADDRESS2
    return TO_ADDRESS2

async def order_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        address2 = update.message.text.strip()
        
        # Check for Cyrillic or non-Latin characters
        if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in address2):
            await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: Apt 12, Suite 305"))
            return TO_ADDRESS2
        
        # Only Latin letters, numbers, spaces, and common address symbols
        if not all((ord(c) < 128 and (c.isalnum() or c.isspace() or c in ".-',#/")) for c in address2):
            await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы и цифры. Разрешены: буквы, цифры, пробелы, дефисы, точки, запятые"))
            return TO_ADDRESS2
        
        context.user_data['to_street2'] = address2
    else:
        context.user_data['to_street2'] = None
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        message_text = """Шаг 4/6: Город получателя
Например: New York"""
    else:
        message_text = """Шаг 11/13: 🌆 Город получателя
Например: New York"""
    
    bot_msg = await safe_telegram_call((update.message or update.callback_query.message).reply_text(
        message_text,
        reply_markup=reply_markup
    ))
    context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = TO_CITY
    return TO_CITY

async def skip_to_address2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_telegram_call(query.answer())
    context.user_data['to_street2'] = None
    return await order_to_address2(update, context)

async def order_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    
    # Check for Cyrillic or non-Latin characters
    if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in city):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы (латиницу). Пример: New York"))
        return TO_CITY
    
    # Validate city
    if len(city) < 2:
        await safe_telegram_call(update.message.reply_text("❌ Название города слишком короткое:"))
        return TO_CITY
    
    if len(city) > 50:
        await safe_telegram_call(update.message.reply_text("❌ Название города слишком длинное. Максимум 50 символов:"))
        return TO_CITY
    
    # Only Latin letters, spaces, dots, hyphens, apostrophes
    if not all((ord(c) < 128 and (c.isalpha() or c.isspace() or c in ".-'")) for c in city):
        await safe_telegram_call(update.message.reply_text("❌ Используйте только английские буквы. Разрешены: буквы, пробелы, дефисы, точки"))
        return TO_CITY
    
    context.user_data['to_city'] = city
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        message_text = """Шаг 5/6: Штат получателя (2 буквы)
Например: NY"""
    else:
        message_text = """Шаг 12/13: 📍 Штат получателя (2 буквы)
Например: NY"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = TO_STATE
    return TO_STATE

async def order_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = update.message.text.strip().upper()
    
    # Validate state
    if len(state) != 2:
        await safe_telegram_call(update.message.reply_text("❌ Код штата должен быть ровно 2 буквы. Например: CA, NY, TX:"))
        return TO_STATE
    
    if not state.isalpha():
        await safe_telegram_call(update.message.reply_text("❌ Код штата должен содержать только буквы:"))
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
        await safe_telegram_call(update.message.reply_text("❌ Неверный код штата. Введите корректный код (например: CA, NY, TX):"))
        return TO_STATE
    
    context.user_data['to_state'] = state
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we're in editing mode
    if context.user_data.get('editing_to_address'):
        message_text = """Шаг 6/6: ZIP код получателя
Например: 10007"""
    else:
        message_text = """Шаг 13/13: 📬 ZIP код получателя
Например: 10007"""
    
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = TO_ZIP
    return TO_ZIP

async def order_to_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zip_code = update.message.text.strip()
    
    # Validate ZIP code
    import re
    # US ZIP format: 5 digits or 5-4 digits
    if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат ZIP кода. Используйте формат: 12345 или 12345-6789:"))
        return TO_ZIP
    
    context.user_data['to_zip'] = zip_code
    
    # Check if we're editing to address
    if context.user_data.get('editing_to_address'):
        context.user_data['editing_to_address'] = False
        # Mark previous message as selected before returning to confirmation
        asyncio.create_task(mark_message_as_selected(update, context))
        await safe_telegram_call(update.message.reply_text("✅ Адрес получателя обновлен!"))
        return await show_data_confirmation(update, context)
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Пропустить", callback_data='skip_to_phone')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """Телефон получателя (необязательно)
Например: +1234567890 или 1234567890
Или нажмите "Пропустить" """
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = TO_PHONE
    return TO_PHONE

async def order_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's a callback query (skip phone button)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        if query.data == 'skip_to_phone':
            # Skip phone - generate random phone number
            random_phone = generate_random_phone()
            context.user_data['to_phone'] = random_phone
            logger.info(f"Generated random TO phone: {random_phone}")
            
            # Mark previous message as selected (non-blocking)
            asyncio.create_task(mark_message_as_selected(update, context))
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = """📦 Вес посылки в фунтах (lb)
Например: 2"""
            bot_msg = await safe_telegram_call(query.message.reply_text(
                message_text,
                reply_markup=reply_markup
            ))
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_bot_message_text'] = message_text
            context.user_data['last_state'] = PARCEL_WEIGHT
            return PARCEL_WEIGHT
    
    phone = update.message.text.strip()
    
    # Check if phone starts with valid characters (+ or digit)
    if not phone or (phone[0] not in '0123456789+'):
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат телефона. Телефон должен начинаться с + или цифры\nНапример: +1234567890 или 1234567890"))
        return TO_PHONE
    
    # Validate phone format
    import re
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a valid US phone number (10 or 11 digits)
    if len(digits_only) < 10 or len(digits_only) > 11:
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат телефона. Введите 10 цифр (например: 1234567890):"))
        return TO_PHONE
    
    # Format phone number
    if len(digits_only) == 11 and digits_only[0] == '1':
        formatted_phone = f"+{digits_only}"
    elif len(digits_only) == 10:
        formatted_phone = f"+1{digits_only}"
    else:
        formatted_phone = f"+{digits_only}"
    
    context.user_data['to_phone'] = formatted_phone
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """📦 Вес посылки в фунтах (lb)
Например: 2"""
    bot_msg = await safe_telegram_call(update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
    context.user_data['last_bot_message_text'] = message_text
    context.user_data['last_state'] = PARCEL_WEIGHT
    return PARCEL_WEIGHT

async def order_parcel_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.strip())
        
        if weight <= 0:
            await safe_telegram_call(update.message.reply_text("❌ Вес должен быть больше 0. Попробуйте еще раз:"))
            return PARCEL_WEIGHT
        
        if weight > 150:
            await safe_telegram_call(update.message.reply_text("❌ Вес слишком большой. Максимум 150 фунтов. Попробуйте еще раз:"))
            return PARCEL_WEIGHT
        
        context.user_data['weight'] = weight
        
        # Check if we're editing parcel weight - ask for dimensions too
        if context.user_data.get('editing_parcel'):
            await safe_telegram_call(update.message.reply_text("✅ Вес посылки обновлен!"))
            # Don't set editing_parcel to False yet - we need to edit dimensions too
        
        # Mark previous message as selected (fire and forget)
        try:
            asyncio.create_task(mark_message_as_selected(update, context))
        except:
            pass  # Don't block on marking
        
        # Ask for length (with skip option only if weight <= 10 lb)
        if weight > 10:
            # Heavy parcel - user MUST enter dimensions
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Use universal timeout wrapper
            bot_msg = await safe_telegram_call(
                update.message.reply_text(
                    """📏 Длина посылки в дюймах (inches))

⚠️ Для посылок тяжелее 10 фунтов необходимо указать точные размеры для корректного расчета стоимости.

Введите длину в дюймах (например: 15):""",
                    reply_markup=reply_markup
                )
            )
        else:
            # Light parcel - can skip and use default dimensions
            keyboard = [[InlineKeyboardButton("⏭️ Использовать стандартные размеры", callback_data='skip_dimensions')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Use universal timeout wrapper
            bot_msg = await safe_telegram_call(
                update.message.reply_text(
                    """📏 Длина посылки в дюймах (inches))
Например: 12

Или нажмите кнопку ниже, чтобы использовать стандартные размеры (10x10x10 дюймов)""",
                    reply_markup=reply_markup
                )
            )
        
        # If message failed to send, return to previous state
        if bot_msg is None:
            await safe_telegram_call(update.message.reply_text("❌ Ошибка отправки. Попробуйте еще раз:"))
            return PARCEL_WEIGHT
        
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = PARCEL_LENGTH  # Save state for next step
        return PARCEL_LENGTH
            
    except asyncio.TimeoutError:
        logger.error(f"Timeout error in order_parcel_weight for user {update.effective_user.id}")
        await safe_telegram_call(update.message.reply_text("❌ Превышено время ожидания. Попробуйте еще раз:"))
        return PARCEL_WEIGHT
    except ValueError:
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат. Введите число (например: 2 или 2.5):"))
        return PARCEL_WEIGHT


async def order_parcel_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's a callback query (skip dimensions button)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        if query.data == 'skip_dimensions':
            # Use default dimensions 10x10x10
            context.user_data['length'] = 10
            context.user_data['width'] = 10
            context.user_data['height'] = 10
            
            # Mark previous message as selected (non-blocking)
            asyncio.create_task(mark_message_as_selected(update, context))
            
            await safe_telegram_call(query.message.reply_text("✅ Используются стандартные размеры: 10x10x10 дюймов"))
            
            # If we're editing parcel, mark as complete
            if context.user_data.get('editing_parcel'):
                context.user_data['editing_parcel'] = False
                await safe_telegram_call(query.message.reply_text("✅ Размеры посылки обновлены!"))
            
            # Show data confirmation
            context.user_data['last_state'] = CONFIRM_DATA
            return await show_data_confirmation(update, context)
    
    try:
        length = float(update.message.text.strip())
        
        if length <= 0:
            await safe_telegram_call(update.message.reply_text("❌ Длина должна быть больше 0. Попробуйте еще раз:"))
            return PARCEL_LENGTH
        
        if length > 108:  # 9 feet max
            await safe_telegram_call(update.message.reply_text("❌ Длина слишком большая. Максимум 108 дюймов. Попробуйте еще раз:"))
            return PARCEL_LENGTH
        
        context.user_data['length'] = length
        
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Ask for width (with skip option only if weight <= 10 lb)
        weight = context.user_data.get('weight', 0)
        
        if weight > 10:
            # Heavy parcel - user MUST enter dimensions
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot_msg = await safe_telegram_call(update.message.reply_text(
                """Ширина посылки в дюймах (in)

Введите ширину в дюймах (например: 12):""",
                reply_markup=reply_markup
            ))
        else:
            # Light parcel - can skip and use default dimensions
            keyboard = [[InlineKeyboardButton("⏭️ Использовать стандартные размеры", callback_data='skip_dimensions')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot_msg = await safe_telegram_call(update.message.reply_text(
                """Ширина посылки в дюймах (in)
Например: 10

Или нажмите кнопку ниже, чтобы использовать стандартные размеры для ширины и высоты (10x10 дюймов)""",
                reply_markup=reply_markup
            ))
        
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_state'] = PARCEL_WIDTH
        return PARCEL_WIDTH
            
    except ValueError:
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат. Введите число (например: 12 или 12.5):"))
        return PARCEL_LENGTH

async def order_parcel_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if it's a callback query (skip dimensions button)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        if query.data == 'skip_dimensions':
            # Use default dimensions 10x10 for width and height
            context.user_data['width'] = 10
            context.user_data['height'] = 10
            
            # Mark previous message as selected (non-blocking)
            asyncio.create_task(mark_message_as_selected(update, context))
            
            await safe_telegram_call(query.message.reply_text("✅ Используются стандартные размеры для ширины и высоты: 10x10 дюймов"))
            
            # If we're editing parcel, mark as complete
            if context.user_data.get('editing_parcel'):
                context.user_data['editing_parcel'] = False
                await safe_telegram_call(query.message.reply_text("✅ Размеры посылки обновлены!"))
            
            # Show data confirmation
            context.user_data['last_state'] = CONFIRM_DATA
            return await show_data_confirmation(update, context)
    
    try:
        width = float(update.message.text.strip())
        
        if width <= 0:
            await safe_telegram_call(update.message.reply_text("❌ Ширина должна быть больше 0. Попробуйте еще раз:"))
            return PARCEL_WIDTH
        
        if width > 108:
            await safe_telegram_call(update.message.reply_text("❌ Ширина слишком большая. Максимум 108 дюймов. Попробуйте еще раз:"))
            return PARCEL_WIDTH
        
        context.user_data['width'] = width
        
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Ask for height (with skip option only if weight <= 10 lb)
        weight = context.user_data.get('weight', 0)
        
        if weight > 10:
            # Heavy parcel - user MUST enter dimensions
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot_msg = await safe_telegram_call(update.message.reply_text(
                """Высота посылки в дюймах (in)

Введите высоту в дюймах (например: 10):""",
                reply_markup=reply_markup
            ))
        else:
            # Light parcel - can skip and use default dimensions
            keyboard = [[InlineKeyboardButton("⏭️ Использовать стандартную высоту", callback_data='skip_height')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot_msg = await safe_telegram_call(update.message.reply_text(
                """Высота посылки в дюймах (in)
Например: 8

Или нажмите кнопку ниже, чтобы использовать стандартную высоту (10 дюймов)""",
                reply_markup=reply_markup
            ))
        
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
            context.user_data['last_state'] = PARCEL_HEIGHT
        return PARCEL_HEIGHT
            
    except ValueError:
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат. Введите число (например: 10 или 10.5):"))
        return PARCEL_WIDTH

async def order_parcel_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🔍 order_parcel_height called - user: {update.effective_user.id}, message: {update.message.text if update.message else 'callback'}")
    
    # Check if it's a callback query (skip height button)
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await safe_telegram_call(query.answer())
        
        if query.data == 'skip_height':
            # Use default height 10
            context.user_data['height'] = 10
            
            # Mark previous message as selected (non-blocking)
            asyncio.create_task(mark_message_as_selected(update, context))
            
            await safe_telegram_call(query.message.reply_text("✅ Используется стандартная высота: 10 дюймов"))
            
            # If we're editing parcel, mark as complete
            if context.user_data.get('editing_parcel'):
                context.user_data['editing_parcel'] = False
                await safe_telegram_call(query.message.reply_text("✅ Размеры посылки обновлены!"))
            
            # Show data confirmation
            context.user_data['last_state'] = CONFIRM_DATA
            return await show_data_confirmation(update, context)
    
    try:
        height = float(update.message.text.strip())
        
        if height <= 0:
            await safe_telegram_call(update.message.reply_text("❌ Высота должна быть больше 0. Попробуйте еще раз:"))
            return PARCEL_HEIGHT
        
        if height > 108:
            await safe_telegram_call(update.message.reply_text("❌ Высота слишком большая. Максимум 108 дюймов. Попробуйте еще раз:"))
            return PARCEL_HEIGHT
        
        context.user_data['height'] = height
        
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # If we're editing parcel, mark as complete
        if context.user_data.get('editing_parcel'):
            context.user_data['editing_parcel'] = False
            await safe_telegram_call(update.message.reply_text("✅ Размеры посылки обновлены!"))
        
        # Show data confirmation
        context.user_data['last_state'] = CONFIRM_DATA
        return await show_data_confirmation(update, context)
            
    except ValueError:
        await safe_telegram_call(update.message.reply_text("❌ Неверный формат. Введите число (например: 8 или 8.5):"))
        return PARCEL_HEIGHT


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
    message += f"   Размеры: {data.get('length', 10)} x {data.get('width', 10)} x {data.get('height', 10)} дюймов\n"
    
    keyboard = [
        [InlineKeyboardButton("✅ Всё верно, показать тарифы", callback_data='confirm_data')],
        [InlineKeyboardButton("✏️ Редактировать данные", callback_data='edit_data')],
        [InlineKeyboardButton("💾 Сохранить как шаблон", callback_data='save_template')],
        [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if it's a message or callback query
    if hasattr(update, 'callback_query') and update.callback_query:
        bot_msg = await safe_telegram_call(update.callback_query.message.reply_text(message, reply_markup=reply_markup))
    else:
        bot_msg = await safe_telegram_call(update.message.reply_text(message, reply_markup=reply_markup))
    
    # Save last bot message context for button protection
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
        context.user_data['last_state'] = CONFIRM_DATA  # Save state for cancel return
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
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📤 Редактирование адреса отправителя\n\nШаг 1/6: Имя отправителя\nНапример: John Smith",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = FROM_NAME
        return FROM_NAME
    
    if query.data == 'edit_to_address':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit to address
        context.user_data['editing_to_address'] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📥 Редактирование адреса получателя\n\nШаг 1/6: Имя получателя\nНапример: Jane Doe",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = TO_NAME
        return TO_NAME
    
    if query.data == 'edit_parcel':
        # Mark previous message as selected (non-blocking)
        asyncio.create_task(mark_message_as_selected(update, context))
        
        # Edit parcel dimensions
        context.user_data['editing_parcel'] = True
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot_msg = await safe_telegram_call(query.message.reply_text(
            "📦 Редактирование посылки\n\nВведите вес посылки в фунтах:\nНапример: 5 или 2.5",
            reply_markup=reply_markup,
        ))
        if bot_msg:
            context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_state'] = PARCEL_WEIGHT
        return PARCEL_WEIGHT
    
    if query.data == 'back_to_confirmation':
        # Return to confirmation screen
        return await show_data_confirmation(update, context)

async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu to select what to edit"""
    query = update.callback_query
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    message = "✏️ Что вы хотите изменить?"
    
    keyboard = [
        [InlineKeyboardButton("📤 Адрес отправителя", callback_data='edit_from_address')],
        [InlineKeyboardButton("📥 Адрес получателя", callback_data='edit_to_address')],
        [InlineKeyboardButton("📦 Вес посылки", callback_data='edit_parcel')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_confirmation')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    
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
    
    # Check template limit (10 templates max)
    templates_count = await db.templates.count_documents({"telegram_id": telegram_id})
    if templates_count >= 10:
        await safe_telegram_call(update.message.reply_text(
            """❌ *Достигнут лимит шаблонов (10)*

Удалите старые шаблоны в меню "📋 Мои шаблоны" """,
            parse_mode='Markdown'
        ))
        return ConversationHandler.END
    
    # Create template
    template = Template(
        user_id=user['id'],
        telegram_id=telegram_id,
        name=template_name,
        from_name=context.user_data.get('from_name', ''),
        from_street1=context.user_data.get('from_street', ''),  # Use 'from_street' not 'from_address'
        from_street2=context.user_data.get('from_street2', ''),
        from_city=context.user_data.get('from_city', ''),
        from_state=context.user_data.get('from_state', ''),
        from_zip=context.user_data.get('from_zip', ''),
        from_phone=context.user_data.get('from_phone', ''),
        to_name=context.user_data.get('to_name', ''),
        to_street1=context.user_data.get('to_street', ''),  # Use 'to_street' not 'to_address'
        to_street2=context.user_data.get('to_street2', ''),
        to_city=context.user_data.get('to_city', ''),
        to_state=context.user_data.get('to_state', ''),
        to_zip=context.user_data.get('to_zip', ''),
        to_phone=context.user_data.get('to_phone', '')
    )
    
    template_dict = template.model_dump()
    template_dict['created_at'] = template_dict['created_at'].isoformat()
    await db.templates.insert_one(template_dict)
    
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
    
    # Get user
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
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
    templates = await db.templates.find({"telegram_id": telegram_id}).sort("created_at", -1).to_list(10)
    logger.info(f"📋 my_templates_menu: user {telegram_id} has {len(templates)} templates")
    
    if not templates:
        keyboard = [
            [InlineKeyboardButton("📦 Создать заказ", callback_data='new_order')],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            """📋 *Мои шаблоны*

У вас пока нет сохраненных шаблонов.
Создайте заказ и нажмите "*Сохранить как шаблон*" на экране проверки данных.""",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
        return ConversationHandler.END
    
    # Build template list message
    message = f"📋 *Выберите шаблон:*\n\n"
    
    keyboard = []
    for i, template in enumerate(templates, 1):
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
        
        # Add compact template info to message
        message += f"*{i}. {template['name']}*\n"
        message += f"📤 От: {from_name}\n"
        message += f"   {from_street}, {from_city}, {from_state} {from_zip}\n"
        message += f"📥 Кому: {to_name}\n"
        message += f"   {to_street}, {to_city}, {to_state} {to_zip}\n\n"
        
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
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
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
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
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
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
    
    context.user_data['last_state'] = PARCEL_WEIGHT
    return PARCEL_WEIGHT

async def delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete template with confirmation"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    template_id = query.data.replace('template_delete_', '')
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
    if not template:
        await safe_telegram_call(query.message.reply_text("❌ Шаблон не найден"))
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f'template_confirm_delete_{template_id}')],
        [InlineKeyboardButton("❌ Отмена", callback_data=f'template_view_{template_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(query.message.reply_text(
            f"""⚠️ *Удалить шаблон "{template['name']}"?*

Это действие нельзя отменить.""",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        ))
    # Clear last_bot_message to prevent accidentally removing these buttons
    context.user_data.pop('last_bot_message_id', None)
    context.user_data.pop('last_bot_message_text', None)
    # Don't return state - working outside ConversationHandler

async def confirm_delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and delete template"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (non-blocking)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    template_id = query.data.replace('template_confirm_delete_', '')
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    
    if template:
        result = await db.templates.delete_one({"id": template_id})
        logger.info(f"🗑️ Deleted template '{template['name']}' (id: {template_id}) - deleted_count: {result.deleted_count}")
        
        keyboard = [[InlineKeyboardButton("🔙 К списку шаблонов", callback_data='my_templates')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_telegram_call(query.message.reply_text(
            f"""✅ Шаблон "{template['name']}" удален""",
            reply_markup=reply_markup
        ))
    else:
        logger.warning(f"⚠️ Template {template_id} not found for deletion")
        await safe_telegram_call(query.message.reply_text("❌ Шаблон не найден"))
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
    
    await db.templates.update_one(
        {"id": template_id},
        {"$set": {"name": new_name}}
    )
    
    keyboard = [[InlineKeyboardButton("👁️ Просмотреть", callback_data=f'template_view_{template_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_telegram_call(update.message.reply_text(
            f"""✅ Шаблон переименован в "{new_name}" """,
            reply_markup=reply_markup
        ))
    
    return ConversationHandler.END

async def order_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new order (without template)"""
    logger.info(f"order_new called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Clear topup flag to prevent conflict with order input
    context.user_data['awaiting_topup_amount'] = False
    
    # Mark previous message as selected (remove buttons from choice screen)
    asyncio.create_task(mark_message_as_selected(update, context))
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = """📦 Создание нового заказа

Шаг 1/13: 👤 Имя отправителя
Например: John Smith"""
    bot_msg = await safe_telegram_call(query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        ))
    
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        context.user_data['last_state'] = FROM_NAME
    logger.info(f"order_new returning FROM_NAME state")
    return FROM_NAME

async def order_from_template_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show template list for order creation"""
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    telegram_id = query.from_user.id
    templates = await db.templates.find({"telegram_id": telegram_id}).sort("created_at", -1).to_list(10)
    
    if not templates:
        await safe_telegram_call(query.message.reply_text("❌ У вас нет сохраненных шаблонов"))
        return ConversationHandler.END
    
    message = "📋 *Выберите шаблон:*\n\n"
    keyboard = []
    
    for i, template in enumerate(templates, 1):
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
        
        # Add detailed template info to message
        message += f"*{i}. {template['name']}*\n"
        message += f"📤 От: {from_name}\n"
        message += f"   {from_street}, {from_city}, {from_state} {from_zip}\n"
        message += f"📥 Кому: {to_name}\n"
        message += f"   {to_street}, {to_city}, {to_state} {to_zip}\n\n"
        
        keyboard.append([InlineKeyboardButton(
            f"{i}. {template['name']}", 
            callback_data=f'template_use_{template["id"]}'
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='start')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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

async def fetch_shipping_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch shipping rates from ShipStation"""
    query = update.callback_query
    
    # Send initial progress message
    progress_msg = await safe_telegram_call(query.message.reply_text("⏳ Получаю доступные курьерские службы и тарифы... (0 сек)"))
    
    try:
        import requests
        import asyncio
        
        data = context.user_data
        
        # Validate required fields and check for None values
        required_fields = ['from_name', 'from_street', 'from_city', 'from_state', 'from_zip', 
                          'to_name', 'to_street', 'to_city', 'to_state', 'to_zip', 'weight']
        missing_fields = [field for field in required_fields if not data.get(field) or data.get(field) == 'None' or data.get(field) == '']
        
        if missing_fields:
            logger.error(f"Missing or invalid required fields: {missing_fields}")
            logger.error(f"Current user_data: {data}")
            keyboard = [
                [InlineKeyboardButton("✏️ Редактировать данные", callback_data='edit_data')],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
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
            keyboard = [
                [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await safe_telegram_call(query.message.reply_text(
            "❌ Ошибка: не удалось загрузить список курьеров.\n\nПожалуйста, попробуйте позже.",
            reply_markup=reply_markup,
        ))
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
                        'length': data.get('length', 10),
                        'width': data.get('width', 10),
                        'height': data.get('height', 10),
                        'unit': 'inch'
                    }
                }]
            }
        }
        
        # Log the request for debugging
        logger.info(f"ShipStation rate request: {rate_request}")
        
        # Get rates from ShipStation using async wrapper to prevent blocking
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    requests.post,
                    'https://api.shipstation.com/v2/rates',
                    headers=headers,
                    json=rate_request,
                    timeout=30
                ),
                timeout=35  # Overall timeout including thread overhead
            )
        except asyncio.TimeoutError:
            logger.error("ShipStation rate request timed out after 35 seconds")
            keyboard = [
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data='continue_order')],
                [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await safe_telegram_call(query.message.reply_text(
                "❌ Превышено время ожидания ответа от ShipStation.\n\nПопробуйте еще раз или проверьте правильность адресов.",
                reply_markup=reply_markup
            ))
            return CONFIRM_DATA
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('message', f'Status code: {response.status_code}')
            logger.error(f"ShipStation rate request failed: {error_msg}")
            logger.error(f"Response body: {response.text}")
            
            keyboard = [
                [InlineKeyboardButton("✏️ Редактировать адреса", callback_data='edit_addresses_error')],
                [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await safe_telegram_call(query.message.reply_text(
            f"❌ Ошибка при получении тарифов:\n{error_msg}\n\nПроверьте правильность введенных адресов.",
            reply_markup=reply_markup,
        ))
            return CONFIRM_DATA  # Stay to handle callback
        
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
            
            await safe_telegram_call(query.message.reply_text(
            f"❌ Нет доступных тарифов для данного направления.\n\nПроверьте правильность введенных адресов.",
            reply_markup=reply_markup,
        ))
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
            
            # Deduplicate by service_type - keep only cheapest for each service
            seen_services = {}
            deduplicated_rates = []
            for rate in sorted_carrier_rates:
                service_type = rate.get('service_type', '')
                if service_type not in seen_services:
                    seen_services[service_type] = True
                    deduplicated_rates.append(rate)
            
            # Take top 5 unique services from each carrier
            balanced_rates.extend(deduplicated_rates[:5])
        
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
            'Stamps.com': '🦅 USPS',  # Stamps.com это USPS
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
        
        # Add user balance info at the end
        telegram_id = query.from_user.id
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        user_balance = user.get('balance', 0.0) if user else 0.0
        
        message += f"\n{'='*30}\n"
        message += f"💰 <b>Ваш баланс: ${user_balance:.2f}</b>\n"
        message += f"{'='*30}\n"
        
        # Add refresh rates button
        keyboard.append([
            InlineKeyboardButton("🔄 Обновить тарифы", callback_data='refresh_rates')
        ])
        
        # Add cancel button
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Save state for cancel return - only when showing rates
        context.user_data['last_state'] = SELECT_CARRIER
        
        bot_msg = await safe_telegram_call(query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML'))
        
        # Save last bot message context for button protection
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message
        
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
    context.user_data['last_state'] = PAYMENT_METHOD  # Save state for cancel return
    
    # Get user balance
    telegram_id = query.from_user.id
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    balance = user.get('balance', 0.0)
    user_discount = user.get('discount', 0.0)  # Get user discount percentage
    
    # Show payment options
    amount = selected_rate['amount']  # Amount with markup
    original_amount = selected_rate['original_amount']  # GoShippo price
    markup = amount - original_amount
    
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
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    data = context.user_data
    selected_rate = data['selected_rate']
    amount = context.user_data.get('final_amount', selected_rate['amount'])  # Use discounted amount
    
    # Get user discount (should be already calculated and stored in context)
    user_discount = context.user_data.get('user_discount', 0)
    discount_amount = context.user_data.get('discount_amount', 0)
    
    try:
        if query.data == 'pay_from_balance':
            # Pay from balance
            if user.get('balance', 0) < amount:
                await safe_telegram_call(query.message.reply_text("❌ Недостаточно средств на балансе."))
                return ConversationHandler.END
            
            # Create order
            order = await create_order_in_db(user, data, selected_rate, amount, user_discount, discount_amount)
            
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
                
                await safe_telegram_call(query.message.reply_text(
                    f"""✅ Заказ оплачен с баланса!

💳 Списано: ${amount}
💰 Новый баланс: ${new_balance:.2f}

📦 Shipping label создан успешно!""",
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
                await db.payments.insert_one(payment_dict)
                
                keyboard = [[InlineKeyboardButton("💳 Оплатить", url=pay_link)],
                           [InlineKeyboardButton("🔙 Главное меню", callback_data='start')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await safe_telegram_call(query.message.reply_text(
                    f"""✅ Заказ создан!

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
            await db.pending_orders.insert_one(pending_order)
            
            context.user_data['last_state'] = TOPUP_AMOUNT  # Save state for cancel return
            
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
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
        
        context.user_data.clear()
        return ConversationHandler.END
        
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
    pending_order = await db.pending_orders.find_one({"telegram_id": telegram_id}, {"_id": 0})
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
    
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    selected_rate = pending_order['selected_rate']
    logger.info(f"Selected rate keys: {selected_rate.keys()}")
    amount = pending_order.get('final_amount', selected_rate.get('amount', selected_rate.get('totalAmount', 0)))
    user_balance = user.get('balance', 0)
    
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
    await db.pending_orders.delete_one({"telegram_id": telegram_id})
    
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
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
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
            await db.payments.insert_one(payment_dict)
            
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
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        # Crypto names for display
        crypto_names = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'USDT': 'USDT (Tether)',
            'LTC': 'Litecoin',
            'USDC': 'USDC'
        }
        
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
            await db.payments.insert_one(payment_dict)
            
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
        
        # Get phone numbers (should always have values now due to random generation)
        from_phone = order['address_from'].get('phone', generate_random_phone())
        from_phone = from_phone.strip() if from_phone else generate_random_phone()
        
        to_phone = order['address_to'].get('phone', generate_random_phone())  
        to_phone = to_phone.strip() if to_phone else generate_random_phone()
        
        logger.info(f"Sending phones to ShipStation - from: '{from_phone}', to: '{to_phone}'")
        
        # Create label request for ShipStation V2
        label_request = {
            'label_layout': 'letter',
            'label_format': 'pdf',
            'shipment': {
                'ship_to': {
                    'name': order['address_to']['name'],
                    'phone': to_phone,
                    'address_line1': order['address_to']['street1'],
                    'address_line2': order['address_to'].get('street2', ''),
                    'city_locality': order['address_to']['city'],
                    'state_province': order['address_to']['state'],
                    'postal_code': order['address_to']['zip'],
                    'country_code': order['address_to'].get('country', 'US')
                },
                'ship_from': {
                    'name': order['address_from']['name'],
                    'company_name': '-',  # Minimal placeholder to avoid showing real company name
                    'phone': from_phone,
                    'address_line1': order['address_from']['street1'],
                    'address_line2': order['address_from'].get('street2', ''),
                    'city_locality': order['address_from']['city'],
                    'state_province': order['address_from']['state'],
                    'postal_code': order['address_from']['zip'],
                    'country_code': order['address_from'].get('country', 'US'),
                    'address_residential_indicator': 'yes'
                },
                'packages': [{
                    'weight': {
                        'value': order['parcel']['weight'],
                        'unit': 'pound'
                    },
                    'dimensions': {
                        'length': order['parcel'].get('length', 10),
                        'width': order['parcel'].get('width', 10),
                        'height': order['parcel'].get('height', 10),
                        'unit': 'inch'
                    }
                }],
                'service_code': order.get('selected_service_code', order.get('service_code', ''))  # Add service_code
            },
            'rate_id': order['rate_id']
        }
        
        logger.info(f"Purchasing label with rate_id: {order['rate_id']}")
        
        response = await asyncio.to_thread(
            requests.post,
            'https://api.shipstation.com/v2/labels',
            headers=headers,
            json=label_request,
            timeout=30
        )
        
        # ShipStation API returns 200 or 201 for success
        if response.status_code not in [200, 201]:
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
                # Download label PDF
                headers_download = {'API-Key': SHIPSTATION_API_KEY}
                label_response_download = await asyncio.to_thread(
                    requests.get,
                    label_download_url,
                    headers=headers_download,
                    timeout=30
                )
                
                if label_response_download.status_code == 200:
                    # Generate AI thank you message ONCE
                    try:
                        thank_you_msg = await generate_thank_you_message()
                    except Exception as e:
                        logger.error(f"Error generating thank you message: {e}")
                        thank_you_msg = "Спасибо за использование нашего сервиса!"
                    
                    # Send label as document
                    message_text = f"""✅ Shipping Label создан!

Order: #{order_id[:8]}
Сумма: ${order['amount']:.2f}
Carrier: {order['selected_carrier'].upper()}
Service: {order['selected_service']}
Tracking: {tracking_number}

Ваша этикетка во вложении."""
                    
                    # Clean tracking number for filename (remove invalid characters)
                    safe_tracking = "".join(c for c in tracking_number if c.isalnum() or c in "-_").strip()
                    filename = f"{safe_tracking}.pdf" if safe_tracking else f"label_{order_id[:8]}.pdf"
                    
                    await safe_telegram_call(bot_instance.send_document(
                        chat_id=telegram_id,
                        document=label_response_download.content,
                        filename=filename,
                        caption=message_text
                    ))
                    
                    # Send tracking info without buttons
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=f"🔗 Трекинг номер:\n\n`{tracking_number}`",
                        parse_mode='Markdown'
                    ))
                    
                    # Send AI-generated thank you message (ONCE)
                    logger.info(f"Sending thank you message to user {telegram_id}")
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=thank_you_msg
                    ))
                    logger.info(f"Thank you message sent successfully to user {telegram_id}")
                    
                    logger.info(f"Label PDF sent to user {telegram_id}")
                else:
                    # Fallback to text if PDF download fails
                    await safe_telegram_call(bot_instance.send_message(
                        chat_id=telegram_id,
                        text=f"""📦 Shipping label создан!

Tracking: {tracking_number}
Carrier: {order['selected_carrier']}
Service: {order['selected_service']}

Label PDF: {label_download_url}

Вы оплатили: ${order['amount']:.2f}"""
                    ))
                    logger.warning(f"Could not download label PDF, sent URL instead")
                    
            except Exception as e:
                logger.error(f"Error sending label to user: {e}")
                
        # Send notification to admin about new label
        if ADMIN_TELEGRAM_ID:
            try:
                # Get user info
                user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
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
        
        # Notify admin about error
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
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
    if last_state == SELECT_CARRIER:
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
    
    context.user_data.clear()
    
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
    logger.info(f"return_to_order called - user_id: {update.effective_user.id}")
    query = update.callback_query
    await safe_telegram_call(query.answer())
    
    # Mark previous message as selected (remove buttons and add "✅ Выбрано")
    asyncio.create_task(mark_message_as_selected(update, context))
    
    # Get the state we were in when cancel was pressed
    last_state = context.user_data.get('last_state')
    
    logger.info(f"return_to_order: last_state = {last_state}")
    logger.info(f"return_to_order: user_data keys = {list(context.user_data.keys())}")
    
    # If no last_state - just continue
    if last_state is None:
        logger.warning("return_to_order: No last_state found!")
        await safe_telegram_call(query.message.reply_text("Продолжаем оформление заказа..."))
        return FROM_NAME
    
    # Restore exact screen with instructions for each state
    if last_state == FROM_NAME:
        message_text = "Шаг 1/13: 👤 Имя отправителя\n\nНапример: Ivan Petrov"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return FROM_NAME
    
    elif last_state == FROM_ADDRESS:
        message_text = "Шаг 2/13: Адрес отправителя\n\nВведите улицу и номер дома\nНапример: 215 Clayton St"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return FROM_ADDRESS
    
    elif last_state == FROM_ADDRESS2:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_from_address2')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = """Шаг 3/13: Квартира/Офис отправителя (необязательно)

Например: Apt 5, Suite 201

Или нажмите "Пропустить" """
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return FROM_ADDRESS2
    
    elif last_state == FROM_CITY:
        message_text = "Шаг 4/13: Город отправителя\n\nНапример: Los Angeles"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return FROM_CITY
    
    elif last_state == FROM_STATE:
        message_text = "Шаг 5/13: Штат отправителя\n\nВведите двухбуквенный код штата\nНапример: CA, NY, TX"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return FROM_STATE
    
    elif last_state == FROM_ZIP:
        message_text = "Шаг 6/13: ZIP код отправителя\n\nНапример: 90001"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return FROM_ZIP
    
    elif last_state == FROM_PHONE:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_from_phone')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = "Шаг 7/13: Телефон отправителя (необязательно)\n\nНапример: 5551234567\nИли нажмите 'Пропустить'"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return FROM_PHONE
    
    elif last_state == TO_NAME:
        message_text = "Шаг 8/13: Имя получателя\n\nНапример: John Smith"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return TO_NAME
    
    elif last_state == TO_ADDRESS:
        message_text = "Шаг 9/13: Адрес получателя\n\nВведите улицу и номер дома\nНапример: 123 Main St"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return TO_ADDRESS
    
    if last_state == TO_ADDRESS2:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_to_address2')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = """Шаг 10/13: Квартира/Офис получателя (необязательно)

Например: Apt 12, Suite 305

Или нажмите "Пропустить" """
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return TO_ADDRESS2
    
    elif last_state == TO_CITY:
        message_text = "Шаг 11/13: Город получателя\n\nНапример: New York"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return TO_CITY
    
    elif last_state == TO_STATE:
        message_text = "Шаг 11/13: Штат получателя\n\nВведите двухбуквенный код штата\nНапример: CA, NY, TX"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return TO_STATE
    
    elif last_state == TO_ZIP:
        message_text = "Шаг 12/13: ZIP код получателя\n\nНапример: 10001"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return TO_ZIP
    
    elif last_state == TO_PHONE:
        keyboard = [
            [InlineKeyboardButton("⏭ Пропустить", callback_data='skip_to_phone')],
            [InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = "Шаг 13/13: Телефон получателя (необязательно)\n\nНапример: 5559876543\nИли нажмите 'Пропустить'"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return TO_PHONE
    
    elif last_state == PARCEL_WEIGHT:
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = "Вес посылки в фунтах (lb)\nНапример: 2"
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return PARCEL_WEIGHT
    
    elif last_state == PARCEL_LENGTH:
        keyboard = [[InlineKeyboardButton("⏭️ Использовать стандартные размеры", callback_data='skip_dimensions')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = """📏 Длина посылки в дюймах (inches)
Например: 12

Или нажмите кнопку ниже, чтобы использовать стандартные размеры (10x10x10 дюймов)"""
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return PARCEL_LENGTH
    
    elif last_state == PARCEL_WIDTH:
        keyboard = [[InlineKeyboardButton("⏭️ Использовать стандартные размеры", callback_data='skip_dimensions')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = """📏 Ширина посылки в дюймах (inches)
Например: 10

Или нажмите кнопку ниже, чтобы использовать стандартные размеры для ширины и высоты (10x10 дюймов)"""
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return PARCEL_WIDTH
    
    elif last_state == PARCEL_HEIGHT:
        keyboard = [[InlineKeyboardButton("⏭️ Использовать стандартную высоту", callback_data='skip_height')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = """📏 Высота посылки в дюймах (inches)
Например: 8

Или нажмите кнопку ниже, чтобы использовать стандартную высоту (10 дюймов)"""
        bot_msg = await safe_telegram_call(query.message.reply_text(message_text, reply_markup=reply_markup))
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
        return PARCEL_HEIGHT
    
    # Special states - show their specific screens
    elif last_state == CONFIRM_DATA:
        # User was on data confirmation screen
        return await show_data_confirmation(update, context)
    
    elif last_state == EDIT_MENU:
        # User was on edit menu screen
        return await show_edit_menu(update, context)
    
    # Later stages - restore specific screens
    elif last_state == SELECT_CARRIER:
        logger.info("return_to_order: Handling SELECT_CARRIER state")
        # Check if we have enough data to fetch rates
        data = context.user_data
        required_fields = ['from_name', 'from_city', 'from_state', 'from_zip', 
                          'to_name', 'to_city', 'to_state', 'to_zip', 'weight']
        
        if all(field in data for field in required_fields):
            # Have all data - can fetch rates
            await safe_telegram_call(query.message.reply_text("Возвращаемся к выбору тарифа..."))
            return await fetch_shipping_rates(update, context)
        else:
            # Missing data - just continue
            logger.warning(f"return_to_order: Missing data for SELECT_CARRIER. Has: {list(data.keys())}")
            await safe_telegram_call(query.message.reply_text("Продолжаем оформление заказа..."))
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
            await safe_telegram_call(query.message.reply_text(confirmation_text, reply_markup=reply_markup))
            return PAYMENT_METHOD
        else:
            await safe_telegram_call(query.message.reply_text("Продолжаем..."))
            return last_state
    
    elif last_state == TOPUP_AMOUNT:
        # Return to top-up amount input
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='cancel_order')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
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
    
    else:
        # Default fallback
        await safe_telegram_call(query.message.reply_text("Продолжаем оформление заказа..."))
        return last_state if last_state else PAYMENT_METHOD

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Telegram Shipping Bot API", "status": "running"}


# Debug endpoints removed - were causing startup issues and memory_handler references

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
                await safe_telegram_call(bot_instance.send_message(
                    chat_id=order_data.telegram_id,
                    text=f"""✅ Заказ создан!

💰 Оплатите {order_data.amount} USDT:
{pay_url}

После оплаты мы автоматически создадим shipping label."""
                ))
            
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
            user = await db.users.find_one({"telegram_id": order['telegram_id']}, {"_id": 0})
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
        user = await db.users.find_one({"telegram_id": order['telegram_id']}, {"_id": 0})
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
        
        # ShipStation V2 tracking endpoint
        response = await asyncio.to_thread(
            requests.get,
            f'https://api.shipstation.com/v2/tracking?tracking_number={tracking_number}&carrier_code={carrier}',
            headers=headers,
            timeout=10
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
        
        # Download label from ShipStation
        response = await asyncio.to_thread(
            requests.get,
            label_url,
            headers=headers,
            timeout=30
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
                
                # Void label on ShipStation V2
                void_response = requests.put(
                    f'https://api.shipstation.com/v2/labels/{label["label_id"]}/void',
                    headers=headers,
                    timeout=10
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
        user = await db.users.find_one({"telegram_id": order['telegram_id']}, {"_id": 0})
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
        
        # Create label via ShipStation
        response = await asyncio.to_thread(
            requests.post,
            'https://api.shipstation.com/v2/labels',
            headers=headers,
            json=shipment_data,
            timeout=30
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
        
        logger.info(f"Creating label manually from form")
        
        # Create label via ShipStation
        response = await asyncio.to_thread(
            requests.post,
            'https://api.shipstation.com/v2/labels',
            headers=headers,
            json=shipment_data,
            timeout=30
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
    try:
        body = await request.json()
        logger.info(f"Oxapay webhook received: {body}")
        
        # Extract payment info - Oxapay sends snake_case keys
        track_id = body.get('track_id') or body.get('trackId')  # Support both formats
        status = body.get('status')  # Waiting, Confirming, Paying, Paid, Expired, etc.
        order_id = body.get('order_id') or body.get('orderId')  # Support both formats
        paid_amount = body.get('paidAmount') or body.get('paid_amount') or body.get('amount', 0)  # Actual paid amount
        
        # Convert track_id to int if it's a string number
        if track_id and isinstance(track_id, str) and track_id.isdigit():
            track_id = int(track_id)
        
        if status == 'Paid':
            payment = await db.payments.find_one({"invoice_id": track_id}, {"_id": 0})
            if payment:
                # Update payment status
                await db.payments.update_one(
                    {"invoice_id": track_id},
                    {"$set": {"status": "paid", "paid_amount": paid_amount}}
                )
                
                # Check if it's a top-up
                if payment.get('type') == 'topup':
                    # Add to balance - use actual paid amount
                    telegram_id = payment.get('telegram_id')
                    requested_amount = payment.get('amount', 0)
                    actual_amount = paid_amount if paid_amount > 0 else requested_amount
                    
                    await db.users.update_one(
                        {"telegram_id": telegram_id},
                        {"$inc": {"balance": actual_amount}}
                    )
                    
                    # Remove "Оплатить" button from payment message
                    payment_message_id = payment.get('payment_message_id')
                    logger.info(f"Payment message_id for removal: {payment_message_id}")
                    if payment_message_id and bot_instance:
                        try:
                            await safe_telegram_call(bot_instance.edit_message_reply_markup(
                                chat_id=telegram_id,
                                message_id=payment_message_id,
                                reply_markup=None
                            ))
                            logger.info(f"Removed payment button from message {payment_message_id}")
                        except Exception as e:
                            logger.warning(f"Could not remove payment button: {e}")
                    
                    # Remove "Назад" and "Главное меню" buttons from topup input message
                    topup_input_message_id = payment.get('topup_input_message_id')
                    logger.info(f"Topup input message_id for removal: {topup_input_message_id}")
                    if topup_input_message_id and bot_instance:
                        try:
                            await safe_telegram_call(bot_instance.edit_message_reply_markup(
                                chat_id=telegram_id,
                                message_id=topup_input_message_id,
                                reply_markup=None
                            ))
                            logger.info(f"Removed topup input buttons from message {topup_input_message_id}")
                        except Exception as e:
                            # Ignore "message not modified" error (buttons already removed)
                            if "message is not modified" in str(e).lower():
                                logger.info(f"Topup input buttons already removed from message {topup_input_message_id}")
                            else:
                                logger.warning(f"Could not remove topup input buttons: {e}")
                    else:
                        logger.warning(f"No topup_input_message_id found in payment record")
                    
                    # Notify user
                    if bot_instance:
                        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
                        new_balance = user.get('balance', 0)
                        
                        # Show requested vs actual amount if different
                        if abs(actual_amount - requested_amount) > 0.01:
                            amount_text = f"""💰 *Запрошено:* ${requested_amount:.2f}
💰 *Зачислено:* ${actual_amount:.2f}"""
                        else:
                            amount_text = f"💰 *Зачислено:* ${actual_amount:.2f}"
                        
                        # Check if user has pending order
                        pending_order = await db.pending_orders.find_one({"telegram_id": telegram_id}, {"_id": 0})
                        
                        # Build message text
                        message_text = f"""✅ *Спасибо! Ваш баланс пополнен!*

{amount_text}
💳 *Новый баланс:* ${new_balance:.2f}"""
                        
                        # Create keyboard
                        keyboard = []
                        if pending_order and pending_order.get('selected_rate'):
                            order_amount = pending_order.get('final_amount', pending_order['selected_rate']['amount'])
                            message_text += f"\n\n📦 *Сумма заказа к оплате:* ${order_amount:.2f}"
                            message_text += "\n_Нажмите 'Оплатить заказ' чтобы завершить оплату_"
                            keyboard.append([InlineKeyboardButton("💳 Оплатить заказ", callback_data='return_to_payment')])
                        
                        keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='start')])
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        bot_msg = await safe_telegram_call(bot_instance.send_message(
                            chat_id=telegram_id,
                            text=message_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        ))
                        
                        # Save message context in pending_orders for button protection
                        await db.pending_orders.update_one(
                            {"telegram_id": telegram_id},
                            {"$set": {
                                "topup_success_message_id": bot_msg.message_id,
                                "topup_success_message_text": message_text
                            }}
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
                        if order:
                            await create_and_send_label(payment['order_id'], order['telegram_id'], None)
                    except Exception as e:
                        logger.error(f"Failed to create label: {e}")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Oxapay webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.get("/users")
async def get_users(authenticated: bool = Depends(verify_admin_key)):
    users = await db.users.find({}, {"_id": 0}).to_list(100)
    return users


@api_router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    try:
        from telegram import Update
        
        # Get update data
        update_data = await request.json()
        update_id = update_data.get('update_id', 'unknown')
        logger.info(f"🔵 WEBHOOK RECEIVED: update_id={update_id}")
        
        # Log message details if present
        if 'message' in update_data:
            msg = update_data['message']
            logger.info(f"🔵 MESSAGE: user={msg.get('from',{}).get('id')}, text={msg.get('text','no text')}")
        
        # Check if application is initialized
        if not application:
            logger.error("🔴 WEBHOOK ERROR: Telegram application not initialized yet")
            return {"ok": True}
        
        logger.info(f"🔵 APPLICATION READY: Processing update {update_id}")
        
        # Process update through application
        try:
            update = Update.de_json(update_data, application.bot)
            logger.info(f"🔵 UPDATE PARSED: Starting process_update for {update_id}")
            await application.process_update(update)
            logger.info(f"🟢 UPDATE PROCESSED SUCCESSFULLY: {update_id}")
            return {"ok": True}
        except Exception as process_error:
            logger.error(f"🔴 PROCESSING ERROR for update {update_id}: {process_error}", exc_info=True)
            return {"ok": True}
            
    except Exception as e:
        logger.error(f"🔴 WEBHOOK ENDPOINT ERROR: {e}", exc_info=True)
        return {"ok": True}


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
    }



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

@api_router.post("/users/{telegram_id}/block")
async def block_user(telegram_id: int, authenticated: bool = Depends(verify_admin_key)):
    """Block a user from using the bot"""
    try:
        user = await db.users.find_one({"telegram_id": telegram_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user blocked status
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": True}}
        )
        
        if result.modified_count > 0:
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
        user = await db.users.find_one({"telegram_id": telegram_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user blocked status
        result = await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": False}}
        )
        
        if result.modified_count > 0:
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
        user = await db.users.find_one({"telegram_id": telegram_id})
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
        
        message = f"""🎉 *Приглашение в наш канал!*

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
        
        message = f"""🎉 *Приглашение в наш канал!*

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
        except:
            pass
        
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
        user = await db.users.find_one({"telegram_id": telegram_id})
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
        
        user = await db.users.find_one({"telegram_id": telegram_id})
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
        
        user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
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
        
        # Get carrier accounts
        response = await asyncio.to_thread(
            requests.get,
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
                        'length': parcel.get('length', 10),
                        'width': parcel.get('width', 10),
                        'height': parcel.get('height', 10),
                        'unit': 'inch'
                    }
                }]
            }
        }
        
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    requests.post,
                    'https://api.shipstation.com/v2/rates',
                    headers=headers,
                    json=rate_request,
                    timeout=30
                ),
                timeout=35  # Overall timeout including thread overhead
            )
        except asyncio.TimeoutError:
            logger.error("ShipStation rate request timed out after 35 seconds (API endpoint)")
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
        from datetime import datetime, timezone, timedelta
        
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
                user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
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
    
    # Load correct API key based on api_mode in database
    global SHIPSTATION_API_KEY
    try:
        api_mode_setting = await db.settings.find_one({"key": "api_mode"})
        api_mode = api_mode_setting.get("value", "production") if api_mode_setting else "production"
        
        if api_mode == "test":
            SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY_TEST', SHIPSTATION_API_KEY)
            logger.info(f"🧪 Loaded TEST API key from environment")
        else:
            SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY_PROD', SHIPSTATION_API_KEY)
            logger.info(f"🚀 Loaded PRODUCTION API key from environment")
        
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
            # Build application with optimized settings for high load (5000+ concurrent users)
            # CRITICAL: Use RedisPersistence for webhook mode - multi-pod safe, ultra-fast
            from redis_persistence import RedisPersistence
            
            # Use Redis for instant, multi-pod safe persistence
            redis_host = os.environ.get('REDIS_HOST', 'localhost')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))
            redis_password = os.environ.get('REDIS_PASSWORD', '')
            
            persistence = RedisPersistence(
                redis_host=redis_host,
                redis_port=redis_port,
                redis_password=redis_password,
                update_interval=0.05  # Save every 50ms - nearly instant!
            )
            
            application = (
                Application.builder()
                .token(TELEGRAM_BOT_TOKEN)
                .persistence(persistence)  # CRITICAL for webhook mode!
                .concurrent_updates(True)  # Process updates concurrently
                .connect_timeout(3)  # Super fast connection
                .read_timeout(3)  # Super fast read
                .write_timeout(3)  # Super fast write
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
                per_message=False
            )
            
            order_conv_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(new_order_start, pattern='^new_order$'),
                    CallbackQueryHandler(start_order_with_template, pattern='^start_order_with_template$'),
                    CallbackQueryHandler(return_to_payment_after_topup, pattern='^return_to_payment$')
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
                    PARCEL_LENGTH: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_length),
                        CallbackQueryHandler(order_parcel_length, pattern='^skip_dimensions$'),
                        CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                        CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
                    ],
                    PARCEL_WIDTH: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_width),
                        CallbackQueryHandler(order_parcel_width, pattern='^skip_dimensions$'),
                        CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                        CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
                    ],
                    PARCEL_HEIGHT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, order_parcel_height),
                        CallbackQueryHandler(order_parcel_height, pattern='^skip_height$'),
                        CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                        CallbackQueryHandler(return_to_order, pattern='^return_to_order$')
                    ],
                    CONFIRM_DATA: [
                        CallbackQueryHandler(handle_data_confirmation, pattern='^(confirm_data|save_template|edit_data|edit_addresses_error|edit_from_address|edit_to_address|return_to_order|confirm_cancel|cancel_order)$')
                    ],
                    EDIT_MENU: [CallbackQueryHandler(handle_data_confirmation, pattern='^(edit_from_address|edit_to_address|edit_parcel|back_to_confirmation|return_to_order|confirm_cancel)$')],
                    SELECT_CARRIER: [CallbackQueryHandler(select_carrier, pattern='^(select_carrier_|refresh_rates|check_data|return_to_order|confirm_cancel|cancel_order)')],
                    PAYMENT_METHOD: [
                        CallbackQueryHandler(return_to_order, pattern='^return_to_order$'),
                        CallbackQueryHandler(confirm_cancel_order, pattern='^confirm_cancel$'),
                        CallbackQueryHandler(process_payment, pattern='^(pay_from_balance|pay_with_crypto|top_up_balance|back_to_rates|cancel_order)')
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
                per_message=False
            )
            
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
                logger.error(f"Traceback:", exc_info=context.error)
                
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
            
            # Auto-detect environment based on WEBHOOK_BASE_URL
            # Preview: contains "preview" → POLLING mode
            # Production: contains "crypto-shipping.emergent.host" → WEBHOOK mode
            webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
            is_production = 'crypto-shipping.emergent.host' in webhook_base_url
            
            # Choose webhook URL based on environment
            if is_production:
                # Production: use webhook mode
                webhook_url = webhook_base_url
                logger.info(f"🟢 PRODUCTION ENVIRONMENT: {webhook_base_url}")
            else:
                # Preview: use polling mode
                webhook_url = None
                logger.info(f"🔵 PREVIEW ENVIRONMENT: {webhook_base_url}")
            
            if webhook_url:
                # Production: use webhook
                # Remove trailing slash from webhook_url to avoid double slashes
                webhook_url = webhook_url.rstrip('/')
                webhook_endpoint = f"{webhook_url}/api/telegram/webhook"
                logger.info(f"Starting Telegram Bot in WEBHOOK mode: {webhook_endpoint}")
                await application.bot.delete_webhook(drop_pending_updates=True)
                await application.bot.set_webhook(
                    url=webhook_endpoint,
                    allowed_updates=["message", "callback_query"]
                )
                logger.info("Telegram Bot webhook set successfully!")
            else:
                # Preview: use polling
                logger.info("Starting Telegram Bot in POLLING mode (preview)")
                await application.updater.start_polling()
                logger.info("Telegram Bot polling started successfully!")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}")
            logger.warning("Application will continue without Telegram Bot")
    else:
        logger.warning("Telegram Bot Token not configured. Bot features will be disabled.")
        logger.info("To enable Telegram Bot, add TELEGRAM_BOT_TOKEN to backend/.env")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()