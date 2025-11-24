# Прогресс рефакторинга server.py

## 🎯 Цель: Уменьшить server.py с 8808 до <2000 строк

---

## ✅ Завершено (11% - 1000 строк)

### 1. Models выделены
- **Файл:** `/app/backend/models/models.py`
- **Строк:** ~150
- **Модели:** User, Order, Address, Parcel, Template, Payment, ShippingLabel
- **Статус:** ✅ Используется

### 2. Session Manager выделен
- **Файл:** `/app/backend/session_manager.py`
- **Строк:** ~309
- **Функции:** SessionManager с TTL, атомарными операциями, транзакциями
- **Статус:** ✅ Используется активно

### 3. Performance Monitoring
- **Файл:** `/app/backend/utils/performance.py`
- **Строк:** ~200
- **Функции:** Профилирование DB/API, QueryTimer, статистика
- **Статус:** ✅ Интегрировано (32 вызова)

### 4. Cache Utils
- **Файл:** `/app/backend/utils/cache.py`
- **Строк:** ~40
- **Функции:** SETTINGS_CACHE, get_api_mode_cached
- **Статус:** ✅ Используется

### 5. API Services
- **Файл:** `/app/backend/services/api_services.py`
- **Строк:** ~260
- **Функции:** 
  * create_oxapay_invoice
  * check_oxapay_payment
  * check_shipstation_balance
  * get_shipstation_carrier_ids
  * validate_address_with_shipstation
- **Статус:** ✅ Модуль создан, импорты добавлены

### 6. ShipStation Cache
- **Файл:** `/app/backend/services/shipstation_cache.py`
- **Строк:** ~180
- **Функции:** Кэширование тарифов (60 мин TTL)
- **Статус:** ✅ Используется

**ИТОГО выделено:** ~1140 строк (13%)

---

## ⏳ В процессе

### Удаление дубликатов из server.py
- **Проблема:** Функции из api_services.py всё ещё дублируются в server.py
- **Решение:** Постепенно заменять прямые вызовы на импорты
- **Строк к удалению:** ~400-500

---

## 📋 TODO (Приоритеты)

### 🔴 Приоритет 1: Order Handlers (~1500 строк, 17%)

**Файл:** `/app/backend/handlers/order_handlers.py`

**Функции для переноса (17 handlers):**
```python
# Entry point
new_order_start()

# FROM address flow (6 steps)
order_from_name()
order_from_address()
order_from_address2()
order_from_city()
order_from_state()
order_from_zip()
order_from_phone()

# TO address flow (6 steps)
order_to_name()
order_to_address()
order_to_address2()
order_to_city()
order_to_state()
order_to_zip()
order_to_phone()

# Parcel details (4 steps)
order_parcel_weight()
order_parcel_length()
order_parcel_width()
order_parcel_height()

# Confirmation & rates
show_data_confirmation()
fetch_shipping_rates()
display_shipping_rates()
select_carrier()
```

**Зависимости:**
- session_manager (уже выделен ✅)
- safe_telegram_call
- sanitize_* функции
- ConversationHandler states (FROM_NAME, TO_NAME, etc.)

**Сложность:** 🔴 Высокая
- Много взаимосвязей
- Shared state (context.user_data)
- ConversationHandler configuration

**План действий:**
1. Создать handlers/order_handlers.py
2. Перенести helper функции (safe_telegram_call, sanitize_*)
3. Перенести handlers по группам (FROM → TO → PARCEL → CONFIRM)
4. Обновить imports в server.py
5. Тестировать после каждой группы
6. Удалить дубликаты

---

### 🟡 Приоритет 2: Payment Handlers (~300 строк, 3%)

**Файл:** `/app/backend/handlers/payment_handlers.py`

**Функции для переноса:**
```python
my_balance_command()
handle_topup_amount_input()
confirm_carrier_selection()  # Создание платежа
process_payment_callback()
```

**Зависимости:**
- services/api_services (create_oxapay_invoice) ✅
- session_manager ✅

**Сложность:** 🟡 Средняя

---

### 🟢 Приоритет 3: Template Handlers (~400 строк, 5%)

**Файл:** `/app/backend/handlers/template_handlers.py`

**Функции для переноса:**
```python
my_templates_menu()
show_template()
load_template()
delete_template()
rename_template_start()
rename_template_save()
```

**Зависимости:** Минимальные

**Сложность:** 🟢 Низкая

---

### 🟢 Приоритет 4: Admin Handlers (~200 строк, 2%)

**Файл:** `/app/backend/handlers/admin_handlers.py`

**Функции для переноса:**
```python
admin_panel()
get_user_info()
update_user_balance()
broadcast_message()
```

**Сложность:** 🟢 Низкая

---

### 🟢 Приоритет 5: Common Handlers (~200 строк, 2%)

**Файл:** `/app/backend/handlers/common_handlers.py`

**Функции для переноса:**
```python
start_command()
help_command()
faq_command()
button_callback()
cancel_order()
return_to_order()
```

**Сложность:** 🟢 Низкая

---

### 🔵 Приоритет 6: Utils Cleanup (~500 строк, 6%)

**Файлы:**
- `utils/telegram_helpers.py` - safe_telegram_call, mark_message_as_selected
- `utils/security.py` - sanitize_*, verify_admin_key
- `utils/validators.py` - validate_phone, validate_zip, etc.

**Сложность:** 🔵 Очень низкая

---

## 📊 Roadmap

| Этап | Модуль | Строк | Сложность | Статус |
|------|--------|-------|-----------|--------|
| 1 | Models | 150 | 🟢 | ✅ |
| 2 | SessionManager | 309 | 🟡 | ✅ |
| 3 | Performance | 200 | 🟢 | ✅ |
| 4 | Cache | 40 | 🟢 | ✅ |
| 5 | API Services | 260 | 🟡 | ✅ |
| 6 | ShipStation Cache | 180 | 🟢 | ✅ |
| 7 | **Order Handlers** | 1500 | 🔴 | ⏳ TODO |
| 8 | Payment Handlers | 300 | 🟡 | ⏳ TODO |
| 9 | Template Handlers | 400 | 🟢 | ⏳ TODO |
| 10 | Admin Handlers | 200 | 🟢 | ⏳ TODO |
| 11 | Common Handlers | 200 | 🟢 | ⏳ TODO |
| 12 | Utils Cleanup | 500 | 🔵 | ⏳ TODO |

**Выделено:** 1140 / 8808 = **13%**  
**Осталось:** 7668 строк = **87%**

**Цель:** 2000 строк в server.py  
**Нужно вынести:** 6808 строк

---

## 🎯 Стратегия

### Когда делать рефакторинг:
1. ✅ При добавлении новых features
2. ✅ При исправлении багов в конкретном модуле
3. ✅ Постепенно, по 200-300 строк за раз
4. ❌ НЕ рефакторить всё сразу (риск поломки)

### Правила:
- ✅ Всегда тестировать после изменений
- ✅ Сохранять обратную совместимость
- ✅ Не ломать работающий код
- ✅ Добавлять тесты для новых модулей

### Следующий шаг:
**Удалить дубликаты API функций из server.py** (Приоритет 2)
- Функции уже импортированы из services/api_services.py
- Можно безопасно удалить ~400 строк
- Время: ~30 минут
