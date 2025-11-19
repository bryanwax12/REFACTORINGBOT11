#!/bin/bash

echo "════════════════════════════════════════════════════════════════"
echo "  🔑 АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ И УСТАНОВКА КЛЮЧЕЙ"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Генерация новых ключей
NEW_ADMIN_KEY="sk_admin_$(openssl rand -hex 32)"
NEW_SIGNATURE_KEY="$(openssl rand -base64 32)"
NEW_INSTANCE_ID="production-$(date +%s)"

echo "✅ Сгенерированы новые ключи:"
echo ""
echo "ADMIN_API_KEY=\"$NEW_ADMIN_KEY\""
echo "BOT_SIGNATURE_KEY=\"$NEW_SIGNATURE_KEY\""
echo "BOT_INSTANCE_ID=\"$NEW_INSTANCE_ID\""
echo ""

# Проверка существования файла
if [ ! -f "/app/backend/.env" ]; then
    echo "❌ Файл /app/backend/.env не найден!"
    echo "📝 Создайте его сначала: cp /app/backend/.env.production.example /app/backend/.env"
    exit 1
fi

# Создание резервной копии
echo "📦 Создание резервной копии .env..."
cp /app/backend/.env /app/backend/.env.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Резервная копия создана"
echo ""

# Замена ключей в .env
echo "🔄 Обновление ключей в .env файле..."

# Замена ADMIN_API_KEY
sed -i "s|ADMIN_API_KEY=.*|ADMIN_API_KEY=\"$NEW_ADMIN_KEY\"|g" /app/backend/.env

# Замена BOT_SIGNATURE_KEY
sed -i "s|BOT_SIGNATURE_KEY=.*|BOT_SIGNATURE_KEY=\"$NEW_SIGNATURE_KEY\"|g" /app/backend/.env

# Замена BOT_INSTANCE_ID
sed -i "s|BOT_INSTANCE_ID=.*|BOT_INSTANCE_ID=\"$NEW_INSTANCE_ID\"|g" /app/backend/.env

echo "✅ Ключи обновлены в .env файле"
echo ""

# Показать обновленные значения
echo "════════════════════════════════════════════════════════════════"
echo "  📋 ПРОВЕРКА ОБНОВЛЕННЫХ ЗНАЧЕНИЙ:"
echo "════════════════════════════════════════════════════════════════"
echo ""
grep "ADMIN_API_KEY" /app/backend/.env
grep "BOT_SIGNATURE_KEY" /app/backend/.env
grep "BOT_INSTANCE_ID" /app/backend/.env
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  ⚠️  ВАЖНО: Сохраните эти ключи в безопасном месте!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "ADMIN_API_KEY=\"$NEW_ADMIN_KEY\""
echo "BOT_SIGNATURE_KEY=\"$NEW_SIGNATURE_KEY\""
echo "BOT_INSTANCE_ID=\"$NEW_INSTANCE_ID\""
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  🔄 Перезапустить бэкенд?"
echo "════════════════════════════════════════════════════════════════"
read -p "Перезапустить backend сейчас? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Перезапуск backend..."
    sudo supervisorctl restart backend
    sleep 3
    sudo supervisorctl status backend
    echo "✅ Backend перезапущен"
else
    echo "⏭️  Пропущено. Перезапустите вручную позже:"
    echo "   sudo supervisorctl restart backend"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ ГОТОВО!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📝 Резервная копия старого .env сохранена в:"
ls -t /app/backend/.env.backup.* | head -1
echo ""
