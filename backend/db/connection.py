"""Database connection setup"""
import os
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')

client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=20,  # Optimized for Preview environment
    minPoolSize=2,   # Lower minimum for resource efficiency
    maxIdleTimeMS=30000,  # Close idle connections faster
    waitQueueTimeoutMS=3000,  # Shorter wait time
    serverSelectionTimeoutMS=3000,  # Faster timeout
    connectTimeoutMS=3000  # Add connection timeout
)

def get_db():
    """Get database instance"""
    return client[os.environ.get('DB_NAME', 'telegram_shipping_bot')]
