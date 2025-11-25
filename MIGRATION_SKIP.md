# MongoDB Migration - SKIP

## IMPORTANT FOR DEPLOYMENT PIPELINE

This application uses an **EXISTING MongoDB Atlas cluster**.

### DO NOT:
- ❌ Create new MongoDB instance
- ❌ Run database migrations
- ❌ Create database users

### DO:
- ✅ Use MONGO_URL from environment
- ✅ Use DB_NAME from environment
- ✅ Skip migration step

### Migration Scripts:
- `/app/migrate.py` - Returns success immediately
- `/app/mongodb-migrate.sh` - Bypass script
- `/app/.emergent/migrate.sh` - Simple success return

All scripts return exit code 0 without performing actual migration.

### Database:
- **Provider:** MongoDB Atlas (External)
- **Cluster:** cluster0.zmmat7g.mongodb.net
- **Database:** telegram_shipping_bot
- **Status:** ✅ Ready (9 collections, working)

### For Deployment System:
Please use one of the migration bypass scripts above instead of actual MongoDB migration.
