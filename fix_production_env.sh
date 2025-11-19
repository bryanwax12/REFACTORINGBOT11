#!/bin/bash

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     🔧 АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ .env ДЛЯ PRODUCTION         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Проверка существования файла
if [ ! -f "/app/backend/.env" ]; then
    echo "❌ Файл /app/backend/.env не найден!"
    exit 1
fi

# Создание резервной копии
echo "📦 Создание резервной копии..."
cp /app/backend/.env /app/backend/.env.backup.before_production_$(date +%Y%m%d_%H%M%S)
echo "✅ Резервная копия создана"
echo ""

echo "🔄 Применение изменений для Production..."
echo ""

# Изменение BOT_ENVIRONMENT
sed -i 's/BOT_ENVIRONMENT="test"/BOT_ENVIRONMENT="production"/g' /app/backend/.env
echo "✅ BOT_ENVIRONMENT изменен на production"

# Изменение BOT_MODE
sed -i 's/BOT_MODE="polling"/BOT_MODE="webhook"/g' /app/backend/.env
echo "✅ BOT_MODE изменен на webhook"

# Изменение TELEGRAM_BOT_TOKEN на production токен
sed -i 's/TELEGRAM_BOT_TOKEN="8560388458:AAHxT-vYpImOpy49lMnaXpSHDM-vtnOn6ZE"/TELEGRAM_BOT_TOKEN="8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM"/g' /app/backend/.env
echo "✅ TELEGRAM_BOT_TOKEN изменен на production токен"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     📋 ПРОВЕРКА ОБНОВЛЕННЫХ ЗНАЧЕНИЙ                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
grep "BOT_ENVIRONMENT=" /app/backend/.env | head -1
grep "BOT_MODE=" /app/backend/.env | head -1
grep "TELEGRAM_BOT_TOKEN=" /app/backend/.env | head -1
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     ⚠️  ВАЖНО: WEBHOOK_BASE_URL                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Текущий WEBHOOK_BASE_URL:"
grep "WEBHOOK_BASE_URL=" /app/backend/.env | head -1
echo ""
echo "⚠️  Если это не ваш production домен, измените вручную:"
echo "   nano /app/backend/.env"
echo "   Найдите WEBHOOK_BASE_URL и замените на ваш домен"
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     🔄 СЛЕДУЮЩИЕ ШАГИ                                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "1. Если WEBHOOK_BASE_URL неправильный - исправьте его"
echo "2. Перезапустите backend:"
echo "   sudo supervisorctl restart backend"
echo ""
echo "3. После деплоя установите webhook:"
echo "   curl -X POST https://ваш-домен/api/bot-config/set-webhook \\"
echo "     -H 'x-api-key: ваш_admin_key' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"url\": \"https://ваш-домен/api/telegram/webhook\"}'"
echo ""
echo "✅ Готово!"
