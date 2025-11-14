"""
Database Optimization Script
Adds indexes and analyzes query performance for MongoDB
"""
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_indexes():
    """Create optimal indexes for MongoDB collections"""
    # Get MongoDB connection
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    
    # Get database name from env or use default
    db_name = os.environ.get('MONGODB_DB_NAME', 'telegram_shipping_bot')
    db = client[db_name]
    
    logger.info(f"🔍 Analyzing database: {db_name}")
    
    async def safe_create_index(collection, keys, **kwargs):
        """Safely create index, skip if already exists"""
        try:
            await collection.create_index(keys, **kwargs)
            return True
        except Exception as e:
            if "already exists" in str(e):
                logger.info(f"⏭️  Skipped (already exists): {kwargs.get('name', keys)}")
                return False
            else:
                logger.error(f"❌ Error creating index: {e}")
                return False
    
    # ============================================================
    # USERS COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'users' collection...")
    
    # 1. Unique index on telegram_id (most frequent lookup)
    if await safe_create_index(db.users, "telegram_id", unique=True, name="idx_telegram_id_unique"):
        logger.info("✅ Created unique index: users.telegram_id")
    
    # 2. Index on created_at for analytics
    await db.users.create_index("created_at", name="idx_created_at")
    logger.info("✅ Created index: users.created_at")
    
    # 3. Compound index for balance queries
    await db.users.create_index([("telegram_id", 1), ("balance", -1)], name="idx_telegram_balance")
    logger.info("✅ Created compound index: users.telegram_id + balance")
    
    # ============================================================
    # ORDERS COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'orders' collection...")
    
    # 1. Compound index on telegram_id + created_at (for user order history)
    await db.orders.create_index(
        [("telegram_id", 1), ("created_at", -1)],
        name="idx_user_orders"
    )
    logger.info("✅ Created compound index: orders.telegram_id + created_at")
    
    # 2. Index on order id (unique)
    await db.orders.create_index("id", unique=True, name="idx_order_id_unique")
    logger.info("✅ Created unique index: orders.id")
    
    # 3. Index on payment_status for filtering
    await db.orders.create_index("payment_status", name="idx_payment_status")
    logger.info("✅ Created index: orders.payment_status")
    
    # 4. Index on shipping_status
    await db.orders.create_index("shipping_status", name="idx_shipping_status")
    logger.info("✅ Created index: orders.shipping_status")
    
    # 5. Compound index for admin queries
    await db.orders.create_index(
        [("payment_status", 1), ("created_at", -1)],
        name="idx_payment_date"
    )
    logger.info("✅ Created compound index: orders.payment_status + created_at")
    
    # ============================================================
    # TEMPLATES COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'templates' collection...")
    
    # 1. Compound index on telegram_id + created_at
    await db.templates.create_index(
        [("telegram_id", 1), ("created_at", -1)],
        name="idx_user_templates"
    )
    logger.info("✅ Created compound index: templates.telegram_id + created_at")
    
    # 2. Unique index on template id
    await db.templates.create_index("id", unique=True, name="idx_template_id_unique")
    logger.info("✅ Created unique index: templates.id")
    
    # 3. Index on name for search
    await db.templates.create_index("name", name="idx_template_name")
    logger.info("✅ Created index: templates.name")
    
    # ============================================================
    # SESSIONS COLLECTION INDEXES (for SessionManager)
    # ============================================================
    logger.info("\n📊 Creating indexes for 'user_sessions' collection...")
    
    # 1. Unique index on user_id
    await db.user_sessions.create_index("user_id", unique=True, name="idx_user_id_unique")
    logger.info("✅ Created unique index: user_sessions.user_id")
    
    # 2. TTL index on last_updated (auto-cleanup after 30 minutes)
    await db.user_sessions.create_index(
        "last_updated",
        expireAfterSeconds=1800,  # 30 minutes
        name="idx_session_ttl"
    )
    logger.info("✅ Created TTL index: user_sessions.last_updated (30 min expiry)")
    
    # ============================================================
    # PAYMENTS COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'payments' collection...")
    
    # 1. Index on telegram_id + created_at
    await db.payments.create_index(
        [("telegram_id", 1), ("created_at", -1)],
        name="idx_user_payments"
    )
    logger.info("✅ Created compound index: payments.telegram_id + created_at")
    
    # 2. Index on invoice_id (for webhook lookups)
    await db.payments.create_index("invoice_id", name="idx_invoice_id")
    logger.info("✅ Created index: payments.invoice_id")
    
    # 3. Index on status
    await db.payments.create_index("status", name="idx_payment_status")
    logger.info("✅ Created index: payments.status")
    
    # 4. Index on order_id
    await db.payments.create_index("order_id", name="idx_order_id")
    logger.info("✅ Created index: payments.order_id")
    
    # ============================================================
    # PENDING ORDERS COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'pending_orders' collection...")
    
    # 1. Unique index on telegram_id (only one pending order per user)
    await db.pending_orders.create_index("telegram_id", unique=True, name="idx_pending_user_unique")
    logger.info("✅ Created unique index: pending_orders.telegram_id")
    
    # 2. TTL index for auto-cleanup (1 hour)
    await db.pending_orders.create_index(
        "created_at",
        expireAfterSeconds=3600,  # 1 hour
        name="idx_pending_ttl"
    )
    logger.info("✅ Created TTL index: pending_orders.created_at (1 hour expiry)")
    
    # ============================================================
    # ANALYZE EXISTING INDEXES
    # ============================================================
    logger.info("\n📊 Analyzing created indexes...")
    
    collections = ['users', 'orders', 'templates', 'user_sessions', 'payments', 'pending_orders']
    for coll_name in collections:
        indexes = await db[coll_name].list_indexes().to_list(length=None)
        logger.info(f"\n✅ {coll_name} indexes ({len(indexes)} total):")
        for idx in indexes:
            logger.info(f"   - {idx.get('name')}: {idx.get('key')}")
    
    # ============================================================
    # COLLECTION STATS
    # ============================================================
    logger.info("\n📊 Collection Statistics:")
    for coll_name in collections:
        count = await db[coll_name].count_documents({})
        logger.info(f"   {coll_name}: {count} documents")
    
    logger.info("\n✅ Database optimization complete!")
    client.close()


async def analyze_slow_queries():
    """Analyze and log slow queries"""
    logger.info("\n🔍 Analyzing query patterns...")
    
    # Get MongoDB connection
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    
    db_name = os.environ.get('MONGODB_DB_NAME', 'telegram_shipping_bot')
    db = client[db_name]
    
    # Enable profiling for slow queries (queries > 100ms)
    await db.command('profile', 1, slowms=100)
    logger.info("✅ Enabled query profiling (threshold: 100ms)")
    
    client.close()


if __name__ == "__main__":
    print("🚀 Starting database optimization...\n")
    asyncio.run(create_indexes())
    asyncio.run(analyze_slow_queries())
    print("\n✅ Optimization complete!")
