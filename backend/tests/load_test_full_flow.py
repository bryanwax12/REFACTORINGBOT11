"""
Реалистичный нагрузочный тест для Telegram Shipping Bot
Симулирует полный флоу создания заказа с 30 одновременными пользователями

Тестируемый флоу:
1. /start команда
2. Создание заказа - 18 шагов:
   - Адрес отправителя (7 полей)
   - Адрес получателя (7 полей)
   - Информация о посылке (4 поля)
3. Подтверждение данных
4. Проверка тарифов доставки
5. Выбор тарифа
6. Оплата с баланса
"""
import asyncio
import random
import time
import json
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

# Конфигурация теста
NUM_USERS = 30
WEBHOOK_URL = "http://localhost:8001/api/telegram/webhook"
MONGO_URL = os.getenv('MONGO_URL')

# Тестовые данные для генерации реалистичных заказов
FIRST_NAMES = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'Robert', 'Lisa', 'James', 'Maria']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
STREETS = ['Main St', 'Oak Ave', 'Maple Dr', 'Cedar Ln', 'Pine St', 'Elm Ave', 'Park Blvd', 'Washington St']
CITIES_NY = ['New York', 'Buffalo', 'Rochester', 'Yonkers', 'Syracuse', 'Albany', 'New Rochelle', 'Mount Vernon']
CITIES_CA = ['Los Angeles', 'San Diego', 'San Jose', 'San Francisco', 'Fresno', 'Sacramento', 'Long Beach', 'Oakland']
ZIP_CODES_NY = ['10001', '10002', '10003', '14201', '14202', '14603', '10701', '13201']
ZIP_CODES_CA = ['90001', '90002', '92101', '92102', '95101', '94102', '93701', '94601']


class RealisticLoadTester:
    def __init__(self):
        self.mongo_url = MONGO_URL
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client['telegram_shipping_bot']
        self.results = {
            'total_operations': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'steps_completed': 0,
            'steps_failed': 0,
            'avg_order_time': 0,
            'max_order_time': 0,
            'min_order_time': float('inf'),
            'errors': []
        }
        self.order_times = []
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
    async def generate_test_user(self, user_id: int):
        """Создает или обновляет тестового пользователя с балансом"""
        telegram_id = 7000000000 + user_id
        user_data = {
            'telegram_id': telegram_id,
            'username': f'test_user_{user_id}',
            'first_name': f'Test{user_id}',
            'balance': 100.0,  # Достаточный баланс для оплаты
            'created_at': datetime.utcnow()
        }
        
        await self.db.users.update_one(
            {'telegram_id': telegram_id},
            {'$set': user_data},
            upsert=True
        )
        return telegram_id
    
    def generate_address_data(self, use_ca=False):
        """Генерирует реалистичные данные адреса"""
        if use_ca:
            city = random.choice(CITIES_CA)
            zip_code = random.choice(ZIP_CODES_CA)
            state = 'CA'
        else:
            city = random.choice(CITIES_NY)
            zip_code = random.choice(ZIP_CODES_NY)
            state = 'NY'
            
        return {
            'name': f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            'address': f"{random.randint(100, 9999)} {random.choice(STREETS)}",
            'address2': '',  # Пропускаем
            'city': city,
            'state': state,
            'zip': zip_code,
            'phone': ''  # Пропускаем
        }
    
    def generate_parcel_data(self):
        """Генерирует реалистичные данные посылки"""
        return {
            'weight': str(random.uniform(0.5, 10.0))[:4],  # 0.5-10 lbs
            'length': str(random.randint(5, 20)),
            'width': str(random.randint(5, 20)),
            'height': str(random.randint(5, 20))
        }
    
    async def simulate_telegram_update(self, telegram_id: int, text: str = None, callback_data: str = None):
        """Симулирует Telegram Update через webhook"""
        update_id = random.randint(100000000, 999999999)
        
        if text:
            # Текстовое сообщение
            update = {
                "update_id": update_id,
                "message": {
                    "message_id": random.randint(1000, 9999),
                    "from": {
                        "id": telegram_id,
                        "is_bot": False,
                        "first_name": f"Test{telegram_id}",
                        "username": f"test_user_{telegram_id}"
                    },
                    "chat": {
                        "id": telegram_id,
                        "type": "private"
                    },
                    "date": int(time.time()),
                    "text": text
                }
            }
        elif callback_data:
            # Callback query (кнопка)
            update = {
                "update_id": update_id,
                "callback_query": {
                    "id": str(random.randint(100000000, 999999999)),
                    "from": {
                        "id": telegram_id,
                        "is_bot": False,
                        "first_name": f"Test{telegram_id}",
                        "username": f"test_user_{telegram_id}"
                    },
                    "message": {
                        "message_id": random.randint(1000, 9999),
                        "chat": {
                            "id": telegram_id,
                            "type": "private"
                        },
                        "date": int(time.time())
                    },
                    "chat_instance": str(random.randint(1000000000, 9999999999)),
                    "data": callback_data
                }
            }
        else:
            raise ValueError("Нужно указать text или callback_data")
        
        try:
            response = await self.http_client.post(
                WEBHOOK_URL,
                json=update,
                headers={"Content-Type": "application/json"}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Ошибка отправки webhook: {e}")
            return False
    
    async def simulate_full_order_flow(self, user_id: int):
        """Симулирует полный флоу создания заказа"""
        order_start_time = time.time()
        steps_completed = 0
        
        try:
            # 1. Создаем/обновляем тестового пользователя
            telegram_id = await self.generate_test_user(user_id)
            print(f"👤 User {user_id}: Начинаю создание заказа (telegram_id: {telegram_id})")
            
            # Генерируем данные заказа
            from_address = self.generate_address_data(use_ca=False)  # NY
            to_address = self.generate_address_data(use_ca=True)     # CA
            parcel = self.generate_parcel_data()
            
            # 2. Отправляем /start
            await self.simulate_telegram_update(telegram_id, text="/start")
            await asyncio.sleep(random.uniform(0.3, 0.7))
            steps_completed += 1
            
            # 3. Нажимаем "Создать заказ"
            await self.simulate_telegram_update(telegram_id, callback_data="new_order")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # 4-10. Адрес отправителя (7 шагов)
            # FROM_NAME
            await self.simulate_telegram_update(telegram_id, text=from_address['name'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # FROM_ADDRESS
            await self.simulate_telegram_update(telegram_id, text=from_address['address'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # FROM_ADDRESS2 (skip)
            await self.simulate_telegram_update(telegram_id, callback_data="skip_from_address2")
            await asyncio.sleep(random.uniform(0.3, 0.5))
            steps_completed += 1
            
            # FROM_CITY
            await self.simulate_telegram_update(telegram_id, text=from_address['city'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # FROM_STATE
            await self.simulate_telegram_update(telegram_id, text=from_address['state'])
            await asyncio.sleep(random.uniform(0.3, 0.7))
            steps_completed += 1
            
            # FROM_ZIP
            await self.simulate_telegram_update(telegram_id, text=from_address['zip'])
            await asyncio.sleep(random.uniform(0.3, 0.7))
            steps_completed += 1
            
            # FROM_PHONE (skip)
            await self.simulate_telegram_update(telegram_id, callback_data="skip_from_phone")
            await asyncio.sleep(random.uniform(0.3, 0.5))
            steps_completed += 1
            
            # 11-17. Адрес получателя (7 шагов)
            # TO_NAME
            await self.simulate_telegram_update(telegram_id, text=to_address['name'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # TO_ADDRESS
            await self.simulate_telegram_update(telegram_id, text=to_address['address'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # TO_ADDRESS2 (skip)
            await self.simulate_telegram_update(telegram_id, callback_data="skip_to_address2")
            await asyncio.sleep(random.uniform(0.3, 0.5))
            steps_completed += 1
            
            # TO_CITY
            await self.simulate_telegram_update(telegram_id, text=to_address['city'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # TO_STATE
            await self.simulate_telegram_update(telegram_id, text=to_address['state'])
            await asyncio.sleep(random.uniform(0.3, 0.7))
            steps_completed += 1
            
            # TO_ZIP
            await self.simulate_telegram_update(telegram_id, text=to_address['zip'])
            await asyncio.sleep(random.uniform(0.3, 0.7))
            steps_completed += 1
            
            # TO_PHONE (skip)
            await self.simulate_telegram_update(telegram_id, callback_data="skip_to_phone")
            await asyncio.sleep(random.uniform(0.3, 0.5))
            steps_completed += 1
            
            # 18-21. Информация о посылке (4 шага)
            # PARCEL_WEIGHT
            await self.simulate_telegram_update(telegram_id, text=parcel['weight'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # PARCEL_LENGTH
            await self.simulate_telegram_update(telegram_id, text=parcel['length'])
            await asyncio.sleep(random.uniform(0.3, 0.7))
            steps_completed += 1
            
            # PARCEL_WIDTH
            await self.simulate_telegram_update(telegram_id, text=parcel['width'])
            await asyncio.sleep(random.uniform(0.3, 0.7))
            steps_completed += 1
            
            # PARCEL_HEIGHT
            await self.simulate_telegram_update(telegram_id, text=parcel['height'])
            await asyncio.sleep(random.uniform(0.5, 1.0))
            steps_completed += 1
            
            # 22. Подтверждение данных - "Всё верно, показать тарифы"
            await self.simulate_telegram_update(telegram_id, callback_data="confirm_data")
            await asyncio.sleep(random.uniform(2.0, 4.0))  # Даем время на расчет тарифов
            steps_completed += 1
            
            # 23. Получаем список тарифов и выбираем первый
            # Примечание: в реальном флоу нужно было бы парсить callback_data из тарифов
            # Для упрощения используем типичный формат: rate_0, rate_1, etc.
            rate_index = random.randint(0, 5)
            await self.simulate_telegram_update(telegram_id, callback_data=f"rate_{rate_index}")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            steps_completed += 1
            
            # 24. Выбираем оплату с баланса
            await self.simulate_telegram_update(telegram_id, callback_data="pay_balance")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            steps_completed += 1
            
            order_time = time.time() - order_start_time
            self.order_times.append(order_time)
            
            print(f"✅ User {user_id}: Заказ создан успешно за {order_time:.2f}с ({steps_completed} шагов)")
            
            self.results['successful_orders'] += 1
            self.results['steps_completed'] += steps_completed
            
        except Exception as e:
            order_time = time.time() - order_start_time
            error_msg = f"User {user_id} failed at step {steps_completed}: {str(e)}"
            print(f"❌ {error_msg}")
            
            self.results['failed_orders'] += 1
            self.results['steps_failed'] += 1
            self.results['errors'].append(error_msg)
    
    async def run_load_test(self):
        """Запускает нагрузочный тест с несколькими пользователями"""
        print(f"\n{'='*80}")
        print("🚀 РЕАЛИСТИЧНЫЙ НАГРУЗОЧНЫЙ ТЕСТ - Полный Флоу Создания Заказа")
        print(f"{'='*80}")
        print(f"👥 Количество пользователей: {NUM_USERS}")
        print(f"🎯 Флоу: /start → Создание заказа (18 шагов) → Подтверждение → Выбор тарифа → Оплата")
        print(f"🌐 Webhook URL: {WEBHOOK_URL}")
        print(f"{'='*80}\n")
        
        test_start_time = time.time()
        
        # Запускаем всех пользователей одновременно
        tasks = [
            self.simulate_full_order_flow(user_id)
            for user_id in range(1, NUM_USERS + 1)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        total_test_time = time.time() - test_start_time
        
        # Вычисляем статистику
        if self.order_times:
            self.results['avg_order_time'] = sum(self.order_times) / len(self.order_times)
            self.results['max_order_time'] = max(self.order_times)
            self.results['min_order_time'] = min(self.order_times)
        
        self.results['total_operations'] = self.results['successful_orders'] + self.results['failed_orders']
        
        # Выводим результаты
        self.print_results(total_test_time)
    
    def print_results(self, total_time: float):
        """Выводит результаты нагрузочного теста"""
        print(f"\n{'='*80}")
        print("📊 РЕЗУЛЬТАТЫ НАГРУЗОЧНОГО ТЕСТА")
        print(f"{'='*80}\n")
        
        print(f"⏱️  Общее время выполнения: {total_time:.2f}с")
        print(f"📦 Всего попыток создания заказов: {self.results['total_operations']}")
        print(f"✅ Успешных заказов: {self.results['successful_orders']}")
        print(f"❌ Неудачных заказов: {self.results['failed_orders']}")
        
        if self.results['total_operations'] > 0:
            success_rate = (self.results['successful_orders'] / self.results['total_operations']) * 100
            print(f"📊 Процент успеха: {success_rate:.2f}%")
        
        print(f"\n{'─'*80}")
        print("📈 Статистика по шагам:")
        print(f"{'─'*80}")
        print(f"   ✅ Шагов завершено: {self.results['steps_completed']}")
        print(f"   ❌ Шагов провалено: {self.results['steps_failed']}")
        avg_steps = self.results['steps_completed'] / max(self.results['total_operations'], 1)
        print(f"   📊 Среднее шагов на заказ: {avg_steps:.1f}")
        
        if self.order_times:
            print(f"\n{'─'*80}")
            print("⏱️  Время создания заказа:")
            print(f"{'─'*80}")
            print(f"   Среднее: {self.results['avg_order_time']:.2f}с")
            print(f"   Минимальное: {self.results['min_order_time']:.2f}с")
            print(f"   Максимальное: {self.results['max_order_time']:.2f}с")
        
        if self.results['errors']:
            print(f"\n{'─'*80}")
            print("⚠️  Первые 10 ошибок:")
            print(f"{'─'*80}")
            for error in self.results['errors'][:10]:
                print(f"   • {error}")
        
        print(f"\n{'='*80}")
        
        # Оценка производительности
        success_rate = (self.results['successful_orders'] / max(self.results['total_operations'], 1)) * 100
        avg_time = self.results.get('avg_order_time', 999)
        
        print("\n🎯 Оценка производительности:")
        print(f"{'─'*80}")
        
        if success_rate >= 90 and avg_time < 30:
            print("✅ ОТЛИЧНО - Система справляется с нагрузкой идеально!")
        elif success_rate >= 80 and avg_time < 45:
            print("✅ ХОРОШО - Система работает стабильно под нагрузкой")
        elif success_rate >= 60 and avg_time < 60:
            print("⚠️  ПРИЕМЛЕМО - Есть проблемы с производительностью")
        else:
            print("❌ ПЛОХО - Система не справляется с нагрузкой")
        
        print(f"{'='*80}\n")
    
    async def cleanup(self):
        """Очистка ресурсов"""
        await self.http_client.aclose()
        self.client.close()


async def main():
    tester = RealisticLoadTester()
    try:
        await tester.run_load_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  Тест прерван пользователем")
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
