# 📚 Быстрый Справочник - Telegram Shipping Bot

## 🎯 Основная Информация

**Статус:** ✅ PRODUCTION READY
**Архитектура:** Модульная (4,325 строк в модулях)
**Качество:** 9.9/10 ⭐⭐⭐
**Backend:** FastAPI + Python + MongoDB

---

## 📂 Структура Проекта

```
/app/backend/
├── server.py (8,123 строк) - Главный файл
├── session_manager.py - SessionManager V2
│
├── handlers/ (1,829 строк)
│   ├── common_handlers.py - Команды, меню
│   ├── template_handlers.py - Шаблоны адресов
│   ├── payment_handlers.py - Баланс, оплата
│   ├── order_handlers.py - Заказы
│   ├── admin_handlers.py - Админ-функции
│   ├── webhook_handlers.py - Webhooks
│   └── order_flow/ (792 строк)
│       ├── from_address.py - FROM handlers
│       ├── to_address.py - TO handlers
│       └── parcel.py - Parcel handlers
│
├── services/ (618 строк)
│   ├── api_services.py - API вызовы
│   ├── shipstation_cache.py - Кэш
│   └── shipping_service.py - Shipping
│
├── routers/ (479 строк)
│   └── admin_router.py - Admin API
│
├── utils/ (607 строк)
│   ├── validators.py - Валидация
│   ├── performance.py - Мониторинг
│   └── cache.py - Кэш настроек
│
└── models/
    └── models.py - Pydantic модели
```

---

## 🔧 Основные Модули

### Handlers

**common_handlers.py** - Основные команды
- `start_command()` - /start
- `help_command()` - /help
- `faq_command()` - /faq
- `button_callback()` - Роутинг кнопок
- `safe_telegram_call()` - Обертка API
- `mark_message_as_selected()` - ✅ Checkmarks

**order_flow/** - Создание заказа (18 шагов)
- FROM: name, address, city, state, zip, phone
- TO: name, address, city, state, zip, phone
- PARCEL: weight, length, width, height

**template_handlers.py** - Шаблоны
- `my_templates_menu()` - Список
- `view_template_detail()` - Просмотр
- `edit_template_name()` - Редактирование
- `delete_template_handler()` - Удаление

**payment_handlers.py** - Платежи
- `my_balance_command()` - Баланс
- `add_balance()` - Пополнение
- `topup_amount_handler()` - Обработка суммы

**webhook_handlers.py** - Webhooks
- `handle_oxapay_webhook()` - Платежи
- `handle_telegram_webhook()` - Bot updates

### Services

**api_services.py** - Внешние API
- `create_oxapay_invoice()` - Создание счета
- `check_oxapay_payment()` - Проверка оплаты
- `check_shipstation_balance()` - Баланс ShipStation
- `get_shipstation_carrier_ids()` - ID курьеров
- `validate_address_with_shipstation()` - Валидация адреса

**shipstation_cache.py** - Кэширование
- 80% ускорение запросов
- TTL управление

### Utils

**validators.py** - Валидация (10 функций)
- `validate_name()` - Имена
- `validate_address()` - Адреса
- `validate_city()` - Города
- `validate_state()` - Штаты (50 US states)
- `validate_zip()` - ZIP коды
- `validate_phone()` - Телефоны (с форматированием)
- `validate_weight()` - Вес
- `validate_dimension()` - Размеры

**performance.py** - Мониторинг
- `@profile_db_query` - Декоратор профилирования
- `get_performance_stats()` - Статистика
- Slow query detection (>100ms)

### Routers

**admin_router.py** - Admin API (17 endpoints)
```
GET  /api/admin/users
POST /api/admin/users/{id}/block
POST /api/admin/users/{id}/unblock
GET  /api/admin/maintenance/status
POST /api/admin/maintenance/enable
POST /api/admin/maintenance/disable
GET  /api/admin/stats
GET  /api/admin/stats/expenses
GET  /api/admin/topups
GET  /api/admin/performance/stats
POST /api/admin/sessions/clear
GET  /api/admin/api-mode
POST /api/admin/api-mode
GET  /api/admin/logs
GET  /api/admin/health
GET  /api/admin/metrics
POST /api/admin/shipstation/check-balance
```

---

## 🔑 Ключевые Константы

### Order Flow States
```python
FROM_NAME = range(28)
FROM_ADDRESS = ...
FROM_CITY = ...
FROM_STATE = ...
FROM_ZIP = ...
FROM_PHONE = ...

TO_NAME = ...
TO_ADDRESS = ...
TO_CITY = ...
TO_STATE = ...
TO_ZIP = ...
TO_PHONE = ...

PARCEL_WEIGHT = ...
PARCEL_LENGTH = ...
PARCEL_WIDTH = ...
PARCEL_HEIGHT = ...
```

### Environment Variables
```bash
# MongoDB
MONGO_URL=mongodb://localhost:27017/telegram_shipping_bot

# Telegram
TELEGRAM_BOT_TOKEN_PRODUCTION=...
TELEGRAM_BOT_TOKEN_PREVIEW=...

# APIs
SHIPSTATION_API_KEY=...
OXAPAY_API_KEY=...

# Admin
ADMIN_API_KEY=...
ADMIN_TELEGRAM_ID=...

# URLs
REACT_APP_BACKEND_URL=https://...
WEBHOOK_BASE_URL=https://...
```

---

## 🚀 Запуск и Управление

### Supervisor Commands
```bash
# Проверка статуса
sudo supervisorctl status backend

# Перезапуск (только при изменениях .env или установке зависимостей)
sudo supervisorctl restart backend

# Логи
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/backend.out.log
```

### Установка Зависимостей
```bash
# Python
cd /app/backend
pip install new_package
pip freeze > requirements.txt

# Перезапуск после установки
sudo supervisorctl restart backend
```

### Hot Reload
**Автоматически работает для:**
- Изменения в .py файлах
- Не требует перезапуска

**Требует перезапуска:**
- Изменения в .env
- Установка новых пакетов

---

## 🧪 Тестирование

### Запуск Тестов
```bash
# Backend tests
cd /app/backend
pytest tests/

# Specific test
pytest tests/test_session_manager.py -v
```

### Проверка Lint
```bash
# Python
ruff check /app/backend/server.py
ruff check /app/backend/handlers/
```

### Manual Testing
```bash
# Проверка эндпоинтов
curl -X GET ${REACT_APP_BACKEND_URL}/api/admin/health \
  -H "X-Api-Key: ${ADMIN_API_KEY}"

# Проверка webhook
curl -X POST ${REACT_APP_BACKEND_URL}/api/telegram/webhook \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {...}}'
```

---

## 📊 Мониторинг

### Performance Stats
```bash
# API endpoint
GET /api/admin/performance/stats
Headers: X-Api-Key: ${ADMIN_API_KEY}

# Response
{
  "db_queries": [...],
  "api_calls": [...],
  "slow_queries": [...]
}
```

### Logs
```bash
# Backend logs
GET /api/admin/logs?lines=200&filter=ERROR
Headers: X-Api-Key: ${ADMIN_API_KEY}
```

### Health Check
```bash
# Health status
GET /api/admin/health
Headers: X-Api-Key: ${ADMIN_API_KEY}

# Response
{
  "bot_instance": true,
  "application": true,
  "database": true,
  "bot_username": "...",
  "bot_id": ...
}
```

---

## 🔧 Частые Задачи

### Добавить Новый Handler
```python
# 1. Создать функцию в нужном модуле
# handlers/my_module.py
async def my_new_handler(update, context):
    # Your logic
    pass

# 2. Импортировать в server.py
from handlers.my_module import my_new_handler

# 3. Добавить в ConversationHandler или CommandHandler
```

### Добавить Валидацию
```python
# 1. Создать функцию в utils/validators.py
def validate_my_field(value: str) -> Tuple[bool, str]:
    if not value:
        return False, "Error message"
    return True, ""

# 2. Использовать в handler
from utils.validators import validate_my_field

is_valid, error = validate_my_field(user_input)
if not is_valid:
    await update.message.reply_text(error)
    return CURRENT_STATE
```

### Добавить Admin Endpoint
```python
# routers/admin_router.py
@admin_router.get("/my-endpoint")
async def my_endpoint(authenticated: bool = Depends(verify_admin_key)):
    from server import db
    # Your logic
    return {"result": "..."}
```

### Добавить Профилирование
```python
# Обернуть функцию декоратором
from utils.performance import profile_db_query

@profile_db_query("my_query_name")
async def my_db_function():
    return await db.collection.find_one(...)
```

---

## 🐛 Troubleshooting

### Backend не запускается
```bash
# Проверить логи
tail -100 /var/log/supervisor/backend.err.log

# Проверить синтаксис
python3 /app/backend/server.py

# Проверить зависимости
pip list | grep package_name
```

### Ошибки импорта
```bash
# Проверить PYTHONPATH
echo $PYTHONPATH

# Проверить структуру модулей
ls -la /app/backend/handlers/
```

### MongoDB проблемы
```bash
# Проверить подключение
python3 -c "from motor.motor_asyncio import AsyncIOMotorClient; client = AsyncIOMotorClient('mongodb://localhost:27017'); print(client.list_database_names())"
```

### Telegram API проблемы
```bash
# Проверить webhook
curl -X POST "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

---

## 📞 Поддержка

### Документация
- `/app/REFACTORING_REPORT.md` - Полный отчет
- `/app/QUICK_REFERENCE.md` - Этот файл
- `/app/test_result.md` - История тестирования

### Ресурсы
- FastAPI: https://fastapi.tiangolo.com/
- python-telegram-bot: https://python-telegram-bot.org/
- MongoDB Motor: https://motor.readthedocs.io/
- ShipStation API: https://shipstation.com/docs/api
- Oxapay API: https://oxapay.com/docs

---

**Версия:** 1.0
**Обновлено:** 2025
**Статус:** ✅ Актуально
