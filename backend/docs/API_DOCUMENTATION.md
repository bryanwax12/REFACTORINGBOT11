# API Documentation
# Документация API для Telegram Shipping Bot

## Общая информация

### Base URL
- Production: `https://your-domain.com/api`
- Development: `http://localhost:8001/api`

### Аутентификация
Большинство эндпоинтов требуют аутентификацию через Admin API Key или Telegram User ID.

---

## Orders API
Управление заказами

### POST /api/orders
Создание нового заказа

**Request Body:**
```json
{
  "telegram_id": 123456789,
  "address_from": {
    "name": "John Doe",
    "street1": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip": "10001",
    "country": "US",
    "phone": "+1234567890"
  },
  "address_to": {
    "name": "Jane Smith",
    "street1": "456 Oak Ave",
    "city": "Los Angeles",
    "state": "CA",
    "zip": "90001",
    "country": "US",
    "phone": "+0987654321"
  },
  "parcel": {
    "weight": 1.5,
    "length": 10,
    "width": 8,
    "height": 6
  },
  "amount": 25.99
}
```

**Response:** `200 OK`
```json
{
  "order_id": "order_123456789_abc123",
  "status": "created"
}
```

**Error Responses:**
- `404 Not Found` - User not found
- `422 Unprocessable Entity` - Invalid data format

---

### GET /api/orders/{telegram_id}
Получить все заказы пользователя

**Parameters:**
- `telegram_id` (path) - Telegram ID пользователя
- `skip` (query, optional) - Количество заказов для пропуска (default: 0)
- `limit` (query, optional) - Максимальное количество заказов (default: 10, max: 100)

**Response:** `200 OK`
```json
{
  "orders": [
    {
      "order_id": "order_123456789_abc123",
      "telegram_id": 123456789,
      "status": "pending",
      "amount": 25.99,
      "created_at": "2024-11-15T10:30:00Z",
      "address_from": {...},
      "address_to": {...}
    }
  ],
  "total": 1
}
```

---

### GET /api/orders/detail/{order_id}
Получить детали конкретного заказа

**Response:** `200 OK`
```json
{
  "order_id": "order_123456789_abc123",
  "telegram_id": 123456789,
  "status": "completed",
  "payment_status": "paid",
  "shipping_status": "label_created",
  "tracking_number": "1Z999AA10123456789",
  "carrier": "ups",
  "service_name": "UPS Ground",
  "amount": 25.99,
  "created_at": "2024-11-15T10:30:00Z",
  "address_from": {...},
  "address_to": {...},
  "parcel": {...}
}
```

**Error Responses:**
- `404 Not Found` - Order not found

---

### GET /api/orders/export
Экспорт всех заказов в CSV

**Query Parameters:**
- `status` (optional) - Фильтр по статусу заказа

**Response:** `200 OK`
- Content-Type: `text/csv`
- File download with all orders data

---

## Users API
Управление пользователями

### GET /api/users/{telegram_id}
Получить информацию о пользователе

**Response:** `200 OK`
```json
{
  "id": "user_uuid",
  "telegram_id": 123456789,
  "username": "johndoe",
  "balance": 100.50,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
- `404 Not Found` - User not found

---

### GET /api/users
Получить список всех пользователей (Admin only)

**Query Parameters:**
- `skip` (optional) - Offset (default: 0)
- `limit` (optional) - Limit (default: 50, max: 100)

**Response:** `200 OK`
```json
{
  "users": [
    {
      "id": "user_uuid",
      "telegram_id": 123456789,
      "username": "johndoe",
      "balance": 100.50
    }
  ],
  "total": 150
}
```

---

## Shipping API
Управление доставкой

### POST /api/shipping/rates
Получить тарифы доставки

**Request Body:**
```json
{
  "address_from": {
    "street1": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip": "10001",
    "country": "US"
  },
  "address_to": {
    "street1": "456 Oak Ave",
    "city": "Los Angeles",
    "state": "CA",
    "zip": "90001",
    "country": "US"
  },
  "parcel": {
    "weight": 1.5,
    "length": 10,
    "width": 8,
    "height": 6
  }
}
```

**Response:** `200 OK`
```json
{
  "rates": [
    {
      "carrier": "USPS",
      "service": "Priority Mail",
      "rate": "8.50",
      "delivery_days": "2-3",
      "rate_id": "rate_abc123"
    },
    {
      "carrier": "UPS",
      "service": "Ground",
      "rate": "12.75",
      "delivery_days": "3-5",
      "rate_id": "rate_def456"
    }
  ]
}
```

---

### POST /api/shipping/create_label
Создать shipping label

**Request Body:**
```json
{
  "order_id": "order_123456789_abc123",
  "rate_id": "rate_abc123"
}
```

**Response:** `200 OK`
```json
{
  "label_url": "https://example.com/label.pdf",
  "tracking_number": "1Z999AA10123456789",
  "status": "created"
}
```

---

## Settings API
Управление настройками приложения

### GET /api/settings/bot
Получить настройки бота

**Response:** `200 OK`
```json
{
  "maintenance_mode": false,
  "welcome_message": "Добро пожаловать!",
  "min_order_amount": 10.00,
  "max_order_weight": 50.0
}
```

---

### POST /api/settings/bot
Обновить настройки бота (Admin only)

**Request Body:**
```json
{
  "maintenance_mode": true,
  "welcome_message": "Бот на обслуживании"
}
```

**Response:** `200 OK`
```json
{
  "status": "updated"
}
```

---

## Admin API
Административные функции

### GET /api/admin/stats
Получить статистику (Admin only)

**Response:** `200 OK`
```json
{
  "total_users": 1250,
  "total_orders": 3500,
  "total_revenue": 87500.50,
  "orders_today": 45,
  "active_users_today": 120
}
```

---

### POST /api/admin/broadcast
Отправить массовое сообщение (Admin only)

**Request Body:**
```json
{
  "message": "Важное объявление для всех пользователей",
  "target": "all"
}
```

**Response:** `200 OK`
```json
{
  "status": "queued",
  "estimated_recipients": 1250
}
```

---

## Webhooks API
Обработка вебхуков

### POST /api/webhooks/oxapay
Обработка платежных уведомлений от Oxapay

**Headers:**
- `Content-Type: application/json`

**Request Body:**
```json
{
  "trackId": 12345,
  "orderId": "order_123456789_abc123",
  "status": "Paid",
  "amount": 25.99,
  "currency": "USDT"
}
```

**Response:** `200 OK`
```json
{
  "status": "processed"
}
```

---

### POST /api/webhooks/telegram
Обработка обновлений от Telegram

**Note:** Этот эндпоинт используется только при работе в webhook режиме

---

## Monitoring API
Мониторинг и здоровье системы

### GET /api/health
Проверка состояния сервиса

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

---

### GET /api/metrics
Получить метрики производительности (Admin only)

**Response:** `200 OK`
```json
{
  "request_count": 15000,
  "avg_response_time_ms": 45.2,
  "db_queries_count": 8500,
  "error_rate": 0.02
}
```

---

## Error Responses

Все API эндпоинты могут возвращать следующие ошибки:

### 400 Bad Request
```json
{
  "detail": "Invalid request parameters"
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication required"
}
```

### 403 Forbidden
```json
{
  "detail": "Admin access required"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "loc": ["body", "telegram_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limiting

API имеет следующие ограничения:
- **Public endpoints:** 100 запросов в минуту на IP
- **Authenticated endpoints:** 500 запросов в минуту на пользователя
- **Admin endpoints:** 1000 запросов в минуту

При превышении лимита возвращается `429 Too Many Requests`.

---

## Versioning

API использует versioning через URL:
- v1 (current): `/api/v1/...`
- Deprecated версии будут поддерживаться минимум 6 месяцев

---

## SDK и клиенты

Официальные SDK:
- Python: `pip install telegram-shipping-api`
- JavaScript/TypeScript: `npm install @telegram-shipping/api`

---

## Дополнительная информация

- **Interactive API docs:** `/docs` (Swagger UI)
- **Alternative API docs:** `/redoc` (ReDoc)
- **OpenAPI schema:** `/openapi.json`

---

## Поддержка

Для вопросов и поддержки:
- Email: support@example.com
- Telegram: @support_bot
- GitHub Issues: https://github.com/your-repo/issues
