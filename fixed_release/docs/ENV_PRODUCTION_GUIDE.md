# 🔧 Production Environment Configuration Guide

## 📋 Backend Environment Variables (`/app/backend/.env`)

```bash
# ============================================================
# TELEGRAM BOT CONFIGURATION
# ============================================================

# Production Bot Token (получить от @BotFather)
TELEGRAM_BOT_TOKEN_PRODUCTION="your_production_bot_token_here"

# Test Bot Token (для staging/preview)
TELEGRAM_BOT_TOKEN_TEST="your_test_bot_token_here"

# Admin Telegram ID (ваш личный ID)
ADMIN_TELEGRAM_ID="your_telegram_id_here"

# Channel Configuration
CHANNEL_INVITE_LINK="https://t.me/+your_channel_invite_link"
CHANNEL_ID="@your_channel_username"

# ============================================================
# BOT MODE CONFIGURATION
# ============================================================

# Режим работы: "webhook" для production, "polling" для dev
# ВАЖНО: В production всегда используйте webhook!
BOT_MODE="webhook"

# Webhook URL (автоматически определяется, но можно переопределить)
# Формат: https://your-domain.com
WEBHOOK_BASE_URL="https://your-production-domain.com"

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

# MongoDB Connection String
# КРИТИЧНО: НЕ изменяйте в production, используется Emergent managed MongoDB
MONGO_URL="mongodb://127.0.0.1:27017"

# Database Names
DB_NAME="telegram_shipping_bot"
DB_NAME_PRODUCTION="async-tg-bot-telegram_shipping_bot"
DB_NAME_PREVIEW="telegram_shipping_bot"

# ============================================================
# API KEYS - ADMIN & SECURITY
# ============================================================

# Admin API Key для защиты эндпоинтов
# ВАЖНО: Сгенерируйте уникальный ключ для production!
# Пример генерации: openssl rand -hex 32
ADMIN_API_KEY="sk_admin_YOUR_SECURE_KEY_HERE"

# ============================================================
# SHIPSTATION API CONFIGURATION
# ============================================================

# Production API Keys
SHIPSTATION_API_KEY_PRODUCTION="your_production_shipstation_key"
SHIPSTATION_API_SECRET_PRODUCTION="your_production_shipstation_secret"

# Test/Sandbox API Keys
SHIPSTATION_API_KEY_TEST="your_test_shipstation_key"
SHIPSTATION_API_SECRET_TEST="your_test_shipstation_secret"

# Legacy (для обратной совместимости, используется PRODUCTION по умолчанию)
SHIPSTATION_API_KEY="your_production_shipstation_key"
SHIPSTATION_API_SECRET="your_production_shipstation_secret"

# ============================================================
# PAYMENT GATEWAY - OXAPAY (Crypto Payments)
# ============================================================

# Oxapay API Key
OXAPAY_API_KEY="your_oxapay_api_key_here"

# Oxapay Merchant ID (если требуется)
OXAPAY_MERCHANT_ID="your_merchant_id"

# ВАЖНО: В Oxapay dashboard установите Callback URL:
# https://your-production-domain.com/api/oxapay/webhook

# ============================================================
# OPTIONAL: CryptoBot (Alternative Payment)
# ============================================================

# CryptoBot API Token (если используете)
# CRYPTOBOT_API_TOKEN="your_cryptobot_token"

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

# Log Level: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Production: INFO или WARNING
# Development: DEBUG
LOG_LEVEL="INFO"

# ============================================================
# RATE LIMITING & SECURITY
# ============================================================

# Rate Limiting (requests per minute)
RATE_LIMIT_PER_MINUTE="60"
RATE_LIMIT_PER_HOUR="1000"

# ============================================================
# PERFORMANCE & OPTIMIZATION
# ============================================================

# MongoDB Connection Pool
MONGO_MAX_POOL_SIZE="50"
MONGO_MIN_POOL_SIZE="10"

# Session TTL (minutes)
SESSION_TTL_MINUTES="15"

# ============================================================
# FEATURE FLAGS (Optional)
# ============================================================

# Maintenance Mode
MAINTENANCE_MODE="false"

# Enable/Disable Features
ENABLE_REFERRAL_SYSTEM="false"
ENABLE_DISCOUNT_SYSTEM="true"

# ============================================================
# NOTES FOR PRODUCTION
# ============================================================

# 1. НИКОГДА не коммитьте .env файл в git!
# 2. Используйте webhook mode в production (быстрее и стабильнее)
# 3. Регулярно ротируйте ADMIN_API_KEY
# 4. Мониторьте логи: tail -f /var/log/supervisor/backend.out.log
# 5. Проверяйте Oxapay Callback URL в их dashboard
# 6. Для production используйте HTTPS (обязательно для webhook)
```

---

## 📋 Frontend Environment Variables (`/app/frontend/.env`)

```bash
# ============================================================
# BACKEND API CONFIGURATION
# ============================================================

# Backend URL - автоматически настраивается Emergent
# НЕ изменяйте вручную!
REACT_APP_BACKEND_URL=https://your-production-domain.com

# ============================================================
# FEATURE FLAGS (Optional)
# ============================================================

# Enable Analytics (если используете)
# REACT_APP_ENABLE_ANALYTICS=true

# ============================================================
# NOTES FOR PRODUCTION
# ============================================================

# 1. REACT_APP_BACKEND_URL автоматически управляется Emergent
# 2. Все переменные должны начинаться с REACT_APP_
# 3. После изменения .env нужен rebuild frontend
```

---

## 🚀 Production Deployment Checklist

### Перед деплоем:

- [ ] Обновить `TELEGRAM_BOT_TOKEN_PRODUCTION` в backend/.env
- [ ] Установить `BOT_MODE="webhook"` в backend/.env
- [ ] Сгенерировать уникальный `ADMIN_API_KEY`
- [ ] Добавить production `SHIPSTATION_API_KEY_PRODUCTION`
- [ ] Добавить `OXAPAY_API_KEY`
- [ ] Установить `LOG_LEVEL="INFO"`
- [ ] Проверить `WEBHOOK_BASE_URL` (должен быть ваш production домен)

### После деплоя:

- [ ] Проверить, что бот работает: отправить /start в Telegram
- [ ] Зайти в Oxapay dashboard → установить Callback URL
- [ ] Проверить админ-панель: все кнопки работают
- [ ] Отправить тестовое уведомление (Add Balance)
- [ ] Проверить логи: `tail -f /var/log/supervisor/backend.out.log`
- [ ] Провести тестовый платеж через Oxapay
- [ ] Создать тестовый заказ и получить shipping label

### Мониторинг:

- [ ] Настроить алерты на ошибки в логах
- [ ] Мониторить баланс ShipStation API
- [ ] Проверять webhook delivery в Oxapay dashboard
- [ ] Мониторить rate limiting (если много пользователей)

---

## 🔐 Security Best Practices

1. **API Keys**:
   - Никогда не коммитьте .env в git
   - Регулярно ротируйте ключи (раз в 3-6 месяцев)
   - Используйте разные ключи для test/production

2. **Webhook Security**:
   - Используйте HTTPS (обязательно!)
   - Верифицируйте webhook подписи (TODO в коде)
   - Логируйте все входящие webhooks

3. **Rate Limiting**:
   - Настройте защиту от DDoS
   - Мониторьте suspicious activity
   - Используйте Redis для distributed rate limiting (в будущем)

4. **Database**:
   - Регулярные бэкапы MongoDB
   - Настройте индексы (уже сделано в startup_event)
   - Мониторьте размер БД

---

## 📊 Environment Detection

Система автоматически определяет окружение по `WEBHOOK_BASE_URL`:

```python
# Production
if 'your-production-domain.com' in webhook_base_url:
    environment = "PRODUCTION"
    bot_token = TELEGRAM_BOT_TOKEN_PRODUCTION
    db_name = DB_NAME_PRODUCTION
    
# Preview/Test
else:
    environment = "TEST"
    bot_token = TELEGRAM_BOT_TOKEN_TEST
    db_name = DB_NAME_PREVIEW
```

---

## 🐛 Troubleshooting

### Webhook не работает:
1. Проверить HTTPS (обязателен для webhook)
2. Проверить `WEBHOOK_BASE_URL` в .env
3. Проверить логи: `tail -f /var/log/supervisor/backend.err.log`
4. Тест webhook: `curl -X POST https://your-domain.com/api/telegram/webhook`

### Oxapay webhooks не приходят:
1. Зайти в Oxapay dashboard
2. Проверить Callback URL: `https://your-domain.com/api/oxapay/webhook`
3. Проверить логи webhook delivery в Oxapay
4. Тест: создать тестовый платеж

### Уведомления не отправляются:
1. Проверить `bot_instance` в логах: должно быть "AVAILABLE"
2. Проверить, что bot не запущен в нескольких местах (conflict error)
3. Проверить права бота в Telegram

---

## 📞 Support

При проблемах:
1. Проверить логи: `/var/log/supervisor/backend.out.log`
2. Проверить ошибки: `/var/log/supervisor/backend.err.log`
3. Проверить статус: `sudo supervisorctl status`
