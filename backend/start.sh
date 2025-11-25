#!/bin/bash
set -e

echo "==================================="
echo "Starting Telegram Shipping Bot"
echo "==================================="

echo "✅ Environment ready"
echo ""

# Use PORT environment variable if provided by deployment platform, otherwise default to 8001
PORT=${PORT:-8001}
echo "🚀 Starting on port: $PORT"

# Start the application
exec uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1
