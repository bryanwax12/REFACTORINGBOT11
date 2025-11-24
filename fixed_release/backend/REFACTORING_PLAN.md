# План рефакторинга server.py

## ✅ Завершено

1. **Модели** → `/app/backend/models/models.py`
   - User, Address, Parcel, ShippingLabel, Payment, Order, Template
   - BroadcastRequest, ShippingRateRequest

2. **Конфигурация** → `/app/backend/config.py`
   - MongoDB connection
   - Environment variables
   - API keys (ShipStation, Oxapay, Telegram)

3. **Структура директорий создана:**
   ```
   /app/backend/
   ├── routes/
   ├── handlers/
   ├── services/
   ├── utils/
   └── models/ ✅
   ```

## 📋 Следующие шаги рефакторинга

### Приоритет 1: Утилиты

**`/app/backend/utils/telegram_helpers.py`**
- `safe_telegram_call()` - универсальная обертка для Telegram API
- `mark_message_as_selected()` - добавление ✅ к сообщению
- `with_typing_indicator` - декоратор typing indicator

**`/app/backend/utils/security.py`**
- `sanitize_string()`
- `sanitize_address()`
- `sanitize_phone()`
- `SecurityLogger` класс

**`/app/backend/utils/rate_limiter.py`**
- `RateLimiter` класс
- `is_button_click_allowed()`

### Приоритет 2: Сервисы

**`/app/backend/services/shipstation_service.py`**
- `get_shipstation_carrier_ids()`
- `validate_address_with_shipstation()`
- `fetch_shipping_rates_from_api()`
- `create_shipstation_label()`
- `check_shipstation_balance()`

**`/app/backend/services/oxapay_service.py`**
- `create_oxapay_invoice()`
- `check_oxapay_payment()`

**`/app/backend/services/ai_service.py`**
- `generate_thank_you_message()`

### Приоритет 3: Обработчики

**`/app/backend/handlers/common_handlers.py`**
- `start_command()`
- `help_command()`
- `faq_command()`
- `button_callback()`

**`/app/backend/handlers/order_handlers.py`**
- `new_order_start()`
- `order_from_name()` ... `order_parcel_height()`
- `show_data_confirmation()`
- `fetch_shipping_rates()`
- `select_carrier()`
- `confirm_carrier_selection()`

**`/app/backend/handlers/template_handlers.py`**
- `my_templates_menu()`
- `show_template()`
- `load_template()`
- `delete_template()`
- `rename_template_start()`

**`/app/backend/handlers/balance_handlers.py`**
- `my_balance_command()`
- `handle_topup_amount_input()`

### Приоритет 4: API Routes

**`/app/backend/routes/telegram.py`**
- `/api/telegram/webhook` - главный webhook
- Telegram Application setup

**`/app/backend/routes/admin.py`**
- `/api/admin/users`
- `/api/admin/balance`
- `/api/admin/broadcast`
- `/api/admin/settings`

**`/app/backend/routes/oxapay.py`**
- `/api/oxapay/webhook` - payment callbacks

## 🎯 Преимущества после рефакторинга

1. **Читаемость**: вместо 8630 строк - файлы по 200-500 строк
2. **Тестируемость**: каждый модуль можно тестировать отдельно
3. **Поддержка**: легче найти и исправить баги
4. **Масштабируемость**: легко добавлять новые features
5. **Переиспользование**: утилиты и сервисы можно использовать везде

## ⚠️ Важно при рефакторинге

- Не ломать существующую функциональность
- Тестировать после каждого переноса модуля
- Обновлять импорты постепенно
- Сохранять обратную совместимость

## 📊 Прогресс

- [x] Модели (100%)
- [x] Конфигурация (100%)
- [ ] Утилиты (0%)
- [ ] Сервисы (0%)
- [ ] Обработчики (0%)
- [ ] Routes (0%)

**Общий прогресс: 15%** (2 из 6 модулей)
