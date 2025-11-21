# ✅ Чеклист для деплоя на Emergent

## Обязательные переменные окружения для Production

При настройке деплоя на платформе Emergent, убедитесь, что установлены следующие переменные:

### 1. 🗄️ База данных (КРИТИЧНО!)
```
MONGO_URL=mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority
```
**Важно:** Это MongoDB Atlas M10 кластер. НЕ используйте `mongodb://localhost:27017`!

### 2. 🌐 Webhook URL
```
WEBHOOK_BASE_URL=https://telegram-admin-fix-2.emergent.host
```
**Важно:** Должен соответствовать URL вашего деплоя!

### 3. 🤖 Telegram Bot Token
```
TELEGRAM_BOT_TOKEN=8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM
```

### 4. 🔑 Admin API Key
```
ADMIN_API_KEY=sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024
```

### 5. 📦 ShipStation API Keys
```
SHIPSTATION_API_KEY=P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g
SHIPSTATION_API_KEY_TEST=TEST_3NFykGjeVRke57QiCtJzEOq2ZVsXBrWgOvCNrwcwGU8
SHIPSTATION_API_KEY_PROD=P9tNKoBVBHpcnq2riwwG4AG/SUG9sZVZaYSJ0alfG0g
```

### 6. 💰 Payment API Keys
```
OXAPAY_API_KEY=AIQ2XA-A4ASEL-5HTMND-6WJ2YK
CRYPTOBOT_TOKEN=480059:AA2YcX1suWsXPDHFXJMctgNNntwvug8TINJ
```

### 7. 👤 Admin & Channel
```
ADMIN_TELEGRAM_ID=7066790254
CHANNEL_ID=-1003417145879
CHANNEL_INVITE_LINK=https://t.me/WHITE_LABEL_SHIPPING_BOTCHANNEL
```

### 8. ⚙️ Bot Configuration
```
BOT_ENVIRONMENT=production
BOT_MODE=webhook
```

---

## ⚠️ Известные проблемы платформы Emergent

### Проблема: "Склейка" переменных окружения

Платформа Emergent имеет известный баг, при котором переменные окружения могут "склеиваться" вместе, создавая невалидные значения.

**Пример:**
```
MONGO_URL="value1"REACT_APP_BACKEND_URL="value2"
```

### Решение (уже реализовано в коде):

1. **Файл workaround:** `/app/backend/config_production.py`
   - Содержит "чистые" значения всех критических переменных
   - Используется как fallback если ENV переменные повреждены

2. **Автоматическая детекция:** `/app/backend/server.py` (строки 14-55)
   - Проверяет каждую критическую переменную на "склейку"
   - Автоматически использует `config_production.py` если обнаружена проблема
   - Логирует: `⚠️ Using production config for {key} (env var corrupted or missing)`

### Как проверить, что workaround работает:

После деплоя проверьте логи приложения:
- ✅ `Using env variable for MONGO_URL` - переменная нормальная
- ⚠️ `Using production config for MONGO_URL` - используется workaround

---

## 🧪 Тестирование после деплоя

### 1. Проверка webhook
```bash
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo" | jq
```

Должно показать:
```json
{
  "url": "https://telegram-admin-fix-2.emergent.host/api/telegram/webhook",
  "pending_update_count": 0
}
```

### 2. Проверка MongoDB подключения
Отправьте `/start` в боте. Если получили главное меню - подключение работает!

### 3. Проверка API
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>" \
  https://telegram-admin-fix-2.emergent.host/api/stats
```

---

## 🚨 Если что-то не работает

### 1. Бот не отвечает на /start

**Проверьте логи деплоя:**
- Ищите: `⚠️ Using production config` - workaround сработал
- Ищите: `✅ Webhook set successfully` - webhook зарегистрирован
- Ищите ошибки подключения к MongoDB

**Возможные причины:**
- ❌ MONGO_URL указывает на localhost вместо Atlas
- ❌ WEBHOOK_BASE_URL неправильный
- ❌ Переменные окружения склеились (должен сработать workaround)

### 2. Админ-панель показывает "Failed to load data"

**Причина:** Проблема с ADMIN_API_KEY или CORS

**Решение:**
- Проверьте, что ADMIN_API_KEY в деплое совпадает с ключом в фронтенде
- CORS уже настроен на `*` в `/app/backend/server.py`

---

## 📋 Финальный чеклист перед деплоем

- [ ] MONGO_URL содержит Atlas URL (не localhost)
- [ ] WEBHOOK_BASE_URL соответствует URL деплоя
- [ ] Все API ключи заполнены
- [ ] BOT_MODE=webhook, BOT_ENVIRONMENT=production
- [ ] Файл `config_production.py` существует (workaround для бага платформы)
- [ ] После деплоя: проверить логи на наличие ошибок
- [ ] После деплоя: протестировать `/start` в боте
- [ ] После деплоя: проверить админ-панель

---

**Дата создания:** 21.11.2025  
**Версия:** 1.0  
**Платформа:** Emergent (Kubernetes)
