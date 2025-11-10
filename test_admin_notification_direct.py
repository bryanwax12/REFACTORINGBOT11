#!/usr/bin/env python3
"""
Direct test of admin notification for a created label
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timezone

# Add backend to path
sys.path.append('/app/backend')

# Load environment
load_dotenv('/app/backend/.env')

async def test_admin_notification():
    """Test sending admin notification for the recently created label"""
    from motor.motor_asyncio import AsyncIOMotorClient
    from telegram import Bot
    
    print("🔍 Testing admin notification for recently created label...")
    
    # MongoDB connection
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    ADMIN_TELEGRAM_ID = os.environ.get('ADMIN_TELEGRAM_ID')
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not ADMIN_TELEGRAM_ID:
        print("❌ ADMIN_TELEGRAM_ID not set in .env")
        return False
    
    print(f"✅ Admin Telegram ID: {ADMIN_TELEGRAM_ID}")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Get the latest label
    label = await db.shipping_labels.find_one(
        sort=[('created_at', -1)],
        projection={"_id": 0}
    )
    
    if not label:
        print("❌ No labels found in database")
        client.close()
        return False
    
    print(f"\n📋 Found Label:")
    print(f"   Tracking: {label.get('tracking_number')}")
    print(f"   Order ID: {label.get('order_id')}")
    
    # Get the corresponding order
    order = await db.orders.find_one(
        {'id': label['order_id']},
        {"_id": 0}
    )
    
    if not order:
        print("❌ Order not found for this label")
        client.close()
        return False
    
    # Get user info
    user = await db.users.find_one(
        {"telegram_id": order['telegram_id']},
        {"_id": 0}
    )
    
    if not user:
        print("❌ User not found")
        client.close()
        return False
    
    print(f"✅ Found Order and User")
    print(f"   User: {user.get('first_name', 'Unknown')}")
    print(f"   Amount: ${order.get('amount', 0):.2f}")
    
    # Format admin notification message
    user_name = user.get('first_name', 'Unknown')
    username = user.get('username', '')
    telegram_id = user.get('telegram_id')
    user_display = f"{user_name}" + (f" (@{username})" if username else f" (ID: {telegram_id})")
    
    admin_message = f"""📦 *Новый лейбл создан!*

👤 *Пользователь:* {user_display}

📤 *От:* {order['address_from']['name']}
   {order['address_from']['street1']}, {order['address_from']['city']}, {order['address_from']['state']} {order['address_from']['zip']}

📥 *Кому:* {order['address_to']['name']}  
   {order['address_to']['street1']}, {order['address_to']['city']}, {order['address_to']['state']} {order['address_to']['zip']}

🚚 *Перевозчик:* {order['selected_carrier']} - {order['selected_service']}
📋 *Трекинг:* `{label['tracking_number']}`
💰 *Цена:* ${order['amount']:.2f}
⚖️ *Вес:* {order['parcel']['weight']} lb

🕐 *Время:* {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}"""
    
    print(f"\n📧 Message to send to admin:")
    print("="*60)
    print(admin_message.replace('*', ''))
    print("="*60)
    
    # Initialize bot and send message
    try:
        bot = Bot(TELEGRAM_BOT_TOKEN)
        
        print(f"\n📤 Sending notification to admin {ADMIN_TELEGRAM_ID}...")
        
        message = await bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=admin_message,
            parse_mode='Markdown'
        )
        
        print(f"\n✅ NOTIFICATION SENT SUCCESSFULLY!")
        print(f"   Message ID: {message.message_id}")
        print(f"   Chat ID: {message.chat_id}")
        print(f"   Date: {message.date}")
        
        print(f"\n🎉 ADMIN NOTIFICATION TEST PASSED!")
        print(f"💡 Check Telegram messages for admin ID {ADMIN_TELEGRAM_ID}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to send notification: {e}")
        import traceback
        traceback.print_exc()
        client.close()
        return False

if __name__ == '__main__':
    result = asyncio.run(test_admin_notification())
    sys.exit(0 if result else 1)
