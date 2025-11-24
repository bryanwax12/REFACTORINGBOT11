# Architecture Documentation
# Документация архитектуры Telegram Shipping Bot

## Обзор

Telegram Shipping Bot - это полнофункциональное приложение для управления международными отправками через Telegram, построенное на современной модульной архитектуре.

### Технологический стек

- **Backend:** FastAPI (Python 3.11+)
- **Database:** MongoDB (Motor - async driver)
- **Telegram:** python-telegram-bot
- **Payment:** Oxapay (Crypto payments)
- **Shipping:** ShipStation API

---

## Архитектурные паттерны

### 1. Repository Pattern
Слой доступа к данным изолирован в repositories для обеспечения чистой архитектуры.

```
repositories/
├── __init__.py              # RepositoryManager, фабрика
├── user_repository.py       # Операции с пользователями
├── order_repository.py      # Операции с заказами
├── payment_repository.py    # Операции с платежами
├── template_repository.py   # Операции с шаблонами
└── session_repository.py    # Операции с сессиями
```

**Преимущества:**
- Единая точка доступа к данным
- Легко тестировать (mock repositories)
- Переход на другую БД требует изменений только в repositories

### 2. Service Layer Pattern
Бизнес-логика изолирована в services.

```
services/
├── service_factory.py       # ServiceFactory - IoC контейнер
├── order_service.py         # Логика заказов
├── user_service.py          # Логика пользователей
├── payment_service.py       # Логика платежей
├── session_service.py       # Логика сессий
└── template_service.py      # Логика шаблонов
```

**Преимущества:**
- Разделение concerns
- Переиспользуемая бизнес-логика
- Легко unit-тестировать

### 3. Dependency Injection
ServiceFactory реализует IoC (Inversion of Control) контейнер.

```python
# Инициализация
init_service_factory(db)

# Использование
service = get_service_factory().get_user_service()
user = await service.find_user(telegram_id)
```

### 4. Decorator Pattern
Используется для кросс-cutting concerns:

- `@with_user_session` - автоматическая загрузка сессии
- `@inject_services` - DI для handlers
- `@safe_handler` - обработка ошибок
- `@profile_db_query` - профилирование запросов к БД

---

## Структура проекта

```
backend/
├── handlers/                # Telegram bot handlers
│   ├── common_handlers.py   # Общие handlers
│   ├── payment_handlers.py  # Платежные handlers
│   ├── template_handlers.py # Handlers шаблонов
│   ├── order_handlers.py    # Handlers заказов
│   └── order_flow/          # Handlers для flow создания заказа
│       ├── entry_points.py  # Точки входа в flow
│       ├── confirmation.py  # Подтверждение данных
│       ├── payment.py       # Обработка платежей
│       ├── rates.py         # Получение тарифов
│       ├── skip_handlers.py # Пропуск шагов
│       └── cancellation.py  # Отмена заказа
│
├── routers/                 # FastAPI routers (REST API)
│   ├── orders.py            # /api/orders
│   ├── users.py             # /api/users
│   ├── shipping.py          # /api/shipping
│   ├── settings.py          # /api/settings
│   ├── webhooks.py          # /api/webhooks
│   ├── admin_router.py      # /api/admin
│   └── monitoring_router.py # /api/health, /api/metrics
│
├── repositories/            # Data access layer
│   └── [см. выше]
│
├── services/                # Business logic layer
│   └── [см. выше]
│
├── middleware/              # FastAPI middleware
│   ├── __init__.py
│   ├── error_handler.py     # Централизованная обработка ошибок
│   └── logging_middleware.py# Логирование запросов
│
├── utils/                   # Утилиты
│   ├── api_config.py        # Управление API ключами
│   ├── db_operations.py     # Профилируемые DB операции
│   ├── db_wrappers.py       # DB декораторы
│   ├── handler_decorators.py# Декораторы для handlers
│   ├── session_utils.py     # Утилиты для сессий
│   ├── settings_cache.py    # Кеш настроек
│   ├── telegram_utils.py    # Telegram helpers
│   └── ui_utils.py          # UI компоненты
│
├── tests/                   # Тесты
│   ├── integration/         # Интеграционные тесты
│   └── unit/                # Unit тесты
│
├── docs/                    # Документация
│   ├── API_DOCUMENTATION.md # API docs
│   └── ARCHITECTURE.md      # Этот файл
│
└── server.py                # Главный файл приложения
```

---

## Ключевые компоненты

### Server.py (Точка входа)
**Роль:** Инициализация приложения

**Обязанности:**
- Создание FastAPI app
- Регистрация routers
- Регистрация middleware
- Инициализация MongoDB
- Настройка Telegram bot
- Lifecycle events (startup/shutdown)

**НЕ содержит:**
- ❌ Бизнес-логику
- ❌ Handlers
- ❌ DB операции
- ❌ API endpoints (они в routers/)

### Repositories
**Роль:** Абстракция доступа к данным

**Пример:**
```python
class OrderRepository:
    def __init__(self, db):
        self.collection = db.orders
    
    async def find_by_id(self, order_id: str):
        return await self.collection.find_one(
            {"order_id": order_id}, 
            {"_id": 0}
        )
    
    async def create(self, order_dict: dict):
        return await self.collection.insert_one(order_dict)
```

### Services
**Роль:** Бизнес-логика

**Пример:**
```python
class OrderService:
    def __init__(self, order_repo, user_repo):
        self.order_repo = order_repo
        self.user_repo = user_repo
    
    async def create_order(self, telegram_id, order_data):
        # Validate user
        user = await self.user_repo.find_by_telegram_id(telegram_id)
        if not user:
            raise ValueError("User not found")
        
        # Check balance
        if user['balance'] < order_data['amount']:
            raise ValueError("Insufficient balance")
        
        # Create order
        order_id = generate_order_id(telegram_id)
        order = {
            "order_id": order_id,
            "user_id": user['id'],
            **order_data
        }
        
        await self.order_repo.create(order)
        return order_id
```

### Handlers
**Роль:** Обработка Telegram updates

**Пример:**
```python
@with_user_session
@inject_services(['user', 'order'])
async def handle_new_order(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    user_service,
    order_service
):
    # Handler logic using injected services
    telegram_id = update.effective_user.id
    
    # Business logic через service
    order_id = await order_service.create_order(
        telegram_id, 
        context.user_data
    )
    
    await update.message.reply_text(f"Заказ {order_id} создан!")
```

### Routers (API Endpoints)
**Роль:** REST API endpoints

**Пример:**
```python
@router.get("/orders/{telegram_id}")
async def get_user_orders(telegram_id: int):
    repos = get_repositories()
    orders = await repos.orders.get_user_orders(telegram_id)
    return {"orders": orders}
```

---

## Data Flow

### 1. Telegram Bot Flow
```
Telegram Update 
  → Handler (handlers/)
    → Service (services/)
      → Repository (repositories/)
        → MongoDB
```

### 2. REST API Flow
```
HTTP Request
  → Router (routers/)
    → Service (services/)
      → Repository (repositories/)
        → MongoDB
          ← Response
```

### 3. Webhook Flow
```
External Webhook (Oxapay)
  → Webhook Router (routers/webhooks.py)
    → Service (services/)
      → Repository (repositories/)
        → MongoDB
      → Notification to user (Telegram)
```

---

## Session Management

### User Session
Хранится в `context.user_data` и БД.

**Содержит:**
- Текущий шаг в flow
- Введенные данные (адреса, вес посылки и т.д.)
- Временные данные (выбранный тариф, методы оплаты)

**Синхронизация:**
```python
@with_user_session
async def handler(update, context):
    # Сессия автоматически загружается из БД
    # и доступна в context.user_data
    
    context.user_data['new_field'] = 'value'
    
    # Сессия автоматически сохраняется после handler
```

---

## Error Handling

### 1. Handler Level
```python
@safe_handler(fallback_state=ConversationHandler.END)
async def handler(update, context):
    # Ошибки перехватываются декоратором
    # Пользователь видит дружественное сообщение
    ...
```

### 2. Service Level
```python
class OrderService:
    async def create_order(self, ...):
        try:
            ...
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
```

### 3. Global Level (Middleware)
```python
@app.middleware("http")
async def error_handler_middleware(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
```

---

## Testing Strategy

### 1. Unit Tests
Тестируют отдельные компоненты в изоляции.

```python
async def test_order_service_create():
    # Mock repositories
    order_repo = Mock()
    user_repo = Mock()
    
    # Create service
    service = OrderService(order_repo, user_repo)
    
    # Test
    result = await service.create_order(123, order_data)
    assert result is not None
```

### 2. Integration Tests
Тестируют взаимодействие компонентов.

```python
async def test_order_flow_e2e(test_db):
    # Real DB, real services
    init_service_factory(test_db)
    
    # Simulate full flow
    result = await create_order_handler(...)
    
    # Verify in DB
    order = await test_db.orders.find_one(...)
    assert order['status'] == 'completed'
```

### 3. Test Isolation
Каждый тест получает чистую БД и свежие services:

```python
@pytest.fixture
async def test_db():
    # Reset factories
    reset_service_factory()
    reset_repositories()
    
    # Create new client
    client = AsyncIOMotorClient(...)
    db = client[test_db_name]
    
    # Clean data
    await cleanup_test_data(db)
    
    yield db
    
    # Cleanup after test
    client.close()
```

---

## Performance Optimizations

### 1. Connection Pooling
Motor автоматически управляет connection pool.

### 2. Query Profiling
Все DB операции профилируются:

```python
@profile_db_query("find_user")
async def find_user(telegram_id):
    # Автоматически логируется время выполнения
    ...
```

### 3. Caching
- Settings кешируются в памяти
- Button debouncing предотвращает дублирующие запросы

### 4. Async Everywhere
- Все IO операции async
- Non-blocking handlers

---

## Security

### 1. Input Validation
Все входные данные валидируются через Pydantic models.

### 2. Admin Protection
Admin endpoints требуют API key:

```python
@router.get("/admin/stats")
async def get_stats(api_key: str = Depends(verify_admin_key)):
    ...
```

### 3. Rate Limiting
Защита от DDoS через middleware.

### 4. SQL Injection Prevention
MongoDB с typed queries - защита из коробки.

---

## Monitoring & Logging

### 1. Structured Logging
```python
logger.info(
    "Order created",
    extra={
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount
    }
)
```

### 2. Performance Metrics
- DB query times
- API response times
- Error rates

### 3. Health Checks
```
GET /api/health
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

---

## Deployment

### Development
```bash
# Start services
supervisorctl start backend
supervisorctl start frontend

# Check status
supervisorctl status
```

### Production
- Containerized with Docker
- Kubernetes orchestration
- Auto-scaling based on load
- Zero-downtime deployments

---

## Future Improvements

### Planned
- [ ] Redis caching layer
- [ ] GraphQL API alongside REST
- [ ] Real-time notifications via WebSockets
- [ ] Enhanced analytics dashboard

### Under Consideration
- [ ] Multi-language support
- [ ] White-label solution
- [ ] Mobile app (React Native)

---

## Contributing

См. [CONTRIBUTING.md](CONTRIBUTING.md) для guidelines.

---

## License

Proprietary - All Rights Reserved
