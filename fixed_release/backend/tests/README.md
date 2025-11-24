# Tests for Telegram Shipping Bot

## 📦 Установка зависимостей для тестов

```bash
pip install pytest pytest-asyncio
```

## 🧪 Запуск тестов

### Все тесты:
```bash
cd /app/backend
pytest tests/ -v
```

### Конкретный модуль:
```bash
pytest tests/test_session_manager.py -v
```

### С покрытием:
```bash
pip install pytest-cov
pytest tests/ --cov=. --cov-report=html
```

## 📋 Существующие тесты

### ✅ test_session_manager.py
**Тестирует:** SessionManager (MongoDB session management)

**Покрытие:**
- `get_or_create_session()` - создание/получение сессий
- `update_session_atomic()` - атомарные обновления
- `clear_session()` - удаление сессий
- `save_completed_label()` - финализация с fallback
- `revert_to_previous_step()` - откат к предыдущему шагу

**Статус:** 8/8 тестов

---

## 🔄 TODO: Тесты для других модулей

### ⏳ test_api_services.py
**Тестирует:** services/api_services.py

**Нужно протестировать:**
- `create_oxapay_invoice()` (с mock API)
- `check_oxapay_payment()` (с mock API)
- `check_shipstation_balance()` (с mock API)
- Error handling

### ⏳ test_performance.py
**Тестирует:** utils/performance.py

**Нужно протестировать:**
- `@profile_db_query` декоратор
- `@profile_api_call` декоратор
- `QueryTimer` context manager
- `get_performance_stats()`

### ⏳ test_cache.py
**Тестирует:** utils/cache.py

**Нужно протестировать:**
- `get_api_mode_cached()` - кэширование с TTL
- SETTINGS_CACHE behavior

### ⏳ test_shipstation_cache.py
**Тестирует:** services/shipstation_cache.py

**Нужно протестировать:**
- Cache hit/miss
- TTL expiration
- `get_performance_stats()`

---

## 🎯 Стратегия тестирования

### Unit тесты (priority)
- ✅ SessionManager
- ⏳ API Services (с mocks)
- ⏳ Performance utils
- ⏳ Cache

### Integration тесты (later)
- ⏳ Order flow (end-to-end)
- ⏳ Payment flow
- ⏳ Template management

### Mocking внешних API
```python
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
@patch('services.api_services.requests.post')
async def test_create_oxapay_invoice_mock(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        'status': 200,
        'data': {'track_id': '123', 'payment_url': 'https://...'}
    }
    
    result = await create_oxapay_invoice(10.0, 'order123')
    assert result['success'] is True
```

---

## 📊 Покрытие (Coverage)

**Цель:** >80% покрытия для критических модулей

**Текущее покрытие:**
- SessionManager: ~90% ✅
- API Services: 0% ⏳
- Performance: 0% ⏳
- Cache: 0% ⏳

---

## 🐛 Debugging тестов

### Запуск одного теста:
```bash
pytest tests/test_session_manager.py::test_update_session_atomic -v
```

### С output:
```bash
pytest tests/ -v -s
```

### С pdb:
```bash
pytest tests/ --pdb
```
