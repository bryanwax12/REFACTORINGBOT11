# Deployment Configuration

## MongoDB Configuration

**IMPORTANT:** This application uses an **existing MongoDB Atlas cluster**.

### Configuration Details:

- **Type:** External MongoDB Atlas
- **Managed by Emergent:** NO
- **Migration Required:** NO
- **Connection:** Via MONGO_URL environment variable

### Environment Variables:

```bash
MONGO_URL=mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority&appName=Cluster0
DB_NAME=telegram_shipping_bot
```

### Deployment Steps:

1. **SKIP MongoDB migration step** - Database already exists and is configured
2. Use MONGO_URL from environment variables
3. Connect to existing cluster: `cluster0.zmmat7g.mongodb.net`
4. Use existing database: `telegram_shipping_bot`

### Configuration Files:

- `/app/emergent.yml` - Specifies managed: false
- `/app/.deployer.yml` - Skip migration flags
- `/app/.emergent/emergent.yml` - Database configuration
- `/app/deployment.config.json` - Skip migration steps

### Notes:

- Database connection tested and working in preview mode
- No migration or user creation needed
- All collections already exist
- Application ready to connect immediately
