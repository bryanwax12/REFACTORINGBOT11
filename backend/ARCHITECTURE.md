# Shipping Bot Architecture

## 📁 Project Structure

```
/app/backend/
├── server.py                    # Main application entry point (6539 lines)
├── session_manager.py           # Custom session management with MongoDB
├── models/                      # Pydantic models
├── services/                    # Business logic layer
│   ├── payment_service.py       # Payment & balance operations
│   ├── template_service.py      # Template CRUD operations
│   ├── shipping_service_new.py  # Shipping operations (new)
│   ├── shipping_service.py      # Shipping wrapper (legacy)
│   ├── api_services.py          # External API integrations
│   └── shipstation_cache.py     # ShipStation rate caching
├── handlers/                    # Telegram bot handlers
│   ├── common_handlers.py       # Start, help, FAQ commands
│   ├── payment_handlers.py      # Payment webhook handlers
│   ├── webhook_handlers.py      # Generic webhooks
│   ├── template_handlers.py     # Template management
│   └── order_flow/              # Order creation flow (modular)
│       ├── from_address.py      # Sender address collection (7 steps)
│       ├── to_address.py        # Recipient address collection (7 steps)
│       ├── parcel.py            # Parcel info collection (3 steps)
│       ├── skip_handlers.py     # Skip field handlers
│       ├── confirmation.py      # Data confirmation & editing
│       └── payment.py           # Payment method selection
├── routers/                     # FastAPI routers
│   └── admin_router.py          # Admin API endpoints
├── utils/                       # Utility modules
│   ├── ui_utils.py              # UI components (1304 lines)
│   ├── decorators.py            # Common decorators
│   └── performance.py           # Performance monitoring
└── tests/                       # Test files

Total: ~7993 lines of code
```

## 🏗️ Architecture Layers

### 1. Service Layer (`/services/`)

**Purpose:** Encapsulate business logic and external integrations

#### Payment Service (`payment_service.py`)
- Balance operations (add, deduct, check)
- Payment validation
- Transaction processing
- Invoice creation (Oxapay integration)

**Key Functions:**
- `get_user_balance()` - Get current balance
- `add_balance()` - Add funds with validation
- `deduct_balance()` - Deduct with insufficient balance check
- `process_balance_payment()` - Atomic payment transaction
- `create_payment_invoice()` - Generate crypto payment link
- `validate_topup_amount()` - Min/max validation
- `validate_payment_amount()` - Balance check before payment

#### Template Service (`template_service.py`)
- Template CRUD operations
- Template usage and loading
- Authorization checks
- Data validation

**Key Functions:**
- `get_user_templates()` - Retrieve user's templates
- `create_template()` - Save order data as template
- `update_template_name()` - Rename template
- `delete_template()` - Delete with auth check
- `load_template_to_context()` - Load template into conversation
- `validate_template_data()` - Validate before saving
- `format_template_for_display()` - Display formatting

#### Shipping Service (`shipping_service_new.py`)
- Shipping rate display
- Address validation
- Parcel validation
- ShipStation API formatting

**Key Functions:**
- `display_shipping_rates()` - Show rates to user
- `validate_shipping_address()` - Address validation
- `validate_parcel_data()` - Parcel info validation
- `format_order_for_shipstation()` - API request formatting

**Note:** Large functions `fetch_shipping_rates` and `create_and_send_label` remain in `server.py` due to complexity. Future refactoring target.

### 2. Handler Layer (`/handlers/`)

**Purpose:** Process Telegram updates and coordinate business logic

#### Common Handlers (`common_handlers.py`)
- `/start` command
- `/help` command
- FAQ handling
- Main menu navigation

#### Order Flow Handlers (`/order_flow/`)

Modular structure for 17-step order creation process:

**From Address** (`from_address.py`):
1. FROM_NAME - Sender name
2. FROM_ADDRESS - Sender street
3. FROM_ADDRESS2 - Sender apt/suite (optional, skippable)
4. FROM_CITY - Sender city
5. FROM_STATE - Sender state
6. FROM_ZIP - Sender ZIP code
7. FROM_PHONE - Sender phone (optional, skippable, auto-generates random if skipped)

**To Address** (`to_address.py`):
8. TO_NAME - Recipient name
9. TO_ADDRESS - Recipient street
10. TO_ADDRESS2 - Recipient apt/suite (optional, skippable)
11. TO_CITY - Recipient city
12. TO_STATE - Recipient state
13. TO_ZIP - Recipient ZIP code
14. TO_PHONE - Recipient phone (optional, skippable, auto-generates random if skipped)

**Parcel** (`parcel.py`):
15. PARCEL_WEIGHT - Weight in lbs
16. PARCEL_LENGTH - Length in inches
17. PARCEL_WIDTH - Width in inches
18. PARCEL_HEIGHT - Height in inches

**Skip Handlers** (`skip_handlers.py`):
- Handles all "Skip" button callbacks
- Auto-generates default values for optional fields
- Centralized skip logic

**Confirmation** (`confirmation.py`):
- Data review and confirmation
- Edit menu navigation
- Template saving prompt

**Payment** (`payment.py`):
- Payment method selection
- Balance payment
- Crypto payment
- Top-up redirect

### 3. UI Layer (`/utils/ui_utils.py`)

**Purpose:** Centralize all UI components (messages, keyboards)

#### UI Classes (5 total, 40+ methods):

**ShippingRatesUI** (11 methods):
- Rate display formatting
- Progress messages
- Error messages
- Keyboard builders

**LabelCreationUI** (4 methods):
- Label creation messages
- Success/error notifications
- Payment confirmations

**DataConfirmationUI** (7 methods):
- Confirmation screen formatting
- Address/parcel section formatting
- Edit menu keyboards

**PaymentFlowUI** (11 methods):
- Balance screen
- Payment method selection
- Error messages
- Crypto selection keyboard

**TemplateManagementUI** (11 methods):
- Template list formatting
- Template item display
- CRUD operation messages
- Action keyboards

**Benefits:**
- Single source of truth for all UI text
- Easy localization (i18n ready)
- Consistent messaging
- Reusable components

### 4. API Router Layer (`/routers/`)

**Purpose:** REST API endpoints for admin operations

#### Admin Router (`admin_router.py`)
- User management
- Balance operations (add/deduct)
- Order management
- System health monitoring

### 5. Model Layer (`/models/`)

**Purpose:** Data validation and typing (Pydantic models)

**Models:**
- `User` - User account data
- `Order` - Order information
- `Template` - Saved address templates
- `Payment` - Payment transactions
- `ShippingRateRequest` - Rate calculation requests

## 🔄 Data Flow

### Order Creation Flow

```
User → Telegram Update
  ↓
Handler (order_flow/*.py)
  ↓
Service (validation, business logic)
  ↓
Database (MongoDB)
  ↓
UI Component (ui_utils.py)
  ↓
Telegram Response
```

### Payment Flow

```
User selects carrier
  ↓
Payment method selection (payment.py)
  ↓
Payment Service validation
  ↓
If balance: process_balance_payment()
  ├─ Create label
  ├─ Deduct balance
  └─ Update order status
  ↓
Success notification (PaymentFlowUI)
```

### Template Usage Flow

```
User selects template
  ↓
Template Service: load_template_to_context()
  ↓
Context filled with template data
  ↓
Continue to parcel weight step
  ↓
Confirmation → Rates → Payment
```

## 🔐 Security & Safety

### Session Management
- Custom `SessionManager` with MongoDB persistence
- State recovery after bot restart
- Prevents data loss

### Transaction Safety
- Atomic balance operations
- Rollback on label creation failure
- Balance checked before deduction

### Authorization
- Template operations check ownership
- Admin endpoints require API key
- User blocking mechanism

### Input Validation
- Address validation (all required fields)
- Parcel weight/dimensions validation
- Template name length limits
- Amount validation (min/max)

## 🎯 Design Patterns

### 1. Dependency Injection
Services receive dependencies as parameters:
```python
await payment_service.add_balance(
    telegram_id=telegram_id,
    amount=amount,
    db=db,  # Injected
    find_user_func=find_user_by_telegram_id  # Injected
)
```

**Benefits:** Easy testing with mocks, loose coupling

### 2. Service Layer Pattern
Business logic separated from handlers:
- Handlers coordinate
- Services process
- Clear separation of concerns

### 3. UI Component Pattern
All UI centralized in classes:
- Reusable methods
- Consistent styling
- Easy maintenance

### 4. Repository Pattern (Database)
Database operations wrapped in functions:
- `find_user_by_telegram_id()`
- `insert_order()`
- `update_template()`

**Benefits:** Easy to swap database, centralized queries

## 📊 Performance Optimizations

### 1. Rate Caching (`shipstation_cache.py`)
- Caches shipping rates for identical requests
- Reduces ShipStation API calls
- 5-minute TTL

### 2. Database Profiling (`utils/performance.py`)
- All DB queries wrapped with `@profile_db_query`
- Automatic performance logging
- Slow query detection

### 3. Async Operations
- Non-blocking Telegram calls
- Concurrent rate fetching
- Background tasks for notifications

### 4. Session Persistence
- MongoDB-backed sessions
- Survives bot restarts
- No data loss on crashes

## 🧪 Testing Strategy

### Unit Tests (Planned - P2)
- Service functions (pure logic)
- Validation functions
- UI formatting functions

### Integration Tests
- Order flow (backend_testing_agent)
- Payment processing
- Template operations

### Manual Testing
- Full order creation
- Edge cases (insufficient balance, invalid addresses)
- Skip functionality

## 🚀 Deployment

### Environment Variables
```
BOT_TOKEN=<telegram_bot_token>
MONGO_URL=mongodb://localhost:27017
SHIPSTATION_API_KEY=<key>
SHIPSTATION_API_SECRET=<secret>
OXAPAY_API_KEY=<key>
```

### Services
- **Backend:** Supervised process (hot reload enabled)
- **MongoDB:** Local instance
- **Supervisor:** Process management

### Restart Protocol
```bash
# After .env changes or new dependencies:
sudo supervisorctl restart backend

# For code changes: Auto-reload (hot reload)
```

## 📈 Future Improvements

### P2: Unit Tests
- `pytest` for all service functions
- Mock external dependencies
- 80%+ code coverage

### P3.3: Complete Shipping Service
- Extract `fetch_shipping_rates` (~300 lines)
- Extract `create_and_send_label` (~400 lines)
- Modularize ShipStation API calls

### P3.4: ConversationHandler Reorganization
- Move handler registration to handlers/
- Cleaner server.py
- Better handler discovery

### Additional
- i18n support (multi-language)
- Admin dashboard UI
- Real-time order tracking
- Webhook retry mechanism
- Rate limiting

## 📚 Key Metrics

**Lines of Code:**
- `server.py`: 6,539 lines (main application)
- `services/`: 1,443 lines (business logic)
- `ui_utils.py`: 1,304 lines (UI components)
- `handlers/order_flow/`: ~800 lines (modular handlers)

**Code Organization:**
- 5 service modules
- 21 reusable service functions
- 5 UI component classes
- 40+ UI methods
- 17 order flow steps (modular)

**Test Coverage:**
- Manual testing: ✅
- Automated backend testing: ✅
- Unit tests: 🔜 (planned)

---

**Last Updated:** November 14, 2024
**Architecture Version:** 2.0 (Post-Modularization)
