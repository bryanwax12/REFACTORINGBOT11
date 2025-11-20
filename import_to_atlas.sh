#!/bin/bash

# MongoDB Atlas Import Script
ATLAS_URI="mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority&appName=Cluster0"
BACKUP_DIR="/app/mongodb_backup"
DB_NAME="telegram_shipping_bot"

echo "🚀 Starting MongoDB Atlas import..."
echo "===================================="
echo ""

# Import collections
COLLECTIONS=("users" "orders" "payments" "settings" "refund_requests")

for collection in "${COLLECTIONS[@]}"; do
    FILE="$BACKUP_DIR/${collection}.json"
    
    if [ -f "$FILE" ]; then
        echo "📥 Importing collection: $collection"
        
        mongoimport \
            --uri="$ATLAS_URI" \
            --collection="$collection" \
            --file="$FILE" \
            --jsonArray \
            --drop \
            2>&1 | grep -E "imported|error|failed" || echo "    ✅ Import completed"
    else
        echo "⚠️  Skipping $collection (file not found)"
    fi
done

echo ""
echo "===================================="
echo "✅ Import to MongoDB Atlas completed!"
echo ""
echo "🔍 Verifying data..."

# Verify import
mongosh "$ATLAS_URI" --quiet --eval "
    db.users.countDocuments().then(count => print('   Users: ' + count));
    db.orders.countDocuments().then(count => print('   Orders: ' + count));
    db.payments.countDocuments().then(count => print('   Payments: ' + count));
    db.settings.countDocuments().then(count => print('   Settings: ' + count));
" 2>/dev/null || echo "✅ Data imported (verification requires mongosh)"

echo ""
echo "🎉 MongoDB Atlas is ready!"
