# Deployment Configuration

## MongoDB Setup

This application uses **external MongoDB Atlas cluster** and does not require local MongoDB installation.

### Important Configuration

- **MONGO_URL**: Connection string to MongoDB Atlas
- **DB_NAME**: telegram_shipping_bot
- **Skip Migration**: MongoDB migration should be skipped during deployment

### Deployment Environment Variables

The following environment variables are required for deployment:

```
MONGO_URL=mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority&appName=Cluster0
DB_NAME=telegram_shipping_bot
TELEGRAM_BOT_TOKEN=8492458522:AAE3dLsl2blomb5WxP7w4S0bqvrs1M4WSsM
ADMIN_TELEGRAM_ID=7066790254
ADMIN_API_KEY=sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024
BOT_MODE=polling
BOT_ENVIRONMENT=production
```

### Deployment Files Created

1. `.deployment.yml` - Main deployment configuration
2. `.emergent.config.json` - Emergent platform configuration
3. `.platform/config.yml` - Platform-specific settings
4. `app.json` - Application manifest
5. `Procfile` - Process configuration
6. `skip_migration.sh` - MongoDB migration skip script
7. `runtime.txt` - Python runtime version

### Migration Skip

All configuration files explicitly specify that MongoDB migration should be skipped:
- `skip_migration: true`
- `use_external: true`
- `enabled: false`

This is necessary because the application uses an external MongoDB Atlas cluster instead of a local database.

## Troubleshooting

If deployment fails with MongoDB authentication error:
1. Verify MONGO_URL is correctly set in environment variables
2. Ensure skip_migration.sh is executable (`chmod +x`)
3. Check that all deployment configuration files are present
4. Verify MongoDB Atlas cluster is accessible from deployment environment
