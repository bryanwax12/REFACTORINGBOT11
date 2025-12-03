from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os

# CRITICAL: Load .env BEFORE any other imports that use environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# WORKAROUND: Emergent platform concatenates environment variables
# Use production config file if env vars are corrupted
def is_env_corrupted(value):
    """Check if environment variable is concatenated with others"""
    if not value:
        return False
    # Check for obvious concatenation patterns
    corruption_indicators = [
        'REACT_APP_',  # Frontend var mixed in
        'MONGO_URL=',  # Another var mixed in
        'WEBHOOK_BASE_URL=',  # Another var mixed in
        'BOT_TOKEN=',  # Another var mixed in
        'TELEGRAM_BOT_TOKEN=',  # Another var mixed in
    ]
    for indicator in corruption_indicators:
        if indicator in value:
            return True
    # Check if value is suspiciously long (normal keys are < 60 chars)
    if len(value) > 60:
        return True
    return False

# Check critical env variables
for key in ['ADMIN_API_KEY', 'MONGO_URL', 'TELEGRAM_BOT_TOKEN', 'WEBHOOK_BASE_URL', 'SHIPSTATION_API_KEY']:
    current_value = os.environ.get(key)
    if current_value:
        print(f"✅ Using env variable for {key}: {current_value[:20]}...")
    else:
        print(f"⚠️ Environment variable {key} not set")

# Verify ShipStation API keys are set
if not os.environ.get('SHIPSTATION_API_KEY_TEST'):
    print("⚠️ SHIPSTATION_API_KEY_TEST not set")
if not os.environ.get('SHIPSTATION_API_KEY_PROD'):
    print("⚠️ SHIPSTATION_API_KEY_PROD not set")

from bot_protection import BotProtection
from telegram_safety import TelegramSafetySystem, TelegramBestPractices
import logging
import httpx

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime, timezone
import uuid
import time
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import asyncio
import warnings

# Suppress PTBUserWarning about per_message settings (expected behavior)
try:
    from telegram.warnings import PTBUserWarning
    warnings.filterwarnings("ignore", category=PTBUserWarning)
except ImportError:
    # Fallback if PTBUserWarning not available
    warnings.filterwarnings("ignore", message=".*per_message.*")

# Setup logger
logger = logging.getLogger(__name__)

# Performance monitoring

# API Services
from services.api_services import (
    check_shipstation_balance
)

# Business Logic Services

# Common handlers (start, help, faq, button routing)
from handlers.common_handlers import (
    start_command,
    help_command,
    button_callback,
    mark_message_as_selected,
    safe_telegram_call
)

# Admin handlers
from handlers.admin_handlers import (
    notify_admin_error
)

# Webhook handlers

# Order flow handlers

# Import address2 handlers directly since they're not in __init__.py yet

# Payment handlers
from handlers.payment_handlers import (
    my_balance_command as handler_my_balance_command,
)

# Template handlers  
from handlers.template_handlers import (
    my_templates_menu as handler_my_templates_menu,
    view_template as handler_view_template,
    use_template as handler_use_template,
    edit_template_menu as handler_edit_template_menu,
    edit_template_from_address as handler_edit_template_from_address,
    edit_template_to_address as handler_edit_template_to_address,
    delete_template as handler_delete_template,
    confirm_delete_template as handler_confirm_delete_template,
    rename_template_start as handler_rename_template_start,
    rename_template_save as handler_rename_template_save,
)

# Order flow - cancellation handlers
from handlers.order_flow.cancellation import (
    cancel_order as handler_cancel_order,
    confirm_cancel_order as handler_confirm_cancel_order,
)

# Order flow - entry point handlers
from handlers.order_flow.entry_points import (
    new_order_start as handler_new_order_start,
    start_order_with_template as handler_start_order_with_template,
)

# Order flow - confirmation handlers
from handlers.order_flow.confirmation import (
    show_data_confirmation as handler_show_data_confirmation,
)

# Order handlers (shipping rates, carrier selection)
from handlers.order_handlers import (
    display_shipping_rates as handler_display_shipping_rates,
    select_carrier as handler_select_carrier,
)

# Template save handlers
from handlers.order_flow.template_save import (
    save_template_name as handler_save_template_name,
    handle_template_update as handler_handle_template_update,
)

# Utility functions (Phase 4 refactoring - gradually moving from server.py)
# Note: These are still defined in server.py for backward compatibility
# TODO: Update all imports to use utils modules and remove duplicates
from utils.telegram_utils import (
    is_button_click_allowed as util_is_button_click_allowed,
    generate_random_phone as util_generate_random_phone,
    sanitize_string as util_sanitize_string,
    generate_thank_you_message as util_generate_thank_you_message
)
from utils.session_utils import (
    save_to_session as util_save_to_session,
    handle_critical_api_error as util_handle_critical_api_error,
    handle_step_error as util_handle_step_error
)
from utils.settings_cache import (
    clear_settings_cache as util_clear_settings_cache
)

# MIGRATED: Profiled DB operations moved to utils.db_operations
# (delete_template now imported from handlers.template_handlers instead)

# Debug logging removed - was causing startup issues

# MongoDB connection with connection pooling for high load
# Import performance config for optimized settings
from config.performance_config import BotPerformanceConfig

try:
    # Support both MONGO_URL (local) and MONGODB_URI (deployment platform)
    # Priority: MONGODB_URI > MONGO_URL (for deployment compatibility)
    mongo_url = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URL', '')
    
    if mongo_url:
        print(f"📊 MongoDB URL source: {'MONGODB_URI' if os.environ.get('MONGODB_URI') else 'MONGO_URL'}")
        print(f"📊 MongoDB URL: {mongo_url[:30]}...")
    
    if not mongo_url:
        print("⚠️ MONGO_URL/MONGODB_URI not set - MongoDB will be initialized later")
        client = None
        db = None
        session_manager = None
        repository_manager = None
    else:
        mongodb_config = BotPerformanceConfig.get_mongodb_config()
        client = AsyncIOMotorClient(
            mongo_url,
            maxPoolSize=mongodb_config['maxPoolSize'],
            minPoolSize=mongodb_config['minPoolSize'],
            maxIdleTimeMS=mongodb_config['maxIdleTimeMS'],
            serverSelectionTimeoutMS=mongodb_config['serverSelectionTimeoutMS'],
            connectTimeoutMS=mongodb_config['connectTimeoutMS'],
            socketTimeoutMS=mongodb_config['socketTimeoutMS']
        )

        # Get database name from environment
        db_name = os.environ.get('DB_NAME', 'telegram_shipping_bot')
        print(f"📊 Using database: {db_name}")

        db = client[db_name]

        # Initialize Session Manager for state management
        from session_manager import SessionManager
        session_manager = SessionManager(db)

        # Initialize Repository Manager for data access layer
        from repositories import init_repositories, get_repositories
        repository_manager = init_repositories(db)
        print("📦 Repository Manager initialized successfully")
except Exception as e:
    print(f"⚠️ MongoDB initialization failed: {e}")
    print("⚠️ Application will start without database - configure MONGO_URL to enable")
    client = None
    db = None
    session_manager = None
    repository_manager = None

# In-memory cache for frequently accessed data

user_balance_cache = {}  # Cache user balances
cache_ttl = 60  # Cache TTL in seconds

# ============================================================
# API CONFIGURATION (Refactored with APIConfigManager)
# ============================================================
from utils.api_config import init_api_config

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
    # Create bot instance (timeout settings will be applied in Application.builder())
    # Note: Bot() constructor doesn't accept timeout params directly in PTB 20.x
    bot_instance = Bot(token=TELEGRAM_BOT_TOKEN)
    print(f"✅ Bot instance created: @{get_bot_username()}")
    print("⚡ Performance optimizations will be applied in Application.builder()")

# Simple in-memory cache for frequently accessed settings
# Cache moved to utils/cache.py


# Button click debouncing - prevent multiple rapid clicks
button_click_tracker = {}  # {user_id: {button_data: last_click_timestamp}}
BUTTON_DEBOUNCE_SECONDS = 0.1  # Максимально быстрый: 100ms между нажатиями

# Rate limiting для защиты от Telegram бана
# Using optimized rate limiter from middleware

# Note: Old simple RateLimiter replaced with advanced TelegramRateLimiter
# from middleware.rate_limiter which has:
# - Per-chat and global rate limiting
# - Smart retry logic for "Too Many Requests" errors
# - Semaphore-based concurrency control
# - Safe message sending with automatic rate limiting

# Helper function for session management
# DEPRECATED: Use utils.session_utils.save_to_session instead
save_to_session = util_save_to_session

# DEPRECATED: Use utils.session_utils.handle_critical_api_error instead
handle_critical_api_error = util_handle_critical_api_error


# DEPRECATED: Use utils.session_utils.handle_step_error instead
handle_step_error = util_handle_step_error

# DEPRECATED: Use utils.telegram_utils.is_button_click_allowed instead
# Keeping for backward compatibility
is_button_click_allowed = util_is_button_click_allowed

# Oxapay - Cryptocurrency Payment Gateway
OXAPAY_API_KEY = os.environ.get('OXAPAY_API_KEY', '')
OXAPAY_API_URL = 'https://api.oxapay.com'

# Oxapay helper functions - imported from services/api_services.py

# DEPRECATED: Use utils.telegram_utils.generate_random_phone instead
generate_random_phone = util_generate_random_phone

# DEPRECATED: Use utils.settings_cache.clear_settings_cache instead
clear_settings_cache = util_clear_settings_cache

# check_shipstation_balance - imported from services/api_services.py

# DEPRECATED: Use utils.telegram_utils.generate_thank_you_message instead
generate_thank_you_message = util_generate_thank_you_message

app = FastAPI(title="Telegram Shipping Bot")

# ==================== STARTUP EVENT ====================
@app.on_event("startup")
async def startup_event():
    """
    Автоматическая очистка старых сессий при запуске (включая deploy)
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    
    # Подождем 5 секунд, чтобы БД точно подключилась
    await asyncio.sleep(5)
    
    try:
        logger.warning("🧹 STARTUP: Автоматическая очистка старых сессий...")
        
        # Очистка через MongoDB
        result = await db.user_sessions.delete_many({})
        
        logger.warning(f"✅ STARTUP: Очищено {result.deleted_count} старых сессий")
        logger.warning("🎉 STARTUP: Все пользователи начнут с чистого листа!")
        
    except Exception as e:
        logger.error(f"⚠️ STARTUP: Не удалось очистить сессии: {e}")
        logger.error("⚠️ STARTUP: Это не критично, продолжаем работу")

# ==================== MIDDLEWARE ====================
from fastapi.middleware.cors import CORSMiddleware
from middleware.logging import RequestLoggingMiddleware
from middleware.rate_limiting import RateLimitMiddleware

# Add CORS middleware (CRITICAL for deployed version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware (order matters - first added = last executed)
app.add_middleware(RequestLoggingMiddleware, log_body=False)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60, requests_per_hour=1000)

api_router = APIRouter(prefix="/api")

# ==================== HEALTH CHECK ENDPOINT ====================
@app.get("/health")
async def health_check():
    """Health check endpoint for deployment platform"""
    db_status = "not_configured"
    db_error = None
    
    try:
        # Check if MongoDB is accessible
        if db is not None:
            await db.command('ping')
            db_status = "connected"
        else:
            db_status = "not_configured"
    except Exception as e:
        logger.warning(f"MongoDB not accessible in health check: {e}")
        db_status = "unavailable"
        db_error = str(e)
    
    # Return healthy status if app is running, even if DB is temporarily unavailable
    return {
        "status": "healthy",
        "app": "running",
        "database": db_status,
        "bot_configured": bool(TELEGRAM_BOT_TOKEN),
        "db_error": db_error if db_error else None
    }

@app.get("/api/health")
async def api_health_check():
    """Health check endpoint with /api prefix"""
    return await health_check()

# ==================== DEBUG ENDPOINT (NO AUTH) ====================
@app.get("/api/debug/config")
async def debug_config_no_auth():
    """Debug endpoint to check configuration (NO AUTH REQUIRED)"""
    import os
    from utils.simple_cache import get_cache_stats
    
    return {
        "status": "backend_running",
        "admin_key_set": bool(os.environ.get('ADMIN_API_KEY')),
        "admin_key_length": len(os.environ.get('ADMIN_API_KEY', '')),
        "admin_key_preview": os.environ.get('ADMIN_API_KEY', '')[:20] + '...' if os.environ.get('ADMIN_API_KEY') else 'NOT_SET',
        "mongo_url_set": bool(os.environ.get('MONGO_URL')),
        "mongo_url_preview": os.environ.get('MONGO_URL', '')[:30] + '...' if os.environ.get('MONGO_URL') else 'NOT_SET',
        "webhook_base_url": os.environ.get('WEBHOOK_BASE_URL', 'NOT_SET'),
        "config_file_used": os.path.exists('/app/backend/config_production.py'),
        "cache_stats": get_cache_stats(),
        "persistence_enabled": True,
    }

# ==================== ROUTERS REGISTRATION ====================
# Import and register all API routers
try:
    from routers.admin_router import admin_router
    from routers.admin_labels import router as admin_labels_router
    from routers.api_config_router import router as api_config_router
    from routers.bot import router as bot_router
    from routers.bot_config_router import router as bot_config_router
    from routers.broadcast import router as broadcast_router
    from routers.monitoring_router import router as monitoring_router
    from routers.orders import router as orders_router
    from routers.settings import router as settings_router
    from routers.shipping import router as shipping_router
    from routers.stats import router as stats_router
    from routers.users import router as users_router
    from routers.webhooks import router as webhooks_router
    from routers.legacy_api import router as legacy_api_router
    from routers.admin import admin_router_v2  # New modular admin router with balance endpoints
    
    # Register routers with app (routers already have /api prefix)
    app.include_router(legacy_api_router)  # Legacy endpoints for frontend compatibility
    app.include_router(admin_router)
    app.include_router(admin_router_v2)  # New admin router with balance management
    app.include_router(admin_labels_router)
    app.include_router(api_config_router)
    app.include_router(bot_router)
    app.include_router(bot_config_router)
    app.include_router(broadcast_router)
    app.include_router(monitoring_router)
    app.include_router(orders_router)
    app.include_router(settings_router)
    app.include_router(shipping_router)
    app.include_router(stats_router)
    app.include_router(users_router)
    app.include_router(webhooks_router)
    
    # Upload router
    from routers.upload import router as upload_router
    app.include_router(upload_router)
    
    # Mount static files for uploads
    uploads_dir = Path("/app/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
    
    # Refunds router
    from routers.refunds import router as refunds_router
    app.include_router(refunds_router)
    
    # Legacy admin endpoints (without /admin prefix for frontend compatibility)
    from routers.legacy_admin_endpoints import legacy_admin_router
    app.include_router(legacy_admin_router)
    
    logger.info("✅ All API routers registered successfully")
except Exception as e:
    logger.error(f"❌ Error registering routers: {e}")

# ==================== SECURITY ====================

# Input Sanitization

# DEPRECATED: Use utils.telegram_utils.sanitize_string instead
sanitize_string = util_sanitize_string

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

# Error handling middleware (должен быть первым!)
from middleware.error_handler_middleware import error_handler_middleware
app.middleware("http")(error_handler_middleware)

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
# Helper function to check if user is blocked
# check_user_blocked and send_blocked_message moved to handlers/common_handlers.py

# MIGRATED: Use handlers.common_handlers.handle_orphaned_button

# mark_message_as_selected_nonblocking removed - unused function (mark_message_as_selected is called directly)

# safe_telegram_call moved to handlers/common_handlers.py

# mark_message_as_selected moved to handlers/common_handlers.py

# check_maintenance_mode moved to handlers/common_handlers.py

# start_command and help_command moved to handlers/common_handlers.py


# faq_command moved to handlers/common_handlers.py



# MIGRATED: Use handlers.order_handlers.handle_create_label_request

# button_callback moved to handlers/common_handlers.py

# MIGRATED: Use handlers.payment_handlers.my_balance_command
# Keeping alias for backward compatibility
my_balance_command = handler_my_balance_command

# MIGRATED: Use handlers.payment_handlers.handle_topup_amount_input

# Conversation states for order creation
FROM_NAME, FROM_ADDRESS, FROM_ADDRESS2, FROM_CITY, FROM_STATE, FROM_ZIP, FROM_PHONE, TO_NAME, TO_ADDRESS, TO_ADDRESS2, TO_CITY, TO_STATE, TO_ZIP, TO_PHONE, PARCEL_WEIGHT, PARCEL_LENGTH, PARCEL_WIDTH, PARCEL_HEIGHT, CALCULATING_RATES, CONFIRM_DATA, EDIT_MENU, SELECT_CARRIER, PAYMENT_METHOD, TOPUP_AMOUNT, TEMPLATE_NAME, TEMPLATE_LIST, TEMPLATE_VIEW, TEMPLATE_RENAME, TEMPLATE_LOADED = range(29)

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
    CALCULATING_RATES: "CALCULATING_RATES",
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

# Reverse mapping: string names to state constants
STATE_CONSTANTS = {v: k for k, v in STATE_NAMES.items()}

# MIGRATED: Use handlers.order_flow.entry_points.new_order_start
# Keeping alias for backward compatibility
new_order_start = handler_new_order_start



# Skip handlers moved to handlers/order_flow/skip_handlers.py


# MIGRATED: Use handlers.order_flow.confirmation.show_data_confirmation
# Keeping alias for backward compatibility
show_data_confirmation = handler_show_data_confirmation

# MIGRATED: Use handlers.order_flow.confirmation.handle_data_confirmation


# MIGRATED: Use handlers.order_flow.confirmation.show_edit_menu

# MIGRATED: Use handlers.order_flow.template_save.save_template_name
save_template_name = handler_save_template_name

# MIGRATED: Use handlers.order_flow.template_save.handle_template_update
handle_template_update = handler_handle_template_update

# MIGRATED: Use handlers.template_handlers.handle_template_new_name

# MIGRATED: Use handlers.order_flow.entry_points.continue_order_after_template


# MIGRATED: Use handlers.template_handlers.my_templates_menu
# Keeping alias for backward compatibility
my_templates_menu = handler_my_templates_menu

# MIGRATED: Use handlers.template_handlers.view_template
# Keeping alias for backward compatibility
view_template = handler_view_template

# MIGRATED: Use handlers.template_handlers.use_template
# Keeping alias for backward compatibility
use_template = handler_use_template

# Template editing handlers
edit_template_menu = handler_edit_template_menu
edit_template_from_address = handler_edit_template_from_address
edit_template_to_address = handler_edit_template_to_address

# Template deletion handlers
delete_template = handler_delete_template
confirm_delete_template = handler_confirm_delete_template

# MIGRATED: Use handlers.order_flow.entry_points.start_order_with_template
# Keeping alias for backward compatibility
start_order_with_template = handler_start_order_with_template

# MIGRATED: Use handlers.template_handlers.confirm_delete_template
confirm_delete_template = handler_confirm_delete_template


# MIGRATED: Use handlers.template_handlers.rename_template_start
rename_template_start = handler_rename_template_start

# MIGRATED: Use handlers.template_handlers.rename_template_save
rename_template_save = handler_rename_template_save

# MIGRATED: Use handlers.order_flow.entry_points.order_new


# MIGRATED: Use handlers.order_flow.entry_points.order_from_template_list
from handlers.order_flow.entry_points import order_from_template_list


# MIGRATED: Use handlers.order_flow.skip_handlers.skip_address_validation

# MIGRATED: Use handlers.order_handlers.display_shipping_rates
display_shipping_rates = handler_display_shipping_rates


# MIGRATED: Use handlers.order_flow.rates.fetch_shipping_rates


# MIGRATED: Use handlers.order_handlers.select_carrier
select_carrier = handler_select_carrier

# MIGRATED: Use handlers.order_flow.payment.process_payment


async def create_order_in_db(user, data, selected_rate, amount, discount_percent=0, discount_amount=0):
    # Get order_id from session or generate new one
    from utils.order_utils import generate_order_id
    order_id = data.get('order_id') or generate_order_id(telegram_id=user['telegram_id'])
    
    order = Order(
        user_id=user.get('id', user.get('_id', str(user['telegram_id']))),
        order_id=order_id,  # Add unique order_id
        telegram_id=user['telegram_id'],
        address_from=Address(
            name=data['from_name'],
            street1=data.get('from_address', data.get('from_street', '')),  # Use from_address (correct key)
            street2=data.get('from_address2', data.get('from_street2', '')),
            city=data['from_city'],
            state=data['from_state'],
            zip=data['from_zip'],
            country="US",
            phone=data.get('from_phone', '')
        ),
        address_to=Address(
            name=data['to_name'],
            street1=data.get('to_address', data.get('to_street', '')),  # Use to_address (correct key)
            street2=data.get('to_address2', data.get('to_street2', '')),
            city=data['to_city'],
            state=data['to_state'],
            zip=data['to_zip'],
            country="US",
            phone=data.get('to_phone', '')
        ),
        parcel=Parcel(
            length=data.get('parcel_length', data.get('length', 10)),
            width=data.get('parcel_width', data.get('width', 10)),
            height=data.get('parcel_height', data.get('height', 10)),
            weight=data.get('parcel_weight', data.get('weight', 1)),
            distance_unit="in",
            mass_unit="lb"
        ),
        amount=amount  # This is the amount with markup (and discount applied) that user pays
    )
    
    order_dict = order.model_dump()
    order_dict['created_at'] = order_dict['created_at'].isoformat()
    order_dict['selected_carrier'] = selected_rate.get('carrier', selected_rate.get('carrier_friendly_name', 'Unknown'))
    order_dict['selected_service'] = selected_rate.get('service', selected_rate.get('service_type', 'Standard'))
    order_dict['selected_service_code'] = selected_rate.get('service_code', '')  # Add service_code
    order_dict['rate_id'] = selected_rate.get('rate_id', '')
    
    # Get original_amount safely
    rate_amount = selected_rate.get('amount', amount)
    original_amount = selected_rate.get('original_amount', rate_amount)
    
    order_dict['original_amount'] = original_amount  # Store original GoShippo price
    order_dict['markup'] = rate_amount - original_amount  # Store markup amount before discount
    order_dict['discount_percent'] = discount_percent  # Store discount percentage
    order_dict['discount_amount'] = discount_amount  # Store discount amount
    
    # Insert order using Repository Pattern
    repos = get_repositories()
    result = await repos.orders.collection.insert_one(order_dict)
    
    # Add MongoDB _id as 'id' field for compatibility
    order_dict['id'] = result.inserted_id
    
    return order_dict

async def create_and_send_label(order_id, telegram_id, message):
    try:
        # Get order using Repository Pattern
        from repositories import get_repositories
        repos = get_repositories()
        order = await repos.orders.find_by_order_id(order_id)
        
        logger.info(f"Creating label for order {order_id}")
        
        
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
        
        # Update order using Repository Pattern
        from repositories import get_repositories
        repos = get_repositories()
        update_result = await repos.orders.update_by_order_id(order_id, {
            "shipping_status": "label_created",
            "tracking_number": tracking_number,
            "label_id": label_id,
            "shipment_id": shipment_id
        })
        logger.info(f"📝 Order updated with tracking info: {update_result}")
        
        # Send label to user
        logger.info(f"📨 Preparing to send label to user {telegram_id}")
        if bot_instance:
            logger.info(f"✅ bot_instance available, proceeding with label delivery")
            try:
                # Show typing indicator in background while processing
                import asyncio
                from telegram.constants import ChatAction
                
                async def send_typing_continuously():
                    """Send typing indicator every 4 seconds while processing"""
                    try:
                        while True:
                            await bot_instance.send_chat_action(
                                chat_id=telegram_id,
                                action=ChatAction.TYPING
                            )
                            await asyncio.sleep(4)
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.debug(f"Typing indicator error: {e}")
                
                typing_task = asyncio.create_task(send_typing_continuously())
                
                try:
                    # Download label PDF using service
                    logger.info(f"⬇️ Downloading label PDF from: {label_download_url[:50]}...")
                    from services.shipping_service import download_label_pdf
                    success, pdf_bytes, error = await download_label_pdf(label_download_url, timeout=30)
                    logger.info(f"📥 Label PDF download result: success={success}")
                    
                    if success:
                        # Send label using service
                        logger.info(f"📤 Sending label PDF to user {telegram_id}...")
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
                            logger.info(f"📨 Sending tracking number to user...")
                            await safe_telegram_call(bot_instance.send_message(
                                chat_id=telegram_id,
                                text=f"🔗 Трекинг номер:\n\n`{tracking_number}`",
                                parse_mode='Markdown'
                            ))
                            logger.info(f"✅ Label and tracking sent successfully to user {telegram_id}")
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
                
                finally:
                    # Stop typing indicator
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass
                    
            except Exception as e:
                logger.error(f"Error sending label to user: {e}")
                # Stop typing indicator on error
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass
            
            # STEP 4: Save completed label and clear session
            await session_manager.save_completed_label(telegram_id, {
                'order_id': order_id,
                'tracking_number': tracking_number,
                'carrier': order['selected_carrier'],
                'label_url': label_download_url,
                'amount': order['amount']
            })
            logger.info(f"✅ Label saved and session cleared for user {telegram_id}")
        
        # Send notification to admin about new label (MOVED OUTSIDE bot_instance check)
        logger.info(f"🔔 Attempting to send admin notification. ADMIN_TELEGRAM_ID={ADMIN_TELEGRAM_ID}")
        if ADMIN_TELEGRAM_ID:
            try:
                logger.info(f"📤 Preparing admin notification for order {order_id}")
                # Get user info using Repository Pattern
                from repositories import get_user_repo
                user_repo = get_user_repo()
                user = await user_repo.find_by_telegram_id(telegram_id)
                user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
                username = user.get('username', '') if user else ''
                user_display = f"{user_name}" + (f" (@{username})" if username else f" (ID: {telegram_id})")
                
                # Format admin notification
                # Format FROM address with proper alignment
                from_addr_lines = []
                from_addr_lines.append(f"📍 *От:* {order['address_from']['name']}")
                from_addr_lines.append(f"     📍 {order['address_from']['street1']}")
                if order['address_from'].get('street2'):
                    from_addr_lines.append(f"     📍 {order['address_from']['street2']}")
                from_addr_lines.append(f"     🏙️ {order['address_from']['city']}, {order['address_from']['state']} {order['address_from']['zip']}")
                from_addr_str = '\n'.join(from_addr_lines)
                
                # Format TO address with proper alignment
                to_addr_lines = []
                to_addr_lines.append(f"📍 *Кому:* {order['address_to']['name']}")
                to_addr_lines.append(f"     📍 {order['address_to']['street1']}")
                if order['address_to'].get('street2'):
                    to_addr_lines.append(f"     📍 {order['address_to']['street2']}")
                to_addr_lines.append(f"     🏙️ {order['address_to']['city']}, {order['address_to']['state']} {order['address_to']['zip']}")
                to_addr_str = '\n'.join(to_addr_lines)
                
                admin_message = f"""📦 *Новый лейбл создан!*

👤 *Пользователь:* {user_display}

{from_addr_str}

{to_addr_str}

🚚 *Перевозчик:* {order['selected_carrier']} - {order['selected_service']}
📦 *Трекинг:* `{tracking_number}`
💰 *Цена:* ${order['amount']:.2f}
⚖️ *Вес:* {order['parcel']['weight']} lb

🕐 *Время:* {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}"""

                # Send to admin
                if 'application' in globals() and hasattr(application, 'bot'):
                    admin_bot = application.bot
                else:
                    from telegram import Bot
                    admin_bot = Bot(TELEGRAM_BOT_TOKEN)
                
                logger.info(f"📨 Sending notification to admin {ADMIN_TELEGRAM_ID}...")
                await safe_telegram_call(admin_bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                ))
                logger.info(f"✅ Label creation notification sent to admin {ADMIN_TELEGRAM_ID}")
            except Exception as e:
                logger.error(f"❌ Failed to send label notification to admin: {e}", exc_info=True)
        
        # Check ShipStation balance after label creation
        logger.info(f"🔍 Checking ShipStation balance...")
        asyncio.create_task(check_shipstation_balance())
        
        logger.info(f"✅ Label created successfully for order {order_id}")
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
        from repositories import get_user_repo
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(telegram_id)
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

# MIGRATED: Use handlers.order_flow.cancellation.cancel_order
# Keeping alias for backward compatibility
cancel_order = handler_cancel_order

# MIGRATED: Use handlers.order_flow.cancellation.confirm_cancel_order
# Keeping alias for backward compatibility
confirm_cancel_order = handler_confirm_cancel_order

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
        await safe_telegram_call(update.effective_message.reply_text("Продолжаем оформление заказа..."))
        return FROM_NAME
    
    # If last_state is a number (state constant), we need the string name
    # Check if it's a string (state name) or int (state constant)
    if isinstance(last_state, int):
        # It's a state constant - return it directly
        keyboard, message_text = OrderStepMessages.get_step_keyboard_and_message(str(last_state))
        logger.warning(f"return_to_order: last_state is int ({last_state}), should be string!")
        
        # Show next step
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(
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
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(message_text, reply_markup=keyboard))
    else:
        reply_markup = get_cancel_keyboard()
        bot_msg = await safe_telegram_call(update.effective_message.reply_text(message_text, reply_markup=reply_markup))
    
    # Save context
    if bot_msg:
        context.user_data['last_bot_message_id'] = bot_msg.message_id
        context.user_data['last_bot_message_text'] = message_text
    
    # Return the state constant
    return globals().get(last_state, FROM_NAME)
async def root():
    return {"message": "Telegram Shipping Bot API", "status": "running"}


# Debug endpoints removed - were causing startup issues and memory_handler references

# Old API decorators removed - endpoints moved to routers/


@app.on_event("startup")
async def startup_event():
    logger.info("Starting application...")
    
    # Инициализация мониторинга
    from utils.monitoring import init_sentry
    init_sentry()
    
    # Инициализация фабрики сервисов
    from services.service_factory import init_service_factory
    init_service_factory(db)
    logger.info("✅ Service factory initialized")
    
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
            global application, bot_instance  # Use global variables for webhook access
            
            # Prevent duplicate bot initialization
            if application is not None:
                logger.warning("⚠️  Telegram Bot application already initialized, skipping re-initialization")
                return
            
            logger.info("Initializing Telegram Bot...")
            # Build application - using in-memory state (STABLE) with performance optimizations
            
            # Get optimized settings from performance config
            app_settings = BotPerformanceConfig.get_optimized_application_settings()
            
            # DictPersistence for webhook mode - stores conversation state between HTTP requests
            # This is CRITICAL for webhook mode to work correctly!
            from telegram.ext import DictPersistence
            persistence = DictPersistence()
            logger.info("✅ DictPersistence initialized for webhook mode")
            
            # Optimize: Only receive needed update types (saves ~20-40ms)
            from telegram import Update
            allowed_update_types = [
                Update.MESSAGE,
                Update.CALLBACK_QUERY,
                Update.MY_CHAT_MEMBER,
            ]
            logger.info(f"⚡ Optimized: Only accepting {len(allowed_update_types)} update types")
            
            application = (
                Application.builder()
                .token(TELEGRAM_BOT_TOKEN)
                .persistence(persistence)  # DictPersistence for webhook mode - preserves conversation state
                .concurrent_updates(True)  # Allow concurrent updates for better performance in webhook mode
                .connect_timeout(app_settings['connect_timeout'])  # Fast connection
                .read_timeout(app_settings['read_timeout'])   # Optimized read timeout
                .write_timeout(app_settings['write_timeout'])  # Reliable message delivery
                .pool_timeout(app_settings['pool_timeout'])    # Connection pool optimization
                # Keep default rate limiter to prevent Telegram ban
                .build()
            )
            
            logger.info("✅ Application built with DictPersistence for webhook mode")
            logger.info("🔧 CRITICAL FIX: DictPersistence preserves conversation state between HTTP requests")
            
            # CRITICAL: Update global bot_instance with the application's bot for notifications
            # Without this, notifications will NOT work!
            global bot_instance
            bot_instance = application.bot
            
            # CRITICAL: Also store in app.state for FastAPI routers to access
            app.state.bot_instance = application.bot
            logger.info(f"🔔 Bot instance updated for notifications: @{get_bot_username()}")
            logger.info("✅ Bot instance also stored in app.state for routers")
            
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
                allow_reentry=True,
                name='template_rename_conversation',
                persistent=True  # Enabled: Using DictPersistence
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
# Old ConversationHandler definition removed - see handlers/order_flow/conversation_setup.py
            
            application.add_handler(template_rename_handler)
            
            # Refund conversation handler
            from handlers.refund_handlers import (
                refund_menu,
                process_refund_labels,
                cancel_refund,
                my_refunds,
                REFUND_INPUT
            )
            
            refund_conv_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(refund_menu, pattern='^refund_menu$')
                ],
                states={
                    REFUND_INPUT: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, process_refund_labels)
                    ]
                },
                fallbacks=[
                    CallbackQueryHandler(cancel_refund, pattern='^start$'),
                    CommandHandler('start', start_command)
                ],
                name='refund_conversation',
                persistent=True,  # Enabled: Using DictPersistence
                per_chat=True,
                per_user=True,
                allow_reentry=True
            )
            
            application.add_handler(refund_conv_handler)
            application.add_handler(CallbackQueryHandler(my_refunds, pattern='^my_refunds$'))
            from handlers.refund_handlers import return_to_main_menu
            application.add_handler(CallbackQueryHandler(return_to_main_menu, pattern='^main_menu$'))
            application.add_handler(order_conv_handler)
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CommandHandler("balance", my_balance_command))
            
            # Template handlers (must be before generic button_callback)
            # NOTE: use_template, edit_template_from_address, edit_template_to_address are now handled as entry points in order_conv_handler
            application.add_handler(CallbackQueryHandler(view_template, pattern='^template_view_'))
            application.add_handler(CallbackQueryHandler(edit_template_menu, pattern='^template_edit_'))
            application.add_handler(CallbackQueryHandler(delete_template, pattern='^template_delete_'))
            application.add_handler(CallbackQueryHandler(confirm_delete_template, pattern='^template_confirm_delete_'))
            # rename_template_start is now handled by template_rename_handler ConversationHandler
            application.add_handler(CallbackQueryHandler(my_templates_menu, pattern='^my_templates$'))
            application.add_handler(CallbackQueryHandler(order_from_template_list, pattern='^order_from_template$'))
            
            # Handler for topup amount input (text messages)
            # Will only process if awaiting_topup_amount flag is set
            from handlers.payment_handlers import handle_topup_amount_input
            from telegram.ext import filters as telegram_filters
            
            async def wrapped_topup_handler(update, context):
                """Wrapper that only calls handler if awaiting topup"""
                if context.user_data.get('awaiting_topup_amount'):
                    await handle_topup_amount_input(update, context)
            
            application.add_handler(MessageHandler(
                telegram_filters.TEXT & ~telegram_filters.COMMAND,
                wrapped_topup_handler
            ), group=1)  # Lower priority than ConversationHandler
            
            application.add_handler(CallbackQueryHandler(button_callback))

            logger.info("✅ ConversationHandler is the only handler for order flow - all debug handlers removed")

            
            
            # Global error handler for catching all exceptions
            async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                """Log all errors and notify admin"""
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
                
                # Notify admin about the error
                try:
                    if isinstance(update, Update) and update.effective_user:
                        from repositories import get_user_repo
                        user_repo = get_user_repo()
                        user = await user_repo.find_by_telegram_id(update.effective_user.id)
                        
                        if user:
                            error_details = f"{type(context.error).__name__}: {str(context.error)[:300]}"
                            await notify_admin_error(
                                user_info=user,
                                error_type="Global Bot Error",
                                error_details=error_details
                            )
                            logger.info("✅ Admin notified about error")
                except Exception as notify_error:
                    logger.error(f"Failed to notify admin about error: {notify_error}")
            
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
            logger.info(f"   BOT_MODE env: {bot_config.mode.upper()}")
            logger.info(f"   Webhook URL configured: {bool(webhook_url)}")
            logger.info(f"   Selected mode: {mode_icon} {'WEBHOOK' if use_webhook else 'POLLING'}")
            logger.info(f"   Bot: @{get_bot_username()}")
            
            # KUBERNETES DEPLOYMENT: Warn if polling in production
            if not use_webhook and is_production_environment():
                logger.warning("⚠️ POLLING MODE in production! This may cause conflicts with multiple replicas.")
                logger.warning("⚠️ Consider setting WEBHOOK_BASE_URL and WEBHOOK_PATH for production deployment.")
            
            if use_webhook and webhook_url:
                # Webhook mode
                logger.info(f"🌐 WEBHOOK MODE: {webhook_url}")
                
                # Удалить старый webhook перед установкой нового
                await application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("   Old webhook deleted")
                
                # Установить новый webhook
                await application.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "callback_query", "my_chat_member"],
                    drop_pending_updates=True  # Drop pending updates to avoid processing old messages
                )
                logger.info(f"   Webhook URL configured: {webhook_url}")
                
                logger.info(f"✅ Webhook set successfully: {webhook_url}")
                
            else:
                # Polling mode
                logger.info("🔄 POLLING MODE")
                
                # Убедиться что webhook отключен
                try:
                    await application.bot.delete_webhook(drop_pending_updates=True)
                    logger.info("   Webhook disabled")
                except Exception as e:
                    logger.debug(f"   Webhook delete skipped: {e}")
                
                # Запустить polling
                logger.info("   Starting polling with dropped pending updates...")
                await application.updater.start_polling(
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=True  # Drop old updates to avoid conflicts
                )
                
                logger.info("✅ Polling started successfully")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}", exc_info=True)
            logger.warning("Application will continue without Telegram Bot")
    else:
        logger.warning("Telegram Bot Token not configured. Bot features will be disabled.")
        logger.info("To enable Telegram Bot, add TELEGRAM_BOT_TOKEN to backend/.env")
    
    # Final check: verify bot_instance is available
    if bot_instance:
        logger.info("✅✅✅ bot_instance is AVAILABLE and ready for notifications!")
    else:
        logger.warning("⚠️⚠️⚠️ bot_instance is NOT set! Notifications will NOT work!")

@app.on_event("shutdown")
async def shutdown_db_client():
    """Cleanup on shutdown"""
    global bot_instance, application
    
    # Stop Telegram bot properly
    if application:
        try:
            logger.info("🛑 Stopping Telegram bot...")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("✅ Telegram bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")
    
    # Close MongoDB connection
    if db_client:
        try:
            logger.info("🛑 Closing MongoDB connection...")
            db_client.close()
            logger.info("✅ MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB: {e}")
