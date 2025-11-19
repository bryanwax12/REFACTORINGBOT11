"""
Скрипт очистки админки
Оставляет только пользователя White_Label_Shipping_Bot_Agent
Удаляет все остальные данные
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
TARGET_TELEGRAM_ID = 7066790254  # White_Label_Shipping_Bot_Agent

async def cleanup_database():
    """Очистка базы данных"""
    print("🔌 Подключение к MongoDB...")
    client = AsyncIOMotorClient(MONGO_URL)
    db_name = os.getenv("DB_NAME", "telegram_shipping_bot")
    print(f"📂 Используется БД: {db_name}")
    db = client[db_name]
    
    try:
        # 1. Найти целевого пользователя
        print(f"\n🔍 Поиск пользователя с Telegram ID: {TARGET_TELEGRAM_ID}")
        target_user = await db.users.find_one({"telegram_id": TARGET_TELEGRAM_ID}, {"_id": 0})
        
        if not target_user:
            print("❌ Целевой пользователь не найден!")
            return
        
        print(f"✅ Найден: {target_user.get('username')} (ID: {target_user['id']})")
        
        # 2. Подсчет данных перед удалением
        print("\n📊 Текущее состояние БД:")
        users_count = await db.users.count_documents({})
        orders_count = await db.orders.count_documents({})
        payments_count = await db.payments.count_documents({})
        labels_count = await db.shipping_labels.count_documents({})
        refunds_count = await db.refund_requests.count_documents({})
        
        print(f"  - Пользователей: {users_count}")
        print(f"  - Заказов: {orders_count}")
        print(f"  - Платежей: {payments_count}")
        print(f"  - Лейблов: {labels_count}")
        print(f"  - Запросов на возврат: {refunds_count}")
        
        # 3. Удаление данных других пользователей
        print(f"\n🗑️  Удаление данных всех пользователей кроме {target_user.get('username')}...")
        
        # Удаляем пользователей
        result_users = await db.users.delete_many({"telegram_id": {"$ne": TARGET_TELEGRAM_ID}})
        print(f"  ✅ Удалено пользователей: {result_users.deleted_count}")
        
        # Удаляем заказы других пользователей
        result_orders = await db.orders.delete_many({"telegram_id": {"$ne": TARGET_TELEGRAM_ID}})
        print(f"  ✅ Удалено заказов: {result_orders.deleted_count}")
        
        # Удаляем платежи других пользователей
        result_payments = await db.payments.delete_many({"telegram_id": {"$ne": TARGET_TELEGRAM_ID}})
        print(f"  ✅ Удалено платежей: {result_payments.deleted_count}")
        
        # Удаляем лейблы других пользователей
        result_labels = await db.shipping_labels.delete_many({"telegram_id": {"$ne": TARGET_TELEGRAM_ID}})
        print(f"  ✅ Удалено лейблов: {result_labels.deleted_count}")
        
        # Удаляем запросы на возврат других пользователей
        result_refunds = await db.refund_requests.delete_many({"telegram_id": {"$ne": TARGET_TELEGRAM_ID}})
        print(f"  ✅ Удалено запросов на возврат: {result_refunds.deleted_count}")
        
        # 4. Подсчет данных после удаления
        print("\n📊 Состояние БД после очистки:")
        users_count_after = await db.users.count_documents({})
        orders_count_after = await db.orders.count_documents({})
        payments_count_after = await db.payments.count_documents({})
        labels_count_after = await db.shipping_labels.count_documents({})
        refunds_count_after = await db.refund_requests.count_documents({})
        
        print(f"  - Пользователей: {users_count_after}")
        print(f"  - Заказов: {orders_count_after}")
        print(f"  - Платежей: {payments_count_after}")
        print(f"  - Лейблов: {labels_count_after}")
        print(f"  - Запросов на возврат: {refunds_count_after}")
        
        print("\n✅ Очистка завершена успешно!")
        print(f"✅ Оставлен только пользователь: {target_user.get('username')} (TG ID: {TARGET_TELEGRAM_ID})")
        
    except Exception as e:
        print(f"\n❌ Ошибка при очистке: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()
        print("\n🔌 Соединение с БД закрыто")

if __name__ == "__main__":
    asyncio.run(cleanup_database())
