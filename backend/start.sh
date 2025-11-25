#!/bin/bash
set -e

echo "==================================="
echo "Starting Telegram Shipping Bot"
echo "==================================="

# Ensure critical environment variables are set
if [ -z "$MONGO_URL" ]; then
    echo "❌ ERROR: MONGO_URL environment variable is not set"
    exit 1
fi

if [ -z "$DB_NAME" ]; then
    echo "❌ ERROR: DB_NAME environment variable is not set"
    exit 1
fi

echo "✅ Environment validated"
echo "   MongoDB: External (MongoDB Atlas)"
echo "   Database: $DB_NAME"
echo ""

# Start the application
exec uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
