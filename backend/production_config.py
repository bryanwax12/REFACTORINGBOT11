# Production Configuration for High Load (5000+ concurrent users)

# Uvicorn Settings
UVICORN_CONFIG = {
    "host": "0.0.0.0",
    "port": 8001,
    "workers": 4,  # Number of worker processes (CPU cores)
    "loop": "uvloop",  # Use uvloop for better performance
    "limit_concurrency": 5000,  # Maximum concurrent connections
    "limit_max_requests": 10000,  # Restart worker after X requests (prevents memory leaks)
    "timeout_keep_alive": 30,  # Keep-alive timeout
    "backlog": 2048,  # Maximum number of pending connections
}

# MongoDB Connection Pool Settings (already applied in server.py)
MONGODB_POOL_CONFIG = {
    "maxPoolSize": 200,
    "minPoolSize": 10,
    "maxIdleTimeMS": 45000,
    "waitQueueTimeoutMS": 5000,
    "serverSelectionTimeoutMS": 5000
}

# Cache Settings
CACHE_TTL = 60  # seconds
USER_BALANCE_CACHE_SIZE = 5000  # Maximum cached users

# Rate Limiting (for external APIs)
SHIPSTATION_RATE_LIMIT = 40  # requests per second
OXAPAY_RATE_LIMIT = 10  # requests per second

# Performance Tips:
# 1. Use connection pooling (✅ implemented)
# 2. Cache frequently accessed data (✅ implemented)
# 3. Create database indexes (✅ implemented)
# 4. Use concurrent updates for Telegram bot (✅ implemented)
# 5. Monitor CPU and memory usage
# 6. Scale horizontally with multiple instances if needed
