# 📋 Полная таблица настроек .env для Production

## 🗄️ DATABASE CONFIGURATION

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `MONGO_URL` | `mongodb://localhost:27017` | `mongodb://localhost:27017` | URL подключения к MongoDB | ✅ Оставить как есть |
| `DB_NAME` | `telegram_shipping_bot` | `telegram_shipping_bot_production` | Название базы данных | ⚠️ **ОБЯЗАТЕЛЬНО изменить** |
| `DB_NAME_PRODUCTION` | `telegram_shipping_bot` | `telegram_shipping_bot_production` | Название production БД | ⚠️ **ОБЯЗАТЕЛЬНО изменить** |
| `DB_NAME_PREVIEW` | `telegram_shipping_bot` | `telegram_shipping_bot` | Название preview БД | ✅ Оставить как есть |

---

## 🌐 SERVER CONFIGURATION

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `CORS_ORIGINS` | `*` | `*` | CORS настройки (можно ограничить) | ✅ Оставить или изменить на ваш домен |

---

## 👤 ADMIN CONFIGURATION

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `ADMIN_TELEGRAM_ID` | `7066790254` | `7066790254` | Ваш Telegram ID для уведомлений | ✅ Оставить (или заменить на ваш ID) |
| `ADMIN_API_KEY` | `sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024` | `sk_admin_[сгенерировать новый]` | Ключ для защиты admin endpoints | 🔴 **ОБЯЗАТЕЛЬНО сгенерировать новый!** |

**Как сгенерировать:**
```bash
openssl rand -hex 32
# Результат вставить в: sk_admin_РЕЗУЛЬТАТ
```

---

## 🤖 TELEGRAM BOT CONFIGURATION

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `BOT_ENVIRONMENT` | `test` | `production` | Режим окружения | 🔴 **ОБЯЗАТЕЛЬНО: production** |
| `BOT_MODE` | `polling` | `webhook` | Режим работы бота | 🔴 **ОБЯЗАТЕЛЬНО: webhook** |
| `TEST_BOT_TOKEN` | `8560388458:AAHxT...` | `8560388458:AAHxT...` | Токен тестового бота | ✅ Оставить как есть |
| `TEST_BOT_USERNAME` | `whitelabel_shipping_bot_test_bot` | `whitelabel_shipping_bot_test_bot` | Username тестового бота | ✅ Оставить как есть |
| `PROD_BOT_TOKEN` | `8492458522:AAE3d...` | `8492458522:AAE3d...` | Токен продакшн бота | ✅ Оставить как есть |
| `PROD_BOT_USERNAME` | `whitelabel_shipping_bot` | `whitelabel_shipping_bot` | Username продакшн бота | ✅ Оставить как есть |
| `TELEGRAM_BOT_TOKEN` | `8560388458:AAHxT...` (test) | `8492458522:AAE3d...` (prod) | Legacy токен (auto-select) | 🔴 **Изменить на PROD_BOT_TOKEN** |

---

## 🔗 WEBHOOK CONFIGURATION

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `WEBHOOK_BASE_URL` | `https://telegram-admin-fix-2.preview.emergentagent.com` | `https://ваш-домен.com` | Базовый URL для webhook | 🔴 **ОБЯЗАТЕЛЬНО заменить на ваш домен!** |
| `WEBHOOK_PATH` | `/api/telegram/webhook` | `/api/telegram/webhook` | Путь для webhook | ✅ Оставить как есть |

**Важно:** 
- Домен ДОЛЖЕН иметь HTTPS (SSL сертификат)
- Формат: `https://your-domain.com` (без слэша в конце)
- Telegram будет отправлять обновления на: `{WEBHOOK_BASE_URL}{WEBHOOK_PATH}`

---

## 💰 PAYMENT PROVIDERS

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `CRYPTOBOT_TOKEN` | `480059:AA2YcX1...` | `480059:AA2YcX1...` | Токен CryptoBot для крипто-платежей | ✅ Оставить (или заменить на свой) |
| `OXAPAY_API_KEY` | `AIQ2XA-A4ASEL-5HTMND-6WJ2YK` | `AIQ2XA-A4ASEL-5HTMND-6WJ2YK` | API ключ Oxapay | ✅ Оставить (или заменить на свой) |

**Важно для Oxapay:**
После деплоя настройте Callback URL в панели Oxapay:
```
Callback URL: https://ваш-домен.com/api/oxapay/webhook
```

---

## 📦 SHIPSTATION CONFIGURATION

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `SHIPSTATION_API_KEY` | `P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g` | `P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g` | Текущий API ключ ShipStation | ⚠️ Убедитесь что это Production ключ! |
| `SHIPSTATION_API_KEY_PROD` | `P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g` | `P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g` | Production ключ | ✅ Оставить как есть |
| `SHIPSTATION_API_KEY_TEST` | `TEST_3NFykGjeVRke57QiCtJzEOq2ZVsXBrWgOvCNrwcwGU8` | `TEST_3NFykGjeVRke57QiCtJzEOq2ZVsXBrWgOvCNrwcwGU8` | Test ключ | ✅ Оставить как есть |

**Важно:** 
- В production используется `SHIPSTATION_API_KEY_PROD`
- Получить Production ключ: https://ss.shipstation.com -> Settings -> API Settings
- НЕ используйте Test ключ в production!

---

## 📢 TELEGRAM CHANNEL CONFIGURATION

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `CHANNEL_ID` | `-1003417145879` | `-1003417145879` | ID вашего Telegram канала | ✅ Оставить (или заменить на ваш канал) |
| `CHANNEL_INVITE_LINK` | `https://t.me/WHITE_LABEL_SHIPPING_BOTCHANNEL` | `https://t.me/WHITE_LABEL_SHIPPING_BOTCHANNEL` | Ссылка на канал | ✅ Оставить (или заменить на ваш канал) |

**Важно:**
1. Добавьте бота как **администратора** в канал
2. Channel ID имеет формат: `-100XXXXXXXXXX` (с минусом!)
3. Как получить Channel ID:
   - Добавьте бота в канал как админа
   - Напишите что-то в канал
   - Используйте метод `getUpdates` или проверьте логи бота

---

## 🔒 SECURITY & INTERNAL

| Параметр | Текущее (Test) | Production | Описание | Действие |
|----------|----------------|------------|----------|----------|
| `BOT_INSTANCE_ID` | `stale-button-fix` | `production-[timestamp]` | Уникальный ID экземпляра | 🔴 **Сгенерировать новый!** |
| `BOT_SIGNATURE_KEY` | `VMxm-SuinMcpdSRQjEEZG8Mkekhj0pjRh73dzpZDvOM` | `[сгенерировать новый]` | Ключ для подписи callback данных | 🔴 **ОБЯЗАТЕЛЬНО сгенерировать новый!** |
| `EMERGENT_LLM_KEY` | `sk-emergent-70d3dE30484F46dC99` | `sk-emergent-70d3dE30484F46dC99` | Ключ для AI функций (опционально) | ✅ Оставить как есть |

**Как сгенерировать:**
```bash
# BOT_INSTANCE_ID
echo "production-$(date +%s)"

# BOT_SIGNATURE_KEY
openssl rand -base64 32
```

---

## 🎯 ИТОГОВАЯ ТАБЛИЦА: ЧТО НУЖНО ИЗМЕНИТЬ

| № | Параметр | Статус | Новое значение | Как сгенерировать |
|---|----------|--------|----------------|-------------------|
| 1 | `BOT_ENVIRONMENT` | 🔴 КРИТИЧНО | `production` | Вручную |
| 2 | `BOT_MODE` | 🔴 КРИТИЧНО | `webhook` | Вручную |
| 3 | `WEBHOOK_BASE_URL` | 🔴 КРИТИЧНО | `https://ваш-домен.com` | Ваш реальный домен |
| 4 | `DB_NAME` | 🔴 КРИТИЧНО | `telegram_shipping_bot_production` | Вручную |
| 5 | `DB_NAME_PRODUCTION` | 🔴 КРИТИЧНО | `telegram_shipping_bot_production` | Вручную |
| 6 | `TELEGRAM_BOT_TOKEN` | 🔴 КРИТИЧНО | `8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM` | Копировать из PROD_BOT_TOKEN |
| 7 | `ADMIN_API_KEY` | 🔴 КРИТИЧНО | `sk_admin_[новый]` | `openssl rand -hex 32` |
| 8 | `BOT_SIGNATURE_KEY` | 🔴 КРИТИЧНО | `[новый]` | `openssl rand -base64 32` |
| 9 | `BOT_INSTANCE_ID` | 🔴 КРИТИЧНО | `production-[timestamp]` | `echo "production-$(date +%s)"` |
| 10 | Все остальное | ✅ OK | Оставить как есть | - |

---

## 📝 ПОШАГОВАЯ ИНСТРУКЦИЯ

### Шаг 1: Сгенерируйте новые ключи

```bash
# Запустите эти команды и сохраните результаты
echo "ADMIN_API_KEY=sk_admin_$(openssl rand -hex 32)"
echo "BOT_SIGNATURE_KEY=$(openssl rand -base64 32)"
echo "BOT_INSTANCE_ID=production-$(date +%s)"
```

**Пример вывода:**
```
ADMIN_API_KEY=sk_admin_7a3f9c8e2d1b4a5f6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b
BOT_SIGNATURE_KEY=A8B7c6D5e4F3g2H1i0J9k8L7m6N5o4P3q2R1s0==
BOT_INSTANCE_ID=production-1737321600
```

### Шаг 2: Скопируйте шаблон

```bash
cp /app/backend/.env.production /app/backend/.env
```

### Шаг 3: Отредактируйте .env файл

Откройте файл и замените:

```bash
# 1. Окружение
BOT_ENVIRONMENT="production"
BOT_MODE="webhook"

# 2. Webhook URL
WEBHOOK_BASE_URL="https://ваш-реальный-домен.com"

# 3. База данных
DB_NAME="telegram_shipping_bot_production"
DB_NAME_PRODUCTION="telegram_shipping_bot_production"

# 4. Токен бота (Production)
TELEGRAM_BOT_TOKEN="8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM"

# 5. Вставьте сгенерированные ключи из Шага 1
ADMIN_API_KEY="sk_admin_7a3f9c8e2d1b4a5f..."
BOT_SIGNATURE_KEY="A8B7c6D5e4F3g2H1i0J9k8L7m6N5o4P3q2R1s0=="
BOT_INSTANCE_ID="production-1737321600"
```

### Шаг 4: Проверьте финальный .env

```bash
# Проверьте ключевые параметры
grep "BOT_ENVIRONMENT" /app/backend/.env
grep "BOT_MODE" /app/backend/.env
grep "WEBHOOK_BASE_URL" /app/backend/.env
grep "DB_NAME=" /app/backend/.env
grep "TELEGRAM_BOT_TOKEN" /app/backend/.env | head -1
```

**Должно быть:**
```
BOT_ENVIRONMENT="production"
BOT_MODE="webhook"
WEBHOOK_BASE_URL="https://ваш-домен.com"
DB_NAME="telegram_shipping_bot_production"
TELEGRAM_BOT_TOKEN="8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM"
```

### Шаг 5: Перезапустите бэкенд

```bash
sudo supervisorctl restart backend
```

### Шаг 6: Установите webhook (ПОСЛЕ ДЕПЛОЯ)

```bash
curl -X POST https://ваш-домен.com/api/bot-config/set-webhook \
  -H "x-api-key: ваш_новый_admin_api_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ваш-домен.com/api/telegram/webhook"}'
```

### Шаг 7: Настройте Oxapay

Зайдите в https://oxapay.com -> Merchant Dashboard:
```
Callback URL: https://ваш-домен.com/api/oxapay/webhook
```

---

## ✅ ФИНАЛЬНАЯ ПРОВЕРКА

После всех настроек проверьте:

```bash
# 1. Здоровье бота
curl https://ваш-домен.com/api/bot/health

# 2. Статус webhook
curl https://ваш-домен.com/api/bot-config/webhook-info \
  -H "x-api-key: ваш_новый_admin_api_key"

# 3. Статистика
curl https://ваш-домен.com/api/stats \
  -H "x-api-key: ваш_новый_admin_api_key"
```

**Ожидаемые результаты:**
1. Health: `{"status": "healthy", "bot_username": "whitelabel_shipping_bot"}`
2. Webhook: `{"url": "https://ваш-домен.com/api/telegram/webhook", "is_set": true}`
3. Stats: `{"total_users": 1, "total_orders": 0, ...}`

---

## 🚨 ВАЖНО!

### ❌ НЕ ДЕЛАЙТЕ:
- ❌ Не используйте HTTP (только HTTPS!)
- ❌ Не используйте Test ключи в Production
- ❌ Не используйте polling в Production
- ❌ Не используйте одну БД для Test и Production
- ❌ Не коммитьте .env в git

### ✅ ОБЯЗАТЕЛЬНО:
- ✅ Используйте HTTPS с валидным SSL сертификатом
- ✅ Сгенерируйте новые ключи безопасности
- ✅ Используйте webhook вместо polling
- ✅ Разделяйте БД для Test и Production
- ✅ Настройте Oxapay Callback URL
- ✅ Добавьте бота как админа в канал
- ✅ Проверьте все endpoints после деплоя
