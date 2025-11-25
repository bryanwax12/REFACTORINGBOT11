# 🚀 Deployment Instructions for MongoDB Atlas

## ✅ MongoDB Atlas Setup Complete!

**Connection String:**
```
mongodb+srv://<username>:<password>@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority
```
*(Actual credentials configured via environment variables)*

**Data Imported:**
- ✅ 5 users
- ✅ 3 orders
- ✅ 18 payments
- ✅ 2 settings

---

## 📋 Next Steps for Deployment on Emergent:

### **1. Update Environment Variables for Deployment:**

When you deploy on Emergent platform, you need to set these environment variables:

```bash
MONGO_URL=mongodb+srv://bbeardy3_db_user:ccW9UMMYvz1sSpuJ@cluster0.zmmat7g.mongodb.net/telegram_shipping_bot?retryWrites=true&w=majority
```

**How to set in Emergent:**
1. Go to your deployment settings
2. Add/Update environment variable `MONGO_URL` with the value above
3. Keep all other environment variables as they are
4. Deploy the application

### **2. After Deployment:**

Once deployed, you will get a permanent URL like:
```
https://your-app.emergentagent.com
```

**Update these services with new URL:**

1. **Telegram Bot Webhook:**
   - Set webhook to: `https://your-app.emergentagent.com/api/telegram/webhook`

2. **Oxapay Webhook:**
   - Update in Oxapay dashboard to: `https://your-app.emergentagent.com/api/oxapay/webhook`

---

## 🔄 Current Preview vs Deployed:

| Feature | Preview (Current) | Deployed (Production) |
|---------|------------------|---------------------|
| URL | Changes on fork | Permanent |
| MongoDB | Local (localhost) | Atlas Cloud |
| Uptime | Can sleep | 24/7 |
| Data | Local | Cloud backup |

---

## ⚠️ Important Notes:

1. **Preview will still work** with local MongoDB for testing
2. **Deployed version** will use MongoDB Atlas
3. **Don't delete** MongoDB Atlas cluster - your production data is there
4. **Backup**: Atlas provides automatic backups

---

## 🎯 Ready to Deploy!

Your MongoDB Atlas is configured and data is migrated. 
You can now deploy your application on Emergent platform.
