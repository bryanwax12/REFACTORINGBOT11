# Bot Environment & Mode Refactoring

**Дата**: 2025-11-14  
**Агент**: Fork Agent (E1)  
**Приоритет**: По запросу пользователя

---

## 🎯 Цель Рефакторинга

Разделить конфигурацию для **test** и **production** ботов с гибким переключением между режимами работы (**polling**/**webhook**).

### Было
- Один токен бота с автоопределением по URL
- Жестко закодированная логика выбора webhook/polling
- Сложно переключаться между окружениями

### Стало
- Отдельные конфигурации для test и production ботов
- Гибкое управление через переменные окружения
- API endpoints для управления и мониторинга
- Централизованная система конфигурации

---

## 📁 Новые Файлы

### 1. `/app/backend/utils/bot_config.py`

Централизованная система управления конфигурацией бота.

**Основные классы**:
- `BotConfig` - основной класс конфигурации
- Функции-хелперы для быстрого доступа

**Возможности**:
```python
from utils.bot_config import get_bot_config, get_bot_token

# Получить конфигурацию
config = get_bot_config()
print(config.get_config_summary())

# Получить токен активного бота
token = get_bot_token()

# Проверить режим
if config.should_use_webhook():
    # Webhook логика
    pass
```

### 2. `/app/backend/routers/bot_config_router.py`

API endpoints для управления конфигурацией бота.

**Endpoints**:
- `GET /api/bot-config/status` - текущая конфигурация (публичный)
- `GET /api/bot-config/full` - полная конфигурация (требует auth)
- `GET /api/bot-config/recommendations` - рекомендации
- `GET /api/bot-config/webhook-info` - информация о webhook
- `POST /api/bot-config/switch-environment` - переключить окружение
- `POST /api/bot-config/switch-mode` - переключить режим
- `POST /api/bot-config/set-webhook` - установить webhook вручную
- `POST /api/bot-config/delete-webhook` - удалить webhook

---

## 🔧 Переменные Окружения (.env)

### Основная Конфигурация

```bash
# ============================================================
# TELEGRAM BOT CONFIGURATION
# ============================================================

# Окружение: test или production
BOT_ENVIRONMENT="test"

# Режим работы: polling или webhook
BOT_MODE="polling"

# Test Bot Configuration
TEST_BOT_TOKEN="8560388458:AAEogOidGIJSEjVNxipDu60pu8WwZ2gOCPQ"
TEST_BOT_USERNAME="whitelabel_shipping_bot_test_bot"

# Production Bot Configuration  
PROD_BOT_TOKEN="8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM"
PROD_BOT_USERNAME="whitelabel_shipping_bot"

# Webhook Configuration
WEBHOOK_BASE_URL="https://your-domain.com"
WEBHOOK_PATH="/api/telegram/webhook"

# Legacy (для обратной совместимости)
TELEGRAM_BOT_TOKEN="..."
```

### Комбинации Настроек

#### 1. Local Development (Разработка)
```bash
BOT_ENVIRONMENT="test"
BOT_MODE="polling"
```
**Результат**: Тестовый бот с polling режимом

#### 2. Staging (Тестирование на сервере)
```bash
BOT_ENVIRONMENT="test"
BOT_MODE="webhook"
WEBHOOK_BASE_URL="https://staging.example.com"
```
**Результат**: Тестовый бот с webhook режимом

#### 3. Production
```bash
BOT_ENVIRONMENT="production"
BOT_MODE="webhook"
WEBHOOK_BASE_URL="https://example.com"
```
**Результат**: Продакшн бот с webhook режимом

---

## 🔄 Изменения в Коде

### server.py

**До**:
```python
# Жестко закодированная логика
webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
is_production = 'crypto-shipping.emergent.host' in webhook_base_url

if is_production:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN_PRODUCTION', '')
else:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN_PREVIEW', '')
```

**После**:
```python
from utils.bot_config import (
    get_bot_config,
    get_bot_token,
    is_webhook_mode
)

# Получить конфигурацию
bot_config = get_bot_config()
TELEGRAM_BOT_TOKEN = get_bot_token()

# Вывести информацию
print(f"🤖 BOT CONFIGURATION:")
print(f"   Environment: {bot_config.environment.upper()}")
print(f"   Mode: {bot_config.mode.upper()}")
print(f"   Active Bot: @{bot_config.get_active_bot_username()}")
```

### Запуск бота

**До**:
```python
# Проверка URL для выбора режима
webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
is_production = 'crypto-shipping.emergent.host' in webhook_base_url

if is_production:
    # Webhook
    await application.bot.set_webhook(url=webhook_url)
else:
    # Polling
    await application.updater.start_polling()
```

**После**:
```python
# Используем конфигурацию
use_webhook = is_webhook_mode()
webhook_url = bot_config.get_webhook_url()

if use_webhook and webhook_url:
    # Webhook mode
    await application.bot.set_webhook(url=webhook_url)
else:
    # Polling mode
    await application.updater.start_polling()
```

---

## 🧪 Тестирование

### 1. Проверка текущей конфигурации

```bash
curl https://telegram-shipbot.preview.emergentagent.com/api/bot-config/status
```

**Ответ**:
```json
{
  "success": true,
  "config": {
    "environment": "test",
    "mode": "polling",
    "bot_username": "whitelabel_shipping_bot_test_bot",
    "webhook_enabled": false,
    "is_production": false
  }
}
```

### 2. Полная конфигурация (с auth)

```bash
curl https://telegram-shipbot.preview.emergentagent.com/api/bot-config/full \
  -H "X-API-Key: YOUR_ADMIN_KEY"
```

**Ответ**:
```json
{
  "success": true,
  "config": {
    "environment": "test",
    "mode": "polling",
    "bot_username": "whitelabel_shipping_bot_test_bot",
    "test_bot": {
      "username": "whitelabel_shipping_bot_test_bot",
      "configured": true
    },
    "prod_bot": {
      "username": "whitelabel_shipping_bot",
      "configured": true
    },
    "webhook": {
      "enabled": false,
      "url": null,
      "base_url": "https://...",
      "path": "/api/telegram/webhook"
    }
  }
}
```

### 3. Рекомендации

```bash
curl https://telegram-shipbot.preview.emergentagent.com/api/bot-config/recommendations
```

**Ответ**:
```json
{
  "success": true,
  "current": {...},
  "recommendations": [
    {
      "type": "warning",
      "message": "Production environment should use webhook mode",
      "suggestion": "Set BOT_MODE=webhook in .env"
    }
  ]
}
```

### 4. Информация о webhook

```bash
curl https://telegram-shipbot.preview.emergentagent.com/api/bot-config/webhook-info \
  -H "X-API-Key: YOUR_ADMIN_KEY"
```

---

## 📊 Управление Конфигурацией

### Переключение окружения (требует перезапуск)

```bash
curl -X POST https://telegram-shipbot.preview.emergentagent.com/api/bot-config/switch-environment \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"environment": "production"}'
```

**Ответ**:
```json
{
  "success": true,
  "message": "Environment switched from test to production",
  "warning": "⚠️ SERVER RESTART REQUIRED for changes to take effect!",
  "old_environment": "test",
  "new_environment": "production"
}
```

### Переключение режима (требует перезапуск)

```bash
curl -X POST https://telegram-shipbot.preview.emergentagent.com/api/bot-config/switch-mode \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "webhook"}'
```

---

## 🔄 Миграция с Старой Конфигурации

### Шаг 1: Определить текущее окружение

**Если у вас Preview/Development**:
```bash
BOT_ENVIRONMENT="test"
BOT_MODE="polling"
```

**Если у вас Production**:
```bash
BOT_ENVIRONMENT="production"
BOT_MODE="webhook"
WEBHOOK_BASE_URL="https://your-domain.com"
```

### Шаг 2: Обновить .env

Добавить/обновить переменные:
```bash
# Новые переменные
BOT_ENVIRONMENT="test"
BOT_MODE="polling"
TEST_BOT_TOKEN="..."
PROD_BOT_TOKEN="..."

# Старые переменные можно оставить для обратной совместимости
TELEGRAM_BOT_TOKEN="..."
```

### Шаг 3: Перезапустить сервер

```bash
sudo supervisorctl restart backend
```

### Шаг 4: Проверить конфигурацию

```bash
curl https://your-domain.com/api/bot-config/status
```

---

## 💡 Лучшие Практики

### 1. Development (Разработка)
```bash
BOT_ENVIRONMENT="test"
BOT_MODE="polling"
```
**Почему**: Polling проще для отладки, не требует HTTPS

### 2. Staging (Тестирование)
```bash
BOT_ENVIRONMENT="test"
BOT_MODE="webhook"
WEBHOOK_BASE_URL="https://staging.example.com"
```
**Почему**: Тестирование webhook в условиях, близких к production

### 3. Production
```bash
BOT_ENVIRONMENT="production"
BOT_MODE="webhook"
WEBHOOK_BASE_URL="https://example.com"
```
**Почему**: Webhook более эффективен для production (меньше нагрузки)

---

## 🔒 Безопасность

### Защищенные Endpoints

Требуют `X-API-Key` header:
- `/api/bot-config/full`
- `/api/bot-config/webhook-info`
- `/api/bot-config/switch-environment`
- `/api/bot-config/switch-mode`
- `/api/bot-config/set-webhook`
- `/api/bot-config/delete-webhook`

### Публичные Endpoints

Не требуют аутентификацию:
- `/api/bot-config/status` - только базовая информация
- `/api/bot-config/recommendations` - общие рекомендации

---

## 📝 Логирование

Система выводит детальную информацию при запуске:

```
🔵 BOT CONFIGURATION:
   Environment: TEST
   Mode: 🔄 POLLING
   Active Bot: @whitelabel_shipping_bot_test_bot
✅ Bot instance created: @whitelabel_shipping_bot_test_bot

🔵 Starting Telegram Bot:
   Environment: TEST
   Mode: 🔄 POLLING
   Bot: @whitelabel_shipping_bot_test_bot
🔄 POLLING MODE
   Webhook disabled
✅ Polling started successfully
```

**Иконки**:
- 🟢 = Production environment
- 🔵 = Test environment
- 🌐 = Webhook mode
- 🔄 = Polling mode

---

## 🎯 Преимущества Рефакторинга

| Аспект | До | После |
|--------|-----|-------|
| **Гибкость** | Жестко закодированная логика | Гибкая конфигурация через .env |
| **Управление** | Требует изменения кода | API endpoints для управления |
| **Прозрачность** | Неясно какой бот используется | Детальное логирование |
| **Тестирование** | Сложно переключаться | Легко переключаться между окружениями |
| **Масштабируемость** | Один бот | Два независимых бота |
| **Мониторинг** | Нет информации | API для мониторинга конфигурации |

---

## 🚀 Следующие Шаги

1. ✅ **Текущая конфигурация**: test + polling
2. 🔜 **Для production**: Обновить .env и установить webhook
3. 🔜 **Мониторинг**: Добавить алерты на проблемы с webhook

---

## 📚 Связанные Документы

- `/app/backend/utils/bot_config.py` - исходный код конфигурации
- `/app/backend/routers/bot_config_router.py` - API endpoints
- `/app/backend/.env` - переменные окружения

---

**Автор**: Fork Agent (E1)  
**Статус**: ✅ ЗАВЕРШЕНО  
**Production Ready**: ✅ ДА
