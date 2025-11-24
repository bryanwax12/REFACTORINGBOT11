# Backend Architecture - Modular Structure

## 📁 Directory Structure

```
backend/
├── server.py              # Main application file (legacy, to be migrated)
├── models/                # Pydantic data models
│   ├── __init__.py
│   ├── user.py           # User models
│   ├── order.py          # Order models
│   ├── payment.py        # Payment models
│   └── label.py          # Shipping label models
├── db/                    # Database operations
│   ├── __init__.py
│   ├── connection.py     # MongoDB connection setup
│   ├── users.py          # User database operations
│   ├── orders.py         # Order database operations
│   └── payments.py       # Payment database operations
├── utils/                 # Utility functions
│   ├── __init__.py
│   ├── helpers.py        # General helper functions
│   └── cache.py          # Caching utilities
├── handlers/              # Telegram bot handlers (to be created)
│   └── ...
└── api/                   # FastAPI endpoints (to be created)
    └── ...
```

## 🎯 Benefits of Modular Structure

### 1. **Maintainability**
- Easier to find and fix bugs
- Clear separation of concerns
- Smaller files are easier to understand

### 2. **Scalability**
- Can add new features without touching existing code
- Team members can work on different modules
- Easier to test individual components

### 3. **Reusability**
- Database operations can be reused across handlers
- Models ensure data consistency
- Utilities are available everywhere

### 4. **Performance**
- Optimized database connection pooling
- Efficient caching mechanisms
- Reduced code duplication

## 🔄 Migration Plan

### Phase 1: Foundation (✅ Complete)
- ✅ Create directory structure
- ✅ Set up models module
- ✅ Set up db module
- ✅ Set up utils module

### Phase 2: Handlers (Future)
- Extract Telegram bot handlers from server.py
- Create separate files for each conversation flow
- Implement handler registration system

### Phase 3: API (Future)
- Extract FastAPI endpoints from server.py
- Group related endpoints
- Implement middleware and dependencies

### Phase 4: Integration (Future)
- Update server.py to import from modules
- Test all functionality
- Remove duplicated code from server.py

## 📖 Usage Examples

### Using Models
```python
from models import User, Order

user = User(
    telegram_id=123456789,
    username="john_doe",
    first_name="John",
    balance=50.0,
    created_at="2025-11-10T12:00:00Z"
)
```

### Using Database Operations
```python
from db import get_user, update_user_balance

# Get user
user = await get_user(telegram_id=123456789)

# Update balance
success = await update_user_balance(
    telegram_id=123456789,
    amount=10.0
)
```

### Using Utilities
```python
from utils import generate_random_phone, get_api_mode_cached

# Generate phone
phone = generate_random_phone()  # +15551234567

# Get cached API mode
api_mode = await get_api_mode_cached(db)
```

## 🔧 Configuration

### MongoDB Connection
Configured in `db/connection.py`:
- **maxPoolSize**: 20 (optimized for Preview)
- **minPoolSize**: 2
- **Connection timeout**: 3 seconds

### Caching
Configured in `utils/cache.py`:
- **Cache TTL**: 60 seconds
- **Cached items**: api_mode, maintenance_mode

## 🚀 Next Steps

1. **Migrate handlers**: Move Telegram bot handlers to `handlers/` module
2. **Migrate API endpoints**: Move FastAPI routes to `api/` module
3. **Add tests**: Create unit tests for each module
4. **Documentation**: Add docstrings and type hints
5. **Performance**: Add more caching where needed

## 📝 Notes

- This is a gradual migration approach
- server.py still contains all code (backwards compatible)
- New modules are ready to use but not yet integrated
- No breaking changes to existing functionality
