# План улучшения обработки исключений

## Проблема
В кодовой базе ~269 мест используют широкую обработку `except Exception`, что затрудняет отладку и скрывает реальные проблемы.

## Стратегия улучшения

### 1. Категории исключений по контексту

#### A. Telegram API вызовы
**Специфичные исключения:**
- `telegram.error.TimedOut` - таймаут API
- `telegram.error.NetworkError` - сетевые проблемы
- `telegram.error.RetryAfter` - rate limiting
- `telegram.error.BadRequest` - некорректный запрос (например, редактирование старого сообщения)
- `telegram.error.Forbidden` - бот заблокирован пользователем
- `telegram.error.TelegramError` - базовый класс для всех Telegram ошибок

**Пример улучшения:**
```python
# ❌ Было:
except Exception as e:
    logger.error(f"Telegram error: {e}")

# ✅ Стало:
except telegram.error.BadRequest as e:
    # Нормальная ситуация - сообщение слишком старое
    logger.debug(f"Cannot edit message: {e}")
except telegram.error.TelegramError as e:
    logger.error(f"Telegram API error: {e}", exc_info=True)
```

#### B. HTTP API вызовы (ShipStation, Oxapay)
**Специфичные исключения:**
- `httpx.TimeoutException` - таймаут запроса
- `httpx.NetworkError` - сетевые проблемы
- `httpx.HTTPStatusError` - HTTP ошибки (4xx, 5xx)
- `httpx.RequestError` - базовый класс для всех httpx ошибок

**Пример улучшения:**
```python
# ❌ Было:
except Exception as e:
    logger.error(f"API error: {e}")

# ✅ Стало:
except httpx.TimeoutException:
    logger.warning(f"API timeout for {url}")
    raise HTTPException(status_code=504, detail="External API timeout")
except httpx.HTTPStatusError as e:
    logger.error(f"API HTTP error {e.response.status_code}: {e}")
    raise HTTPException(status_code=e.response.status_code, detail=str(e))
except httpx.RequestError as e:
    logger.error(f"API request failed: {e}", exc_info=True)
    raise HTTPException(status_code=503, detail="External API unavailable")
```

#### C. MongoDB операции
**Специфичные исключения:**
- `pymongo.errors.DuplicateKeyError` - дубликат уникального ключа
- `pymongo.errors.ConnectionFailure` - потеря соединения с БД
- `pymongo.errors.OperationFailure` - ошибка выполнения операции
- `pymongo.errors.PyMongoError` - базовый класс для всех MongoDB ошибок

**Пример улучшения:**
```python
# ❌ Было:
except Exception as e:
    logger.error(f"Database error: {e}")

# ✅ Стало:
except pymongo.errors.DuplicateKeyError as e:
    logger.warning(f"Duplicate key: {e}")
    raise HTTPException(status_code=409, detail="Record already exists")
except pymongo.errors.PyMongoError as e:
    logger.error(f"MongoDB error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Database error")
```

#### D. FastAPI endpoints
**Специфичные исключения:**
- `fastapi.HTTPException` - HTTP ошибки
- `pydantic.ValidationError` - ошибки валидации данных

**Пример улучшения:**
```python
# ❌ Было:
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

# ✅ Стало:
except pydantic.ValidationError as e:
    logger.warning(f"Validation error: {e}")
    raise HTTPException(status_code=422, detail=str(e))
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

### 2. Приоритет файлов для исправления

#### P0 - Критичные (обрабатывают платежи и создание заказов):
1. ✅ `handlers/payment_handlers.py` (4 места)
2. ✅ `handlers/order_flow/payment.py` (5 мест)
3. ✅ `handlers/order_flow/rates.py` (6 мест)
4. ✅ `services/payment_service.py`
5. ✅ `services/shipping_service.py`

#### P1 - Важные (API и админка):
6. ✅ `handlers/common_handlers.py` (5 мест)
7. ✅ `services/api_services.py`
8. ✅ `routers/admin/` (все файлы)
9. ✅ `handlers/admin_handlers.py`

#### P2 - Низкий приоритет (мониторинг и отладка):
10. `api/monitoring.py` (8 мест)
11. `api/alerting.py` (3 места)
12. Остальные routers

### 3. Паттерны для игнорирования

**Когда широкий `except Exception` допустим:**

1. **Фоновые задачи** (не должны ломать основной поток):
```python
async def safe_background_task(coro):
    try:
        await coro
    except Exception as e:  # ✅ OK - фоновая задача
        logger.error(f"Background task error: {e}", exc_info=True)
```

2. **Fallback логика** (есть безопасное значение по умолчанию):
```python
try:
    value = await expensive_calculation()
except Exception:  # ✅ OK - есть fallback
    value = DEFAULT_VALUE
```

3. **Cleanup код** (не должен ломать shutdown):
```python
async def shutdown():
    try:
        await close_connections()
    except Exception:  # ✅ OK - cleanup не должен ломаться
        pass
```

## Прогресс

### P0 - Критичные файлы (✅ ЗАВЕРШЕНО)
- [x] `handlers/payment_handlers.py` - 4 места улучшено
  - Добавлены специфичные исключения: `pymongo.errors`, `telegram.error`, `ValueError`
  - Улучшено логирование с `exc_info=True`
- [x] `handlers/order_flow/payment.py` - 5 мест улучшено
  - Разделены `BadRequest` (ожидаемые) и другие `TelegramError`
  - Добавлены `pymongo.errors` для операций с БД
- [x] `handlers/order_flow/rates.py` - 6 мест улучшено  
  - Добавлены `httpx.TimeoutException` и `httpx.HTTPStatusError`
  - Улучшены сообщения пользователю в зависимости от типа ошибки
- [x] `handlers/common_handlers.py` - 5 мест улучшено
  - Разделены `BadRequest` (ожидаемые, лог debug) и `TelegramError` (неожиданные, лог error)
  - Улучшена обработка в `safe_telegram_call` и `safe_background_task`

### P1 - Важные файлы (✅ ЗАВЕРШЕНО)
- [x] `services/api_services.py` - 6 мест улучшено
  - Добавлены: `httpx.TimeoutException`, `httpx.HTTPStatusError`, `httpx.RequestError`
  - Улучшена обработка JSON parsing ошибок (`ValueError`, `KeyError`)
- [x] `services/shipping_service.py` - 3 места улучшено
  - Добавлены специфичные HTTP исключения и `telegram.error`
  - Исправлен bare `except` на конкретные типы
- [x] `services/payment_service.py` - 4 места улучшено
  - Добавлены `pymongo.errors` для всех операций с БД
  - Разделены validation и database errors
- [x] `handlers/admin_handlers.py` - 2 места улучшено
  - Разделены `telegram.error.BadRequest` и другие Telegram ошибки
  - Добавлена обработка `pymongo.errors`
- [x] `routers/admin/stats.py` - 4 места улучшено
- [x] `routers/admin/system.py` - 6 мест улучшено
- [x] `routers/admin/users.py` - 6 мест улучшено
  - Все admin роутеры: добавлены `pymongo.errors`, `httpx.RequestError`, `telegram.error`

### P2 - Низкий приоритет
- [ ] `api/monitoring.py` (8 мест)
- [ ] `api/alerting.py` (3 места)
- [ ] Остальные routers

## Статистика
- **Всего найдено:** ~269 мест с `except Exception`
- **Исправлено:** 20 мест в P0 файлах
- **Осталось:** ~249 мест

