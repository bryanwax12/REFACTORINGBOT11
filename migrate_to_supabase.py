"""
Migration script from MongoDB Atlas to Supabase PostgreSQL
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
import asyncpg
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection (source)
MONGO_URL = "mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority"

# Supabase connection (destination) - will be provided by user
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')


async def migrate_users(mongo_db, pg_conn):
    """Migrate users collection to PostgreSQL"""
    logger.info("📦 Migrating users...")
    
    users = await mongo_db.users.find({}, {"_id": 0}).to_list(1000)
    
    for user in users:
        try:
            await pg_conn.execute('''
                INSERT INTO users (
                    telegram_id, username, first_name, last_name,
                    balance, blocked, is_channel_member, 
                    channel_status_checked_at, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    balance = EXCLUDED.balance,
                    blocked = EXCLUDED.blocked
            ''', 
                user.get('telegram_id'),
                user.get('username'),
                user.get('first_name'),
                user.get('last_name'),
                user.get('balance', 0.0),
                user.get('blocked', False),
                user.get('is_channel_member', False),
                user.get('channel_status_checked_at')
            )
        except Exception as e:
            logger.error(f"Error migrating user {user.get('telegram_id')}: {e}")
    
    logger.info(f"✅ Migrated {len(users)} users")


async def migrate_orders(mongo_db, pg_conn):
    """Migrate orders collection to PostgreSQL"""
    logger.info("📦 Migrating orders...")
    
    orders = await mongo_db.orders.find({}, {"_id": 0}).to_list(1000)
    
    for order in orders:
        try:
            await pg_conn.execute('''
                INSERT INTO orders (
                    order_id, telegram_id, from_name, from_company,
                    from_street1, from_street2, from_city, from_state,
                    from_zip, from_country, from_phone,
                    to_name, to_company, to_street1, to_street2,
                    to_city, to_state, to_zip, to_country, to_phone,
                    weight, length, width, height, service_code,
                    label_url, tracking_number, shipment_cost, status,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                        $13, $14, $15, $16, $17, $18, $19, $20, $21, $22,
                        $23, $24, $25, $26, $27, $28, $29, NOW())
                ON CONFLICT (order_id) DO NOTHING
            ''',
                order.get('order_id'),
                order.get('telegram_id'),
                order.get('from_name'),
                order.get('from_company'),
                order.get('from_street1'),
                order.get('from_street2'),
                order.get('from_city'),
                order.get('from_state'),
                order.get('from_zip'),
                order.get('from_country', 'US'),
                order.get('from_phone'),
                order.get('to_name'),
                order.get('to_company'),
                order.get('to_street1'),
                order.get('to_street2'),
                order.get('to_city'),
                order.get('to_state'),
                order.get('to_zip'),
                order.get('to_country', 'US'),
                order.get('to_phone'),
                order.get('weight'),
                order.get('length'),
                order.get('width'),
                order.get('height'),
                order.get('service_code'),
                order.get('label_url'),
                order.get('tracking_number'),
                order.get('shipment_cost'),
                order.get('status', 'pending')
            )
        except Exception as e:
            logger.error(f"Error migrating order {order.get('order_id')}: {e}")
    
    logger.info(f"✅ Migrated {len(orders)} orders")


async def migrate_payments(mongo_db, pg_conn):
    """Migrate payments collection to PostgreSQL"""
    logger.info("📦 Migrating payments...")
    
    payments = await mongo_db.payments.find({}, {"_id": 0}).to_list(1000)
    
    for payment in payments:
        try:
            await pg_conn.execute('''
                INSERT INTO payments (
                    payment_id, telegram_id, amount, currency,
                    status, payment_method, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (payment_id) DO NOTHING
            ''',
                payment.get('payment_id'),
                payment.get('telegram_id'),
                payment.get('amount'),
                payment.get('currency', 'USD'),
                payment.get('status', 'pending'),
                payment.get('payment_method')
            )
        except Exception as e:
            logger.error(f"Error migrating payment {payment.get('payment_id')}: {e}")
    
    logger.info(f"✅ Migrated {len(payments)} payments")


async def migrate_settings(mongo_db, pg_conn):
    """Migrate settings collection to PostgreSQL"""
    logger.info("📦 Migrating settings...")
    
    settings = await mongo_db.settings.find({}, {"_id": 0}).to_list(100)
    
    for setting in settings:
        try:
            await pg_conn.execute('''
                INSERT INTO settings (key, value, created_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            ''',
                setting.get('key'),
                str(setting.get('value'))
            )
        except Exception as e:
            logger.error(f"Error migrating setting {setting.get('key')}: {e}")
    
    logger.info(f"✅ Migrated {len(settings)} settings")


async def main():
    """Main migration function"""
    if not SUPABASE_URL:
        print("❌ Error: SUPABASE_URL environment variable not set")
        print("Usage: SUPABASE_URL='postgresql://...' python migrate_to_supabase.py")
        return
    
    logger.info("🚀 Starting migration from MongoDB to Supabase...")
    
    # Connect to MongoDB
    logger.info("Connecting to MongoDB Atlas...")
    mongo_client = AsyncIOMotorClient(MONGO_URL)
    mongo_db = mongo_client.telegram_shipping_bot
    
    # Connect to Supabase PostgreSQL
    logger.info("Connecting to Supabase PostgreSQL...")
    pg_conn = await asyncpg.connect(SUPABASE_URL)
    
    try:
        # Migrate data
        await migrate_users(mongo_db, pg_conn)
        await migrate_orders(mongo_db, pg_conn)
        await migrate_payments(mongo_db, pg_conn)
        await migrate_settings(mongo_db, pg_conn)
        
        logger.info("🎉 Migration completed successfully!")
        
        # Show statistics
        user_count = await pg_conn.fetchval('SELECT COUNT(*) FROM users')
        order_count = await pg_conn.fetchval('SELECT COUNT(*) FROM orders')
        payment_count = await pg_conn.fetchval('SELECT COUNT(*) FROM payments')
        
        logger.info(f"📊 Final counts:")
        logger.info(f"   Users: {user_count}")
        logger.info(f"   Orders: {order_count}")
        logger.info(f"   Payments: {payment_count}")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        await pg_conn.close()
        mongo_client.close()


if __name__ == "__main__":
    asyncio.run(main())
