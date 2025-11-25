"""
Database Configuration with Dual MongoDB Support
Workaround for Emergent deployment MongoDB migration issue
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
import logging

logger = logging.getLogger(__name__)


def get_mongodb_client():
    """
    Get MongoDB client with fallback logic
    
    Priority:
    1. EXTERNAL_MONGO_URL - Our external MongoDB Atlas (production data)
    2. MONGO_URL - Fallback or Emergent managed (for migration only)
    """
    # Primary: External MongoDB Atlas (our actual database)
    external_mongo_url = os.environ.get('EXTERNAL_MONGO_URL')
    
    # Fallback: Platform provided or standard MONGO_URL
    mongo_url = os.environ.get('MONGO_URL')
    
    # Use external if available, otherwise fallback
    connection_url = external_mongo_url or mongo_url
    
    if not connection_url:
        logger.error("No MongoDB connection string found!")
        raise ValueError("EXTERNAL_MONGO_URL or MONGO_URL must be set")
    
    # Log which database we're using (without exposing credentials)
    if external_mongo_url:
        logger.info("✅ Using EXTERNAL MongoDB Atlas (production)")
    else:
        logger.warning("⚠️ Using fallback MONGO_URL")
    
    # Create client
    from config.performance_config import BotPerformanceConfig
    mongodb_config = BotPerformanceConfig.get_mongodb_config()
    
    client = AsyncIOMotorClient(
        connection_url,
        maxPoolSize=mongodb_config['maxPoolSize'],
        minPoolSize=mongodb_config['minPoolSize'],
        maxIdleTimeMS=mongodb_config['maxIdleTimeMS'],
        serverSelectionTimeoutMS=mongodb_config['serverSelectionTimeoutMS'],
        connectTimeoutMS=mongodb_config['connectTimeoutMS'],
        socketTimeoutMS=mongodb_config['socketTimeoutMS']
    )
    
    return client


def get_database_name():
    """Get database name with fallback"""
    # Try external DB name first
    db_name = os.environ.get('EXTERNAL_DB_NAME') or os.environ.get('DB_NAME', 'telegram_shipping_bot')
    return db_name
