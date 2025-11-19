# 🚀 Quick Commands для Production

## 📝 Генерация ключей безопасности

```bash
# Генерация Admin API Key
echo "ADMIN_API_KEY=\"sk_admin_$(openssl rand -hex 32)\""

# Генерация Bot Signature Key
echo "BOT_SIGNATURE_KEY=\"$(openssl rand -base64 32)\""

# Генерация Instance ID
echo "BOT_INSTANCE_ID=\"production-$(date +%s)\""
```

## 🔧 Настройка Webhook

```bash
# Установка webhook
curl -X POST https://YOUR_DOMAIN/api/bot-config/set-webhook \
  -H "x-api-key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://YOUR_DOMAIN/api/telegram/webhook"}'

# Проверка webhook
curl https://YOUR_DOMAIN/api/bot-config/webhook-info \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Удаление webhook
curl -X POST https://YOUR_DOMAIN/api/bot-config/delete-webhook \
  -H "x-api-key: YOUR_ADMIN_KEY"
```

## 🔍 Проверка статуса

```bash
# Здоровье бота
curl https://YOUR_DOMAIN/api/bot/health

# Метрики
curl https://YOUR_DOMAIN/api/bot/metrics \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Логи (последние 50 строк)
curl https://YOUR_DOMAIN/api/bot/logs?lines=50 \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Статистика
curl https://YOUR_DOMAIN/api/stats \
  -H "x-api-key: YOUR_ADMIN_KEY"
```

## 🔄 Управление ботом

```bash
# Перезагрузка бота
curl -X POST https://YOUR_DOMAIN/api/bot/restart \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Включить режим обслуживания
curl -X POST https://YOUR_DOMAIN/api/maintenance/enable \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Выключить режим обслуживания
curl -X POST https://YOUR_DOMAIN/api/maintenance/disable \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Проверить режим обслуживания
curl https://YOUR_DOMAIN/api/maintenance/status
```

## 📢 Рассылки

```bash
# Рассылка всем пользователям
curl -X POST https://YOUR_DOMAIN/api/broadcast \
  -H "x-api-key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Ваше сообщение",
    "target": "all"
  }'

# Рассылка только активным пользователям
curl -X POST https://YOUR_DOMAIN/api/broadcast \
  -H "x-api-key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Ваше сообщение",
    "target": "active"
  }'

# Рассылка с изображением
curl -X POST https://YOUR_DOMAIN/api/broadcast \
  -H "x-api-key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Ваше сообщение",
    "target": "all",
    "image_url": "https://example.com/image.jpg"
  }'
```

## 👥 Управление пользователями

```bash
# Список всех пользователей
curl https://YOUR_DOMAIN/api/users \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Детали пользователя
curl https://YOUR_DOMAIN/api/users/TELEGRAM_ID/details \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Добавить баланс
curl -X POST https://YOUR_DOMAIN/api/admin/users/TELEGRAM_ID/balance/add \
  -H "x-api-key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"amount": 100, "notify": true}'

# Вычесть баланс
curl -X POST https://YOUR_DOMAIN/api/admin/users/TELEGRAM_ID/balance/deduct \
  -H "x-api-key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"amount": 50, "notify": true}'
```

## 📦 Управление заказами

```bash
# Список всех заказов
curl https://YOUR_DOMAIN/api/orders \
  -H "x-api-key: YOUR_ADMIN_KEY"

# Детали заказа
curl https://YOUR_DOMAIN/api/orders/ORDER_ID \
  -H "x-api-key: YOUR_ADMIN_KEY"
```

## 🔒 Замена ключей в .env

```bash
# 1. Сгенерируйте новые ключи
NEW_ADMIN_KEY="sk_admin_$(openssl rand -hex 32)"
NEW_SIG_KEY="$(openssl rand -base64 32)"
NEW_INSTANCE="production-$(date +%s)"

# 2. Выведите их на экран
echo "Новые ключи:"
echo "ADMIN_API_KEY=\"$NEW_ADMIN_KEY\""
echo "BOT_SIGNATURE_KEY=\"$NEW_SIG_KEY\""
echo "BOT_INSTANCE_ID=\"$NEW_INSTANCE\""

# 3. Вручную замените в /app/backend/.env

# 4. Перезагрузите бэкенд
sudo supervisorctl restart backend
```

## 🗄️ Backup базы данных

```bash
# Создание backup
mongodump --db telegram_shipping_bot_production --out /backup/$(date +%Y%m%d)

# Восстановление из backup
mongorestore --db telegram_shipping_bot_production /backup/20250119/telegram_shipping_bot_production
```

## 📊 Мониторинг в реальном времени

```bash
# Следить за логами бэкенда
tail -f /var/log/supervisor/backend.out.log

# Следить за логами ошибок
tail -f /var/log/supervisor/backend.err.log

# Статус всех сервисов
sudo supervisorctl status
```

## 🚨 Экстренное восстановление

```bash
# Остановить все сервисы
sudo supervisorctl stop all

# Запустить только MongoDB
sudo supervisorctl start mongodb

# Запустить бэкенд
sudo supervisorctl start backend

# Запустить frontend
sudo supervisorctl start frontend

# Проверить статус
sudo supervisorctl status
```
