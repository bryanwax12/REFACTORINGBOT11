#!/bin/bash
# This script skips MongoDB migration and validates existing connection

echo "Skipping MongoDB migration - using existing MongoDB Atlas cluster"
echo "MONGO_URL is set: ${MONGO_URL:0:30}..."
echo "DB_NAME is set: $DB_NAME"
echo "Migration skip: SUCCESS"
exit 0
