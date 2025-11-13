"""
Configuration and environment variables for Telegram Shipping Bot
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB Configuration
MONGO_URL = os.environ['MONGO_URL']
mongo_client = AsyncIOMotorClient(
    MONGO_URL,
    maxPoolSize=20,
    minPoolSize=2,
    maxIdleTimeMS=30000,
    waitQueueTimeoutMS=3000,
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=3000
)

# Auto-select database name based on environment
WEBHOOK_BASE_URL = os.environ.get('WEBHOOK_BASE_URL', '')
IS_PRODUCTION = 'crypto-shipping.emergent.host' in WEBHOOK_BASE_URL

if IS_PRODUCTION:
    DB_NAME = os.environ.get('DB_NAME_PRODUCTION', 'async-tg-bot-telegram_shipping_bot')
    print(f"🟢 PRODUCTION DATABASE: {DB_NAME}")
else:
    DB_NAME = os.environ.get('DB_NAME_PREVIEW', os.environ.get('DB_NAME', 'telegram_shipping_bot'))
    print(f"🔵 PREVIEW DATABASE: {DB_NAME}")

db = mongo_client[DB_NAME]

# ShipStation API
SHIPSTATION_API_KEY = os.environ.get('SHIPSTATION_API_KEY', '')

# Admin Configuration
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', '')
ADMIN_TELEGRAM_ID = os.environ.get('ADMIN_TELEGRAM_ID', '')

# Channel Configuration
CHANNEL_INVITE_LINK = os.environ.get('CHANNEL_INVITE_LINK', '')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '')

# Telegram Bot Token - Auto-select based on environment
if IS_PRODUCTION:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN_PRODUCTION', '')
    print(f"🟢 PRODUCTION BOT SELECTED: @whitelabel_shipping_bot")
else:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN_PREVIEW', 
                                       os.environ.get('TELEGRAM_BOT_TOKEN', ''))
    print(f"🔵 PREVIEW BOT SELECTED: @whitelabel_shipping_bot_test_bot")

# Oxapay Configuration
OXAPAY_API_KEY = os.environ.get('OXAPAY_API_KEY', '')
OXAPAY_API_URL = 'https://api.oxapay.com'

# Cache Configuration
# NOTE: SETTINGS_CACHE moved to utils/cache.py to avoid duplication
CACHE_TTL = 60  # seconds

# Rate Limiting
BUTTON_DEBOUNCE_SECONDS = 0.1
RATE_LIMITER_MIN_INTERVAL = 0.01  # 10ms minimum between calls
