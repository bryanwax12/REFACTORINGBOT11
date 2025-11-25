#!/bin/bash
set -e

echo "==================================="
echo "Starting Telegram Shipping Bot"
echo "==================================="

# Load environment variables
export MONGO_URL="${MONGO_URL:-mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority&appName=Cluster0}"
export DB_NAME="${DB_NAME:-telegram_shipping_bot}"

echo "✅ Environment loaded"
echo "   MongoDB: External (MongoDB Atlas)"
echo "   Database: $DB_NAME"
echo ""

# Start the application
exec uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
