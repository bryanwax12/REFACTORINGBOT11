# Emergent Support Request - MongoDB Migration Blocker

**Application**: Telegram Shipping Bot (orderbot-upgrade)  
**Issue**: Deployment fails at MONGODB_MIGRATE step  
**Priority**: CRITICAL - Blocking production deployment  
**Date**: November 25, 2025

## Problem Summary

Deployment consistently fails at `MONGODB_MIGRATE` step with authentication error, despite extensive configuration attempts to skip this step or use external MongoDB.

## Error Message

```
[MONGODB_MIGRATE] Nov 25 15:56:30 starting mongodb migration...
[MONGODB_MIGRATE] Nov 25 15:56:30 testing MongoDB connection...
[MONGODB_MIGRATE] Nov 25 15:56:30 Emergent managed Atlas connection failed, attempting user creation: 
failed to ping MongoDB: connection() error occurred during connection handshake: 
auth error: sasl conversation error: unable to authenticate using mechanism "SCRAM-SHA-1": 
(AuthenticationFailed) Authentication failed.
[MONGODB_MIGRATE] Nov 25 15:56:30 failed to list source databases: failed to execute command: 
command terminated with exit code 1
```

## Application Configuration

**Database Setup:**
- Using **external MongoDB Atlas cluster** (NOT Emergent managed)
- Connection string: `mongodb+srv://bbeardy3_db_user:***@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot`
- Database works perfectly in local/preview environment
- Application connects successfully to external MongoDB

**Build Status:**
- ✅ Frontend build: SUCCESS
- ✅ Backend build: SUCCESS  
- ✅ Dependencies: SUCCESS
- ❌ MONGODB_MIGRATE: FAILED

## Configuration Attempts Made

We have created comprehensive configuration files to skip MongoDB migration:

### 1. `.cfg` Format Files
- `/app/config.cfg`
- `/app/.emergent.cfg`
- `/app/.deployer.cfg`

**Content:**
```
SKIP_MIGRATION=true
USE_EXTERNAL_DB=true
MONGODB_MIGRATE_SKIP=true
EMERGENT_SKIP_MIGRATION=true
MONGO_HOST=external
MONGO_DATABASE=telegram_shipping_bot
MIGRATION_DIR=./skip
```

### 2. YAML Configuration Files
- `/app/.deployment.yml`
- `/app/.platform/config.yml`

**Content:**
```yaml
mongodb:
  enabled: false
  skip_migration: true
  use_external: true
  connection_string_env: MONGO_URL
```

### 3. JSON Configuration Files
- `/app/.emergent.config.json`
- `/app/emergent.json`
- `/app/app.json`

**Content:**
```json
{
  "mongodb": {
    "enabled": false,
    "skip_migration": true,
    "use_external": true
  }
}
```

### 4. Environment Variables
Added to `.env` files:
```
MONGODB_MIGRATE_SKIP=true
EMERGENT_SKIP_MIGRATION=true
SKIP_MIGRATION=true
USE_EXTERNAL_DB=true
```

### 5. Additional Files
- `Procfile` - Custom start command
- `runtime.txt` - Python 3.11
- `/app/skip/` - Empty migration directory
- `/app/skip_migration.sh` - Migration skip script

## Platform Behavior Observed

1. **All configuration files are ignored** - Platform doesn't recognize any skip flags
2. **Hardcoded migration step** - MONGODB_MIGRATE appears mandatory in deployment pipeline
3. **Platform tries own credentials first** - Error shows "Emergent managed Atlas connection failed"
4. **No bypass mechanism found** - No documented way to skip this step

## What We Need

### Option 1: Manual Bypass (Preferred)
Please manually bypass or disable the MONGODB_MIGRATE step for our application deployment.

**Reason**: We use external MongoDB Atlas cluster that doesn't require platform migration.

### Option 2: Configuration Guidance
If there IS a way to skip MongoDB migration through configuration:
- Please provide official documentation
- Specify exact file format and location required
- Clarify which environment variables the platform recognizes

### Option 3: Alternative Approach
If external MongoDB isn't supported during deployment:
- Explain platform limitations
- Suggest alternative deployment approaches
- Provide workaround for external database usage

## Additional Information

**Application Details:**
- Stack: FastAPI + React + MongoDB Atlas
- Bot: Telegram shipping bot with ShipStation integration
- Environment: Production deployment
- Current State: Working perfectly in preview environment

**What Works:**
- ✅ Application code
- ✅ Local MongoDB connection
- ✅ Preview environment
- ✅ All dependencies
- ✅ Frontend and backend builds

**What Doesn't Work:**
- ❌ Production deployment (blocked by MONGODB_MIGRATE)

## Configuration Files Available

All configuration files are present in the repository:
- Configuration: `/app/config.cfg`, `/app/.emergent.cfg`
- Deployment: `/app/.deployment.yml`, `/app/emergent.json`
- Platform: `/app/.platform/config.yml`
- Documentation: `/app/DEPLOYMENT_README.md`, `/app/DEPLOYMENT_FIX_V2.md`

## Request

Please review our configuration and either:
1. Manually bypass MONGODB_MIGRATE step for this deployment, OR
2. Provide documentation on correct configuration format, OR
3. Confirm if external MongoDB is supported and suggest alternative approach

## Contact Information

**Application URL**: https://orderbot-upgrade.emergent.host  
**Repository**: Available in Emergent workspace  
**Logs**: Deployment logs show consistent MONGODB_MIGRATE failure

## Urgency

**CRITICAL** - This is blocking our production deployment. Application is ready to deploy but cannot proceed due to this platform limitation.

We have spent significant effort trying different configuration approaches based on best practices, but the platform continues to ignore all skip flags.

Please assist at your earliest convenience.

---

**Thank you for your help!**
