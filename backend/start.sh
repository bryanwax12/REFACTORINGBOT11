#!/bin/bash
set -e

echo "==================================="
echo "Starting Telegram Shipping Bot"
echo "==================================="

echo "✅ Environment ready"
echo ""

# Start the application
exec uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
