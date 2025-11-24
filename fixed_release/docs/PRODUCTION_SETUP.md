# 🚀 Production Setup Guide

## 📋 Чек-лист перед деплоем

### 1️⃣ Подготовка .env файла

```bash
# Скопируйте шаблон production конфига
cp /app/backend/.env.production /app/backend/.env
```

### 2️⃣ Обязательные изменения в .env

**⚠️ КРИТИЧЕСКИ ВАЖНО:**

#### А. Окружение бота
```bash
BOT_ENVIRONMENT="production"  # Обязательно!
BOT_MODE="webhook"            # Обязательно для production!
```

#### Б. Webhook URL
```bash
# Замените на ваш реальный домен с HTTPS
WEBHOOK_BASE_URL="https://your-actual-domain.com"
```

#### В. База данных
```bash
# Используйте отдельную БД для production
DB_NAME="telegram_shipping_bot_production"
DB_NAME_PRODUCTION="telegram_shipping_bot_production"
```

#### Г. Безопасность
```bash
# Сгенерируйте новый Admin API ключ
ADMIN_API_KEY="sk_admin_$(openssl rand -hex 32)"

# Сгенерируйте новый Signature Key
BOT_SIGNATURE_KEY="$(openssl rand -base64 32)"

# Уникальный Instance ID
BOT_INSTANCE_ID="production-$(date +%s)"
```

---

## 🔐 Настройка внешних сервисов

### 1. Oxapay Webhook
Зайдите в https://oxapay.com -> Merchant Dashboard:
```
Callback URL: https://your-domain.com/api/oxapay/webhook
```

### 2. ShipStation API
- Используйте **Production API Key**, не Test!
- Получить: https://ss.shipstation.com -> Settings -> API Settings

### 3. Telegram Channel
- Добавьте бота как **администратора** в ваш канал
- Получите Channel ID (формат: -100XXXXXXXXXX)
- Обновите `CHANNEL_ID` и `CHANNEL_INVITE_LINK`

---

## 🚀 Запуск в Production

### Шаг 1: Установка Webhook

После деплоя, установите webhook для Telegram:

```bash
# Через API (с вашим admin ключом)
curl -X POST https://your-domain.com/api/bot-config/set-webhook \
  -H "x-api-key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-domain.com/api/telegram/webhook",
    "drop_pending_updates": false
  }'
```

### Шаг 2: Проверка статуса

```bash
# Проверка здоровья бота
curl https://your-domain.com/api/bot/health

# Проверка webhook
curl https://your-domain.com/api/bot-config/webhook-info \
  -H "x-api-key: YOUR_ADMIN_API_KEY"
```

### Шаг 3: Проверка базы данных

```bash
# Проверка статистики
curl https://your-domain.com/api/stats \
  -H "x-api-key: YOUR_ADMIN_API_KEY"
```

---

## ⚙️ Различия между Test и Production

| Параметр | Test (Preview) | Production |
|----------|----------------|------------|
| `BOT_ENVIRONMENT` | `test` | `production` |
| `BOT_MODE` | `polling` | `webhook` |
| `BOT_TOKEN` | `TEST_BOT_TOKEN` | `PROD_BOT_TOKEN` |
| `DB_NAME` | `telegram_shipping_bot` | `telegram_shipping_bot_production` |
| `SHIPSTATION_API_KEY` | `TEST_*` | Production ключ |
| `WEBHOOK_BASE_URL` | Preview URL | Ваш домен |

---

## 🔧 Troubleshooting

### Проблема: Бот не получает сообщения

**Решение:**
1. Проверьте webhook статус:
   ```bash
   curl https://your-domain.com/api/bot-config/webhook-info \
     -H "x-api-key: YOUR_ADMIN_API_KEY"
   ```

2. Убедитесь что URL доступен извне:
   ```bash
   curl https://your-domain.com/api/bot/health
   ```

3. Проверьте логи:
   ```bash
   # В Emergent: перейдите в Monitoring -> Logs
   # Или через API:
   curl https://your-domain.com/api/bot/logs?lines=100 \
     -H "x-api-key: YOUR_ADMIN_API_KEY"
   ```

### Проблема: Webhook не работает

**Возможные причины:**
- ❌ Нет SSL сертификата (HTTPS обязателен!)
- ❌ `BOT_MODE` не установлен в `webhook`
- ❌ Неправильный `WEBHOOK_BASE_URL`
- ❌ Порт не открыт / файрвол блокирует

**Решение:**
```bash
# Переустановите webhook
curl -X POST https://your-domain.com/api/bot-config/delete-webhook \
  -H "x-api-key: YOUR_ADMIN_API_KEY"

# Затем установите снова
curl -X POST https://your-domain.com/api/bot-config/set-webhook \
  -H "x-api-key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/api/telegram/webhook"}'
```

### Проблема: Oxapay webhook не приходит

**Решение:**
1. Проверьте Callback URL в панели Oxapay
2. URL должен быть: `https://your-domain.com/api/oxapay/webhook`
3. Проверьте логи webhooks в панели Oxapay

---

## 📊 Мониторинг

### Здоровье системы
```bash
curl https://your-domain.com/api/bot/health
```

### Метрики
```bash
curl https://your-domain.com/api/bot/metrics \
  -H "x-api-key: YOUR_ADMIN_API_KEY"
```

### Логи
```bash
curl https://your-domain.com/api/bot/logs?lines=100 \
  -H "x-api-key: YOUR_ADMIN_API_KEY"
```

---

## 🔒 Безопасность

### Защищенные endpoints (требуют x-api-key)
- ✅ `/api/bot/restart` - перезагрузка
- ✅ `/api/maintenance/*` - режим обслуживания
- ✅ `/settings/api-mode` (POST) - изменение режима API
- ✅ `/api/broadcast` - рассылки
- ✅ `/api/upload-image` - загрузка файлов
- ✅ Все `/api/admin/*` endpoints

### Публичные endpoints (не требуют ключ)
- ✅ `/api/bot/health` - проверка здоровья
- ✅ `/api/telegram/webhook` - webhook от Telegram
- ✅ `/api/oxapay/webhook` - webhook от Oxapay

---

## 📝 Важные замечания

1. **HTTPS обязателен** для production - Telegram не работает с HTTP
2. **Webhook vs Polling**: В production используйте только webhook
3. **Разделяйте БД**: Test и Production должны использовать разные базы данных
4. **API ключи**: Используйте Production ключи, не Test
5. **Backup**: Регулярно делайте бэкапы MongoDB
6. **Мониторинг**: Настройте алерты для критических ошибок

---

## 🆘 Поддержка

Если возникли проблемы:
1. Проверьте логи: `/api/bot/logs`
2. Проверьте webhook статус: `/api/bot-config/webhook-info`
3. Проверьте здоровье: `/api/bot/health`
4. Обратитесь к документации Telegram Bot API: https://core.telegram.org/bots/api

---

## ✅ Финальный чек-лист

Перед запуском убедитесь что:

- [ ] `.env` файл настроен с правильными значениями
- [ ] `BOT_ENVIRONMENT="production"`
- [ ] `BOT_MODE="webhook"`
- [ ] `WEBHOOK_BASE_URL` указывает на ваш домен с HTTPS
- [ ] Новый `ADMIN_API_KEY` сгенерирован
- [ ] Новый `BOT_SIGNATURE_KEY` сгенерирован
- [ ] `DB_NAME` использует production базу
- [ ] ShipStation использует Production API Key
- [ ] Бот добавлен как админ в Telegram канал
- [ ] Callback URL настроен в Oxapay
- [ ] SSL сертификат установлен и работает
- [ ] Webhook установлен и проверен
- [ ] Базовые endpoints отвечают корректно

🎉 **Готово! Ваш бот готов к production!**
