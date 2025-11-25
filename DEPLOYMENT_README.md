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
MONGO_URL=<your_mongodb_atlas_connection_string>
DB_NAME=telegram_shipping_bot
TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
ADMIN_TELEGRAM_ID=<your_admin_telegram_id>
ADMIN_API_KEY=<your_admin_api_key>
BOT_MODE=polling
BOT_ENVIRONMENT=production
```

**Note:** All credentials should be configured via your deployment platform's environment variables, NOT hardcoded in files.

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
