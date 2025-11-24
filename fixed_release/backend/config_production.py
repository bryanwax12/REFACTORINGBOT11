"""
Production configuration
Used when environment variables are concatenated or corrupted by deployment platform
"""

PRODUCTION_CONFIG = {
    # MongoDB Atlas M10 (Dedicated) - 10x faster than M0
    'MONGO_URL': 'mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority',
    'ADMIN_API_KEY': 'sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024',
    'WEBHOOK_BASE_URL': 'https://telegram-admin-fix-2.emergent.host',
    'TELEGRAM_BOT_TOKEN': '8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM',
    'SHIPSTATION_API_KEY': 'P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g',
    'SHIPSTATION_API_KEY_TEST': 'TEST_3NFykGjeVRke57QiCtJzEOq2ZVsXBrWgOvCNrwcwGU8',
    'SHIPSTATION_API_KEY_PROD': 'P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g',
}
