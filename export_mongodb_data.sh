#!/bin/bash

# MongoDB Data Export Script
# This script exports all data from local MongoDB to prepare for Atlas migration

EXPORT_DIR="/app/mongodb_backup"
MONGO_HOST="localhost"
MONGO_PORT="27017"
DB_NAME="telegram_shipping_bot"

echo "🔵 Starting MongoDB data export..."
echo "=================================="

# Create export directory
mkdir -p "$EXPORT_DIR"

# Export collections
echo ""
echo "📦 Exporting collections from database: $DB_NAME"

# List of collections to export
COLLECTIONS=("users" "orders" "payments" "settings" "refund_requests")

for collection in "${COLLECTIONS[@]}"; do
    echo "  → Exporting collection: $collection"
    mongoexport \
        --host="$MONGO_HOST" \
        --port="$MONGO_PORT" \
        --db="$DB_NAME" \
        --collection="$collection" \
        --out="$EXPORT_DIR/${collection}.json" \
        --jsonArray \
        2>/dev/null
    
    if [ $? -eq 0 ]; then
        COUNT=$(grep -o '{' "$EXPORT_DIR/${collection}.json" | wc -l)
        echo "    ✅ Exported $COUNT documents"
    else
        echo "    ⚠️  Collection not found or empty"
    fi
done

echo ""
echo "=================================="
echo "✅ Export completed!"
echo ""
echo "📁 Backup location: $EXPORT_DIR"
echo "📊 Files created:"
ls -lh "$EXPORT_DIR"/*.json 2>/dev/null | awk '{print "   ", $9, "-", $5}'

echo ""
echo "🔄 Next step: Import these files to MongoDB Atlas"
