#!/bin/bash
set -e

echo "==================================="
echo "Starting Telegram Shipping Bot"
echo "==================================="

# WORKAROUND: Allow both EXTERNAL_MONGO_URL and MONGO_URL
if [ -n "$EXTERNAL_MONGO_URL" ]; then
    echo "✅ Using EXTERNAL_MONGO_URL (MongoDB Atlas)"
elif [ -n "$MONGO_URL" ]; then
    echo "✅ Using MONGO_URL (Fallback or Emergent managed)"
else
    echo "⚠️ WARNING: No MongoDB URL configured"
    echo "   Application will start but database features will be disabled"
fi

if [ -n "$DB_NAME" ]; then
    echo "   Database: $DB_NAME"
fi

echo ""

# Start the application
exec uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
