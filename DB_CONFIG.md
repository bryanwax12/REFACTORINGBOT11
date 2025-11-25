# MongoDB Configuration

## IMPORTANT: External MongoDB Atlas

This application uses an **EXISTING MongoDB Atlas cluster**.

### Configuration:
- **Provider:** MongoDB Atlas (External)
- **Managed by Emergent:** NO
- **Migration Required:** NO
- **Connection:** Via MONGO_URL environment variable

### Environment Variables Required:
```bash
MONGO_URL=mongodb+srv://bbeardy3_db_user:***@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot
DB_NAME=telegram_shipping_bot
```

### Database Details:
- **Cluster:** cluster0.zmmat7g.mongodb.net
- **Database:** telegram_shipping_bot
- **User:** bbeardy3_db_user
- **Collections:** 9 (users, orders, templates, etc.)

### Deployment Instructions:
1. DO NOT create new MongoDB instance
2. DO NOT run migrations
3. USE existing MONGO_URL from environment
4. Connection verified in preview mode ✅

### Verification:
Run `/app/backend/verify_mongodb.py` to test connection
