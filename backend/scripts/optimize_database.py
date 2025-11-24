"""
Database Optimization Script
Adds indexes and analyzes query performance for MongoDB
"""
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
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
    if await safe_create_index(db.users, "created_at", name="idx_users_created_at"):
        logger.info("✅ Created index: users.created_at")
    
    # 3. Compound index for balance queries
    if await safe_create_index(db.users, [("telegram_id", 1), ("balance", -1)], name="idx_telegram_balance"):
        logger.info("✅ Created compound index: users.telegram_id + balance")
    
    # ============================================================
    # ORDERS COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'orders' collection...")
    
    # 1. Compound index on telegram_id + created_at (for user order history)
    if await safe_create_index(db.orders, [("telegram_id", 1), ("created_at", -1)], name="idx_user_orders"):
        logger.info("✅ Created compound index: orders.telegram_id + created_at")
    
    # 2. Index on order id (unique)
    if await safe_create_index(db.orders, "id", unique=True, name="idx_order_id_unique"):
        logger.info("✅ Created unique index: orders.id")
    
    # 3. Index on payment_status for filtering
    if await safe_create_index(db.orders, "payment_status", name="idx_orders_payment_status"):
        logger.info("✅ Created index: orders.payment_status")
    
    # 4. Index on shipping_status
    if await safe_create_index(db.orders, "shipping_status", name="idx_shipping_status"):
        logger.info("✅ Created index: orders.shipping_status")
    
    # 5. Compound index for admin queries
    if await safe_create_index(db.orders, [("payment_status", 1), ("created_at", -1)], name="idx_payment_date"):
        logger.info("✅ Created compound index: orders.payment_status + created_at")
    
    # ============================================================
    # TEMPLATES COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'templates' collection...")
    
    # 1. Compound index on telegram_id + created_at
    if await safe_create_index(db.templates, [("telegram_id", 1), ("created_at", -1)], name="idx_user_templates"):
        logger.info("✅ Created compound index: templates.telegram_id + created_at")
    
    # 2. Unique index on template id
    if await safe_create_index(db.templates, "id", unique=True, name="idx_template_id_unique"):
        logger.info("✅ Created unique index: templates.id")
    
    # 3. Index on name for search
    if await safe_create_index(db.templates, "name", name="idx_template_name"):
        logger.info("✅ Created index: templates.name")
    
    # ============================================================
    # SESSIONS COLLECTION INDEXES (for SessionManager)
    # ============================================================
    logger.info("\n📊 Creating indexes for 'user_sessions' collection...")
    
    # 1. Unique index on user_id
    if await safe_create_index(db.user_sessions, "user_id", unique=True, name="idx_user_id_unique"):
        logger.info("✅ Created unique index: user_sessions.user_id")
    
    # 2. TTL index on last_updated (auto-cleanup after 60 minutes)
    if await safe_create_index(db.user_sessions, "last_updated", expireAfterSeconds=3600, name="idx_session_ttl"):
        logger.info("✅ Created TTL index: user_sessions.last_updated (60 min expiry)")
    
    # ============================================================
    # PAYMENTS COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'payments' collection...")
    
    # 1. Index on telegram_id + created_at
    if await safe_create_index(db.payments, [("telegram_id", 1), ("created_at", -1)], name="idx_user_payments"):
        logger.info("✅ Created compound index: payments.telegram_id + created_at")
    
    # 2. Index on invoice_id (for webhook lookups)
    if await safe_create_index(db.payments, "invoice_id", name="idx_invoice_id"):
        logger.info("✅ Created index: payments.invoice_id")
    
    # 3. Index on status
    if await safe_create_index(db.payments, "status", name="idx_payments_status"):
        logger.info("✅ Created index: payments.status")
    
    # 4. Index on order_id
    if await safe_create_index(db.payments, "order_id", name="idx_payments_order_id"):
        logger.info("✅ Created index: payments.order_id")
    
    # ============================================================
    # PENDING ORDERS COLLECTION INDEXES
    # ============================================================
    logger.info("\n📊 Creating indexes for 'pending_orders' collection...")
    
    # 1. Unique index on telegram_id (only one pending order per user)
    if await safe_create_index(db.pending_orders, "telegram_id", unique=True, name="idx_pending_user_unique"):
        logger.info("✅ Created unique index: pending_orders.telegram_id")
    
    # 2. TTL index for auto-cleanup (1 hour)
    if await safe_create_index(db.pending_orders, "created_at", expireAfterSeconds=3600, name="idx_pending_ttl"):
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
