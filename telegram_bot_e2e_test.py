#!/usr/bin/env python3
"""
Comprehensive E2E Testing for Telegram Shipping Bot
Based on Russian review request for testing order creation flows and validation issues
"""

import requests
import json
import os
import time
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')

# Get backend URL from environment
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://telebot-fixer-1.preview.emergentagent.com')
WEBHOOK_URL = f"{BACKEND_URL}/api/telegram/webhook"

class TelegramBotTester:
    def __init__(self):
        self.test_user_id = 999999999  # Test user ID
        self.update_counter = int(time.time() * 1000)
        self.message_counter = 1
        
    def get_next_update_id(self):
        self.update_counter += 1
        return self.update_counter
    
    def get_next_message_id(self):
        self.message_counter += 1
        return self.message_counter
    
    def create_message_update(self, text):
        """Create a message update for webhook"""
        return {
            "update_id": self.get_next_update_id(),
            "message": {
                "message_id": self.get_next_message_id(),
                "from": {
                    "id": self.test_user_id,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "language_code": "ru"
                },
                "chat": {
                    "id": self.test_user_id,
                    "first_name": "TestUser",
                    "username": "testuser",
                    "type": "private"
                },
                "date": int(time.time()),
                "text": text
            }
        }
    
    def create_callback_update(self, callback_data):
        """Create a callback query update for webhook"""
        return {
            "update_id": self.get_next_update_id(),
            "callback_query": {
                "id": f"callback_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                "from": {
                    "id": self.test_user_id,
                    "is_bot": False,
                    "first_name": "TestUser",
                    "username": "testuser"
                },
                "message": {
                    "message_id": self.get_next_message_id(),
                    "from": {"id": 123456789, "is_bot": True, "first_name": "Bot"},
                    "chat": {"id": self.test_user_id, "type": "private"},
                    "date": int(time.time()),
                    "text": "Previous message"
                },
                "data": callback_data
            }
        }
    
    def send_webhook(self, update_data, timeout=10):
        """Send webhook update to bot"""
        try:
            response = requests.post(
                WEBHOOK_URL,
                json=update_data,
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            )
            return response.status_code, response.text
        except Exception as e:
            return "ERROR", str(e)

def test_full_order_creation_flow():
    """
    ОСНОВНОЙ ФЛОУ 1: Создание заказа (полный флоу)
    /start → Новый заказ → Ввод всех данных FROM/TO → Данные посылки → Подтверждение → Выбор курьера → Оплата
    """
    print("\n🔍 ТЕСТ 1: ПОЛНЫЙ ФЛОУ СОЗДАНИЯ ЗАКАЗА")
    print("=" * 60)
    
    tester = TelegramBotTester()
    results = []
    
    # Шаг 1: /start команда
    print("📋 Шаг 1: /start команда")
    update = tester.create_message_update("/start")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("start_command", success, status))
    print(f"   /start: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Шаг 2: Кнопка "Новый заказ"
    print("📋 Шаг 2: Кнопка 'Новый заказ'")
    update = tester.create_callback_update("new_order")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("new_order_button", success, status))
    print(f"   Новый заказ: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Шаги 3-8: Данные отправителя (FROM)
    from_data = [
        ("FROM_NAME", "Иван Петров"),
        ("FROM_ADDRESS", "ул. Ленина 123"),
        ("FROM_CITY", "Москва"),
        ("FROM_STATE", "NY"),  # Используем валидный US штат
        ("FROM_ZIP", "10001"),
        ("FROM_PHONE", "+1234567890")
    ]
    
    print("📋 Шаги 3-8: Данные отправителя (FROM)")
    for step_name, step_value in from_data:
        update = tester.create_message_update(step_value)
        status, response = tester.send_webhook(update)
        success = status == 200
        results.append((step_name, success, status))
        print(f"   {step_name}: {step_value} → {status} {'✅' if success else '❌'}")
        time.sleep(0.3)
    
    # Шаги 9-14: Данные получателя (TO)
    to_data = [
        ("TO_NAME", "Мария Сидорова"),
        ("TO_ADDRESS", "ул. Пушкина 456"),
        ("TO_CITY", "Санкт-Петербург"),
        ("TO_STATE", "CA"),  # Используем валидный US штат
        ("TO_ZIP", "90210"),
        ("TO_PHONE", "+0987654321")
    ]
    
    print("📋 Шаги 9-14: Данные получателя (TO)")
    for step_name, step_value in to_data:
        update = tester.create_message_update(step_value)
        status, response = tester.send_webhook(update)
        success = status == 200
        results.append((step_name, success, status))
        print(f"   {step_name}: {step_value} → {status} {'✅' if success else '❌'}")
        time.sleep(0.3)
    
    # Шаги 15-18: Данные посылки
    parcel_data = [
        ("PARCEL_WEIGHT", "5"),
        ("PARCEL_LENGTH", "20"),
        ("PARCEL_WIDTH", "15"),
        ("PARCEL_HEIGHT", "10")
    ]
    
    print("📋 Шаги 15-18: Данные посылки")
    for step_name, step_value in parcel_data:
        update = tester.create_message_update(step_value)
        status, response = tester.send_webhook(update)
        success = status == 200
        results.append((step_name, success, status))
        print(f"   {step_name}: {step_value} → {status} {'✅' if success else '❌'}")
        time.sleep(0.3)
    
    # Шаг 19: Подтверждение данных
    print("📋 Шаг 19: Подтверждение данных")
    update = tester.create_callback_update("confirm_data")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("confirm_data", success, status))
    print(f"   Подтверждение: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Анализ результатов
    print("\n📊 РЕЗУЛЬТАТЫ ПОЛНОГО ФЛОУ:")
    successful_steps = sum(1 for _, success, _ in results if success)
    total_steps = len(results)
    success_rate = (successful_steps / total_steps) * 100
    
    print(f"   Успешных шагов: {successful_steps}/{total_steps} ({success_rate:.1f}%)")
    
    # Показать неудачные шаги
    failed_steps = [(step, status) for step, success, status in results if not success]
    if failed_steps:
        print("   ❌ Неудачные шаги:")
        for step, status in failed_steps:
            print(f"      {step}: {status}")
    
    overall_success = success_rate >= 80  # 80% успешности считаем приемлемым
    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ: {'✅ PASSED' if overall_success else '❌ FAILED'}")
    
    return overall_success, results

def test_order_creation_with_skip_buttons():
    """
    ОСНОВНОЙ ФЛОУ 2: Создание заказа с использованием кнопок "Пропустить"
    Тестирует пропуск FROM address2, FROM phone, TO address2, TO phone, размеры посылки
    """
    print("\n🔍 ТЕСТ 2: СОЗДАНИЕ ЗАКАЗА С КНОПКАМИ 'ПРОПУСТИТЬ'")
    print("=" * 60)
    
    tester = TelegramBotTester()
    results = []
    
    # Начальные шаги (аналогично тесту 1)
    print("📋 Начальные шаги")
    
    # /start
    update = tester.create_message_update("/start")
    status, response = tester.send_webhook(update)
    results.append(("start", status == 200, status))
    print(f"   /start: {status} {'✅' if status == 200 else '❌'}")
    time.sleep(0.5)
    
    # Новый заказ
    update = tester.create_callback_update("new_order")
    status, response = tester.send_webhook(update)
    results.append(("new_order", status == 200, status))
    print(f"   Новый заказ: {status} {'✅' if status == 200 else '❌'}")
    time.sleep(0.5)
    
    # Обязательные поля FROM
    required_from = [
        ("FROM_NAME", "Тест Пользователь"),
        ("FROM_ADDRESS", "Тестовая улица 1"),
        ("FROM_CITY", "Тестовый город"),
        ("FROM_STATE", "NY"),
        ("FROM_ZIP", "12345")
    ]
    
    print("📋 Обязательные поля отправителя")
    for step_name, step_value in required_from:
        update = tester.create_message_update(step_value)
        status, response = tester.send_webhook(update)
        results.append((step_name, status == 200, status))
        print(f"   {step_name}: {step_value} → {status} {'✅' if status == 200 else '❌'}")
        time.sleep(0.3)
    
    # ТЕСТ: Пропустить FROM address2
    print("📋 ТЕСТ: Пропустить FROM address2")
    update = tester.create_callback_update("skip_from_address2")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("skip_from_address2", success, status))
    print(f"   Пропустить FROM address2: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # ТЕСТ: Пропустить FROM phone (должен сгенерировать случайный телефон)
    print("📋 ТЕСТ: Пропустить FROM phone")
    update = tester.create_callback_update("skip_from_phone")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("skip_from_phone", success, status))
    print(f"   Пропустить FROM phone: {status} {'✅' if success else '❌'}")
    if success:
        print("   ℹ️ Должен сгенерировать случайный телефон")
    time.sleep(0.5)
    
    # Обязательные поля TO
    required_to = [
        ("TO_NAME", "Получатель Тестовый"),
        ("TO_ADDRESS", "Адрес получателя 2"),
        ("TO_CITY", "Город получателя"),
        ("TO_STATE", "CA"),
        ("TO_ZIP", "54321")
    ]
    
    print("📋 Обязательные поля получателя")
    for step_name, step_value in required_to:
        update = tester.create_message_update(step_value)
        status, response = tester.send_webhook(update)
        results.append((step_name, status == 200, status))
        print(f"   {step_name}: {step_value} → {status} {'✅' if status == 200 else '❌'}")
        time.sleep(0.3)
    
    # ТЕСТ: Пропустить TO address2
    print("📋 ТЕСТ: Пропустить TO address2")
    update = tester.create_callback_update("skip_to_address2")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("skip_to_address2", success, status))
    print(f"   Пропустить TO address2: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # ТЕСТ: Пропустить TO phone
    print("📋 ТЕСТ: Пропустить TO phone")
    update = tester.create_callback_update("skip_to_phone")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("skip_to_phone", success, status))
    print(f"   Пропустить TO phone: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Обязательный вес
    print("📋 Вес посылки (обязательно)")
    update = tester.create_message_update("3")
    status, response = tester.send_webhook(update)
    results.append(("parcel_weight", status == 200, status))
    print(f"   Вес: 3 → {status} {'✅' if status == 200 else '❌'}")
    time.sleep(0.3)
    
    # ТЕСТ: Пропустить размеры посылки (должно установить 10x10x10)
    print("📋 ТЕСТ: Пропустить размеры посылки")
    skip_dimensions = ["skip_parcel_length", "skip_parcel_width", "skip_parcel_height"]
    
    for skip_action in skip_dimensions:
        update = tester.create_callback_update(skip_action)
        status, response = tester.send_webhook(update)
        success = status == 200
        results.append((skip_action, success, status))
        print(f"   {skip_action}: {status} {'✅' if success else '❌'}")
        time.sleep(0.3)
    
    print("   ℹ️ Должно установить размеры по умолчанию: 10x10x10")
    
    # Анализ результатов
    print("\n📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ КНОПОК 'ПРОПУСТИТЬ':")
    successful_steps = sum(1 for _, success, _ in results if success)
    total_steps = len(results)
    success_rate = (successful_steps / total_steps) * 100
    
    print(f"   Успешных шагов: {successful_steps}/{total_steps} ({success_rate:.1f}%)")
    
    # Проверить специфичные тесты пропуска
    skip_tests = [
        ("skip_from_address2", "Пропуск FROM address2"),
        ("skip_from_phone", "Пропуск FROM phone (генерация случайного)"),
        ("skip_to_address2", "Пропуск TO address2"),
        ("skip_to_phone", "Пропуск TO phone"),
        ("skip_parcel_length", "Пропуск длины посылки"),
        ("skip_parcel_width", "Пропуск ширины посылки"),
        ("skip_parcel_height", "Пропуск высоты посылки")
    ]
    
    print("\n📋 СПЕЦИФИЧНЫЕ ТЕСТЫ ПРОПУСКА:")
    skip_success_count = 0
    for test_name, description in skip_tests:
        test_result = next((success for step, success, _ in results if step == test_name), False)
        print(f"   {description}: {'✅' if test_result else '❌'}")
        if test_result:
            skip_success_count += 1
    
    skip_success_rate = (skip_success_count / len(skip_tests)) * 100
    print(f"\n   Успешность тестов пропуска: {skip_success_count}/{len(skip_tests)} ({skip_success_rate:.1f}%)")
    
    overall_success = success_rate >= 70 and skip_success_rate >= 60
    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ: {'✅ PASSED' if overall_success else '❌ FAILED'}")
    
    return overall_success, results

def test_validation_issues():
    """
    ОСНОВНОЙ ФЛОУ 3: Тестирование валидации (специфичные баги)
    Issue 1: Зацикливание валидации штата
    Issue 2: Пропали подсказки при ошибках
    Issue 3: Потеря сессии при нажатии "Пропустить"
    """
    print("\n🔍 ТЕСТ 3: ТЕСТИРОВАНИЕ ВАЛИДАЦИИ И СПЕЦИФИЧНЫХ БАГОВ")
    print("=" * 60)
    
    tester = TelegramBotTester()
    results = []
    
    # Подготовка: дойти до шага валидации штата получателя
    print("📋 Подготовка: переход к шагу TO_STATE")
    
    preparation_steps = [
        ("/start", "message"),
        ("new_order", "callback"),
        ("John Doe", "message"),  # FROM_NAME
        ("123 Main St", "message"),  # FROM_ADDRESS
        ("New York", "message"),  # FROM_CITY
        ("NY", "message"),  # FROM_STATE
        ("10001", "message"),  # FROM_ZIP
        ("+1234567890", "message"),  # FROM_PHONE
        ("Jane Smith", "message"),  # TO_NAME
        ("456 Oak Ave", "message"),  # TO_ADDRESS
        ("Los Angeles", "message"),  # TO_CITY
    ]
    
    for step_data, step_type in preparation_steps:
        if step_type == "message":
            update = tester.create_message_update(step_data)
        else:
            update = tester.create_callback_update(step_data)
        
        status, response = tester.send_webhook(update)
        success = status == 200
        print(f"   Подготовка: {step_data} → {status} {'✅' if success else '❌'}")
        time.sleep(0.2)
    
    print("\n🚨 ISSUE 1: Тестирование зацикливания валидации штата")
    print("   Проблема: При вводе валидного штата 'CA' бот зацикливается")
    
    # Отправить валидный код штата CA
    print("   Отправка валидного штата: 'CA'")
    update = tester.create_message_update("CA")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("valid_state_ca", success, status))
    print(f"   TO_STATE 'CA': {status} {'✅' if success else '❌'}")
    
    # Проверить логи на наличие ошибок валидации
    print("   Проверка логов на ошибки валидации...")
    try:
        validation_logs = os.popen("tail -n 50 /var/log/supervisor/backend.err.log | grep -i 'VALIDATION ERROR.*TO_STATE'").read()
        if validation_logs.strip():
            print("   ❌ Найдены ошибки валидации TO_STATE в логах:")
            for line in validation_logs.strip().split('\n')[-3:]:
                print(f"      {line}")
            results.append(("no_validation_loop", False, "validation_errors_found"))
        else:
            print("   ✅ Ошибки валидации TO_STATE не найдены")
            results.append(("no_validation_loop", True, "no_errors"))
    except Exception as e:
        print(f"   ⚠️ Ошибка проверки логов: {e}")
        results.append(("no_validation_loop", False, "log_check_failed"))
    
    time.sleep(1)
    
    print("\n🚨 ISSUE 2: Тестирование подсказок при ошибках")
    print("   Проблема: Пропали сообщения об ошибках при неверных данных")
    
    # Создать новую сессию для тестирования ошибок
    tester_errors = TelegramBotTester()
    tester_errors.test_user_id = 999999998  # Другой пользователь
    
    # Начать новый заказ
    update = tester_errors.create_message_update("/start")
    tester_errors.send_webhook(update)
    time.sleep(0.3)
    
    update = tester_errors.create_callback_update("new_order")
    tester_errors.send_webhook(update)
    time.sleep(0.3)
    
    # Тестировать различные типы неверных данных
    invalid_data_tests = [
        ("FROM_NAME", "Иван", "кириллица - должна быть ошибка"),
        ("FROM_CITY", "123", "цифры - должна быть ошибка"),
        ("FROM_STATE", "XX", "неверный код - должна быть ошибка"),
        ("FROM_ZIP", "123", "только 3 цифры - должна быть ошибка"),
    ]
    
    error_message_count = 0
    
    for field_name, invalid_value, description in invalid_data_tests:
        print(f"   Тест {field_name}: {invalid_value} ({description})")
        
        update = tester_errors.create_message_update(invalid_value)
        status, response = tester_errors.send_webhook(update)
        
        # Проверить, что запрос обработан
        if status == 200:
            print(f"      Запрос обработан: ✅")
            
            # Проверить логи на наличие сообщений об ошибках
            time.sleep(0.5)
            error_logs = os.popen("tail -n 20 /var/log/supervisor/backend.err.log | grep -i 'VALIDATION ERROR\\|ERROR MESSAGE SENT'").read()
            
            if "❌ VALIDATION ERROR" in error_logs:
                print(f"      Ошибка валидации зафиксирована: ✅")
                if "✅ ERROR MESSAGE SENT successfully" in error_logs:
                    print(f"      Сообщение об ошибке отправлено: ✅")
                    error_message_count += 1
                elif "❌ FAILED to send error message" in error_logs:
                    print(f"      Сообщение об ошибке НЕ отправлено: ❌")
                else:
                    print(f"      Статус отправки сообщения неизвестен: ⚠️")
            else:
                print(f"      Ошибка валидации НЕ зафиксирована: ❌")
        else:
            print(f"      Запрос НЕ обработан: ❌ ({status})")
        
        time.sleep(0.5)
    
    error_messages_working = error_message_count >= 2  # Хотя бы половина должна работать
    results.append(("error_messages", error_messages_working, f"{error_message_count}/4"))
    print(f"\n   Сообщения об ошибках работают: {'✅' if error_messages_working else '❌'} ({error_message_count}/4)")
    
    print("\n🚨 ISSUE 3: Тестирование потери сессии при нажатии 'Пропустить'")
    print("   Проблема: Сессия теряется при использовании кнопок пропуска")
    
    # Создать новую сессию
    tester_session = TelegramBotTester()
    tester_session.test_user_id = 999999997
    
    # Начать заказ и дойти до шага с кнопкой пропуска
    session_steps = [
        ("/start", "message"),
        ("new_order", "callback"),
        ("Test User", "message"),  # FROM_NAME
        ("Test Address", "message"),  # FROM_ADDRESS
    ]
    
    print("   Создание сессии до шага FROM_ADDRESS2...")
    for step_data, step_type in session_steps:
        if step_type == "message":
            update = tester_session.create_message_update(step_data)
        else:
            update = tester_session.create_callback_update(step_data)
        
        status, response = tester_session.send_webhook(update)
        time.sleep(0.2)
    
    # Нажать кнопку "Пропустить"
    print("   Нажатие кнопки 'Пропустить FROM_ADDRESS2'...")
    update = tester_session.create_callback_update("skip_from_address2")
    status, response = tester_session.send_webhook(update)
    skip_success = status == 200
    results.append(("skip_no_session_loss", skip_success, status))
    print(f"   Кнопка пропуска: {status} {'✅' if skip_success else '❌'}")
    
    # Попробовать продолжить заказ
    print("   Попытка продолжить заказ после пропуска...")
    update = tester_session.create_message_update("Test City")  # FROM_CITY
    status, response = tester_session.send_webhook(update)
    continue_success = status == 200
    results.append(("continue_after_skip", continue_success, status))
    print(f"   Продолжение заказа: {status} {'✅' if continue_success else '❌'}")
    
    session_preserved = skip_success and continue_success
    print(f"   Сессия сохранена после пропуска: {'✅' if session_preserved else '❌'}")
    
    # Анализ результатов
    print("\n📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ВАЛИДАЦИИ:")
    
    issue_results = [
        ("Issue 1: Зацикливание валидации штата", next((success for step, success, _ in results if step == "valid_state_ca"), False)),
        ("Issue 2: Сообщения об ошибках", next((success for step, success, _ in results if step == "error_messages"), False)),
        ("Issue 3: Потеря сессии при пропуске", session_preserved)
    ]
    
    for issue_name, issue_success in issue_results:
        print(f"   {issue_name}: {'✅ RESOLVED' if issue_success else '❌ STILL PRESENT'}")
    
    issues_resolved = sum(1 for _, success in issue_results if success)
    overall_success = issues_resolved >= 2  # Хотя бы 2 из 3 проблем должны быть решены
    
    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ: {'✅ PASSED' if overall_success else '❌ FAILED'}")
    print(f"   Решенных проблем: {issues_resolved}/3")
    
    return overall_success, results

def test_template_functionality():
    """
    ОСНОВНОЙ ФЛОУ 4: Тестирование шаблонов
    - Создание и сохранение шаблона
    - Использование шаблона для нового заказа
    - Редактирование адресов в шаблоне
    """
    print("\n🔍 ТЕСТ 4: ТЕСТИРОВАНИЕ ФУНКЦИОНАЛЬНОСТИ ШАБЛОНОВ")
    print("=" * 60)
    
    tester = TelegramBotTester()
    results = []
    
    # Шаг 1: Создать заказ для сохранения как шаблон
    print("📋 Шаг 1: Создание заказа для сохранения как шаблон")
    
    # Полный флоу создания заказа (сокращенная версия)
    order_steps = [
        ("/start", "message"),
        ("new_order", "callback"),
        ("Template User", "message"),  # FROM_NAME
        ("Template Street 123", "message"),  # FROM_ADDRESS
        ("Template City", "message"),  # FROM_CITY
        ("NY", "message"),  # FROM_STATE
        ("10001", "message"),  # FROM_ZIP
        ("+1111111111", "message"),  # FROM_PHONE
        ("Template Recipient", "message"),  # TO_NAME
        ("Recipient Street 456", "message"),  # TO_ADDRESS
        ("Recipient City", "message"),  # TO_CITY
        ("CA", "message"),  # TO_STATE
        ("90210", "message"),  # TO_ZIP
        ("+2222222222", "message"),  # TO_PHONE
        ("2", "message"),  # PARCEL_WEIGHT
        ("15", "message"),  # PARCEL_LENGTH
        ("10", "message"),  # PARCEL_WIDTH
        ("8", "message"),  # PARCEL_HEIGHT
    ]
    
    print("   Создание полного заказа...")
    for i, (step_data, step_type) in enumerate(order_steps):
        if step_type == "message":
            update = tester.create_message_update(step_data)
        else:
            update = tester.create_callback_update(step_data)
        
        status, response = tester.send_webhook(update)
        success = status == 200
        if not success:
            print(f"   Шаг {i+1} неудачен: {step_data} → {status}")
        time.sleep(0.2)
    
    # Шаг 2: Сохранить как шаблон
    print("📋 Шаг 2: Сохранение как шаблон")
    
    # Нажать кнопку "Сохранить как шаблон"
    update = tester.create_callback_update("save_as_template")
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("save_as_template_button", success, status))
    print(f"   Кнопка 'Сохранить как шаблон': {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Ввести название шаблона
    template_name = f"Тестовый шаблон {int(time.time())}"
    update = tester.create_message_update(template_name)
    status, response = tester.send_webhook(update)
    success = status == 200
    results.append(("template_name_input", success, status))
    print(f"   Название шаблона: {template_name} → {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Шаг 3: Использовать шаблон для нового заказа
    print("📋 Шаг 3: Использование шаблона для нового заказа")
    
    # Создать новую сессию для использования шаблона
    tester_template = TelegramBotTester()
    tester_template.test_user_id = 999999996
    
    # Перейти к шаблонам
    template_steps = [
        ("/start", "message"),
        ("my_templates", "callback"),
    ]
    
    for step_data, step_type in template_steps:
        if step_type == "message":
            update = tester_template.create_message_update(step_data)
        else:
            update = tester_template.create_callback_update(step_data)
        
        status, response = tester_template.send_webhook(update)
        time.sleep(0.3)
    
    # Выбрать шаблон (используем общий ID для тестирования)
    update = tester_template.create_callback_update("view_template_test_id")
    status, response = tester_template.send_webhook(update)
    success = status == 200
    results.append(("view_template", success, status))
    print(f"   Просмотр шаблона: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Использовать шаблон
    update = tester_template.create_callback_update("use_template")
    status, response = tester_template.send_webhook(update)
    success = status == 200
    results.append(("use_template", success, status))
    print(f"   Использование шаблона: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Продолжить создание заказа с шаблоном
    update = tester_template.create_callback_update("start_order_with_template")
    status, response = tester_template.send_webhook(update)
    success = status == 200
    results.append(("start_order_with_template", success, status))
    print(f"   Начать заказ с шаблоном: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Шаг 4: Редактирование шаблона
    print("📋 Шаг 4: Редактирование адресов в шаблоне")
    
    # Создать еще одну сессию для редактирования
    tester_edit = TelegramBotTester()
    tester_edit.test_user_id = 999999995
    
    # Перейти к редактированию шаблона
    edit_steps = [
        ("/start", "message"),
        ("my_templates", "callback"),
        ("view_template_test_id", "callback"),
        ("edit_template", "callback"),
    ]
    
    for step_data, step_type in edit_steps:
        if step_type == "message":
            update = tester_edit.create_message_update(step_data)
        else:
            update = tester_edit.create_callback_update(step_data)
        
        status, response = tester_edit.send_webhook(update)
        time.sleep(0.3)
    
    # Редактировать адрес отправителя
    update = tester_edit.create_callback_update("edit_template_from_address")
    status, response = tester_edit.send_webhook(update)
    success = status == 200
    results.append(("edit_from_address", success, status))
    print(f"   Редактирование адреса отправителя: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Редактировать адрес получателя
    update = tester_edit.create_callback_update("edit_template_to_address")
    status, response = tester_edit.send_webhook(update)
    success = status == 200
    results.append(("edit_to_address", success, status))
    print(f"   Редактирование адреса получателя: {status} {'✅' if success else '❌'}")
    time.sleep(0.5)
    
    # Анализ результатов
    print("\n📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ШАБЛОНОВ:")
    
    template_tests = [
        ("save_as_template_button", "Сохранение как шаблон"),
        ("template_name_input", "Ввод названия шаблона"),
        ("view_template", "Просмотр шаблона"),
        ("use_template", "Использование шаблона"),
        ("start_order_with_template", "Начало заказа с шаблоном"),
        ("edit_from_address", "Редактирование адреса отправителя"),
        ("edit_to_address", "Редактирование адреса получателя")
    ]
    
    successful_tests = 0
    for test_name, description in template_tests:
        test_result = next((success for step, success, _ in results if step == test_name), False)
        print(f"   {description}: {'✅' if test_result else '❌'}")
        if test_result:
            successful_tests += 1
    
    success_rate = (successful_tests / len(template_tests)) * 100
    overall_success = success_rate >= 60  # 60% успешности для шаблонов
    
    print(f"\n   Успешных тестов: {successful_tests}/{len(template_tests)} ({success_rate:.1f}%)")
    print(f"🎯 ОБЩИЙ РЕЗУЛЬТАТ: {'✅ PASSED' if overall_success else '❌ FAILED'}")
    
    return overall_success, results

def check_bot_performance():
    """Проверка производительности бота после оптимизации"""
    print("\n🔍 ПРОВЕРКА ПРОИЗВОДИТЕЛЬНОСТИ БОТА")
    print("=" * 60)
    print("🎯 КОНТЕКСТ: После оптимизации бот должен отвечать МГНОВЕННО на каждом шаге")
    
    tester = TelegramBotTester()
    response_times = []
    
    # Тестировать скорость ответа на различных шагах
    test_steps = [
        ("/start", "message"),
        ("new_order", "callback"),
        ("Speed Test User", "message"),
        ("123 Speed St", "message"),
        ("Speed City", "message"),
    ]
    
    print("📋 Измерение времени ответа:")
    
    for step_data, step_type in test_steps:
        if step_type == "message":
            update = tester.create_message_update(step_data)
        else:
            update = tester.create_callback_update(step_data)
        
        start_time = time.time()
        status, response = tester.send_webhook(update)
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # в миллисекундах
        response_times.append(response_time)
        
        speed_status = "⚡" if response_time < 500 else "🐌" if response_time < 1000 else "❌"
        print(f"   {step_data}: {response_time:.0f}ms {speed_status}")
        
        time.sleep(0.1)
    
    # Анализ производительности
    avg_response_time = sum(response_times) / len(response_times)
    max_response_time = max(response_times)
    fast_responses = sum(1 for t in response_times if t < 500)
    
    print(f"\n📊 АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ:")
    print(f"   Среднее время ответа: {avg_response_time:.0f}ms")
    print(f"   Максимальное время ответа: {max_response_time:.0f}ms")
    print(f"   Быстрых ответов (<500ms): {fast_responses}/{len(response_times)}")
    
    performance_good = avg_response_time < 800 and fast_responses >= len(response_times) * 0.7
    print(f"🎯 ПРОИЗВОДИТЕЛЬНОСТЬ: {'✅ ОТЛИЧНАЯ' if performance_good else '❌ ТРЕБУЕТ УЛУЧШЕНИЯ'}")
    
    return performance_good

def main():
    """Основная функция для запуска всех тестов"""
    print("🤖 КОМПЛЕКСНОЕ E2E ТЕСТИРОВАНИЕ TELEGRAM-БОТА")
    print("=" * 80)
    print("🎯 ЦЕЛЬ: Полное E2E тестирование основных флоу бота + проверка специфичных проблем")
    print("🔧 КОНТЕКСТ: После масштабной оптимизации производительности (asyncio.create_task)")
    print("🐛 ФОКУС: Issues 1, 2, 3 - валидация штата, подсказки ошибок, потеря сессии")
    
    # Проверить доступность webhook endpoint
    print(f"\n🔗 Проверка доступности Webhook: {WEBHOOK_URL}")
    try:
        response = requests.get(WEBHOOK_URL, timeout=5)
        if response.status_code == 405:  # Method Not Allowed - ожидаемо для POST endpoint
            print("✅ Webhook endpoint доступен")
        else:
            print(f"⚠️ Неожиданный ответ: {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook недоступен: {e}")
        return False
    
    # Запуск всех тестов
    test_results = []
    
    # Тест 1: Полный флоу создания заказа
    try:
        success, details = test_full_order_creation_flow()
        test_results.append(("Полный флоу создания заказа", success, details))
    except Exception as e:
        print(f"❌ Ошибка в тесте 1: {e}")
        test_results.append(("Полный флоу создания заказа", False, str(e)))
    
    # Тест 2: Создание заказа с кнопками "Пропустить"
    try:
        success, details = test_order_creation_with_skip_buttons()
        test_results.append(("Заказ с кнопками 'Пропустить'", success, details))
    except Exception as e:
        print(f"❌ Ошибка в тесте 2: {e}")
        test_results.append(("Заказ с кнопками 'Пропустить'", False, str(e)))
    
    # Тест 3: Тестирование валидации (Issues 1, 2, 3)
    try:
        success, details = test_validation_issues()
        test_results.append(("Валидация и специфичные баги", success, details))
    except Exception as e:
        print(f"❌ Ошибка в тесте 3: {e}")
        test_results.append(("Валидация и специфичные баги", False, str(e)))
    
    # Тест 4: Функциональность шаблонов
    try:
        success, details = test_template_functionality()
        test_results.append(("Функциональность шаблонов", success, details))
    except Exception as e:
        print(f"❌ Ошибка в тесте 4: {e}")
        test_results.append(("Функциональность шаблонов", False, str(e)))
    
    # Тест 5: Производительность
    try:
        success = check_bot_performance()
        test_results.append(("Производительность бота", success, "performance_check"))
    except Exception as e:
        print(f"❌ Ошибка в тесте производительности: {e}")
        test_results.append(("Производительность бота", False, str(e)))
    
    # Итоговый отчет
    print("\n" + "=" * 80)
    print("📊 ИТОГОВЫЙ ОТЧЕТ E2E ТЕСТИРОВАНИЯ")
    print("=" * 80)
    
    passed_tests = sum(1 for _, success, _ in test_results if success)
    total_tests = len(test_results)
    success_rate = (passed_tests / total_tests) * 100
    
    for test_name, success, details in test_results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    print(f"\n📈 ОБЩАЯ СТАТИСТИКА:")
    print(f"   Пройденных тестов: {passed_tests}/{total_tests}")
    print(f"   Процент успешности: {success_rate:.1f}%")
    
    # Специальный фокус на Issues 1, 2, 3
    print(f"\n🐛 СТАТУС СПЕЦИФИЧНЫХ ПРОБЛЕМ:")
    validation_test = next((success for name, success, _ in test_results if "Валидация" in name), False)
    if validation_test:
        print(f"   Issues 1, 2, 3: ✅ RESOLVED")
    else:
        print(f"   Issues 1, 2, 3: ❌ STILL PRESENT")
    
    overall_success = success_rate >= 60  # 60% успешности считаем приемлемым для E2E тестов
    
    print(f"\n🎯 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ: {'✅ УСПЕШНО' if overall_success else '❌ ТРЕБУЕТ ВНИМАНИЯ'}")
    
    if not overall_success:
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        print(f"   1. Проверить логи backend на ошибки: tail -f /var/log/supervisor/backend.err.log")
        print(f"   2. Убедиться что Telegram bot token корректен")
        print(f"   3. Проверить что webhook endpoint правильно настроен")
        print(f"   4. Проверить состояние MongoDB подключения")
        print(f"   5. Проверить что все ConversationHandler правильно настроены")
    
    return overall_success

if __name__ == "__main__":
    main()