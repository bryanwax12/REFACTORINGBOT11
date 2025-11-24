# Anti-Hang Implementation Plan

## 🎯 Objective
Предотвратить зависания Telegram бота при высокой нагрузке (500+ concurrent users) через комплексные меры.

## 📊 Current State Analysis

### ✅ Already Implemented
1. **MongoDB Connection Pooling**
   - ✅ `serverSelectionTimeoutMS=3000`
   - ✅ `connectTimeoutMS=3000`
   - ✅ `maxPoolSize=20`
   - ✅ TTL indexes for session cleanup

2. **Order ID (Uniqueness)**
   - ✅ Unique `order_id` prevents race conditions
   - ✅ Atomic inserts with MongoDB index

### ❌ Critical Issues Found

1. **Sync HTTP Calls (БЛОКИРУЮТ EVENT LOOP!)**
   - ❌ `requests` used in `/app/backend/services/api_services.py` (6 places)
   - ❌ `requests` used in `/app/backend/services/shipping_service.py` (2 places)
   - ❌ `requests` used in `/app/backend/server.py` (7 places)
   - **Impact**: Каждый HTTP call блокирует loop на 100-500ms → бот "висит"

2. **No Rate Limiting**
   - ❌ Spam от users перегружает DB/API
   - ❌ No protection against rapid messages

3. **No Background Tasks**
   - ❌ Heavy operations (label generation, API calls) блокируют handlers
   - ❌ No queue system

4. **No Error Monitoring**
   - ❌ No Sentry для tracking hangs/errors
   - ❌ No alerts на high latency

## 🔧 Implementation Plan

### Phase 1: Replace Sync HTTP with Async (CRITICAL - 2 hours)

**Priority**: 🔴 HIGHEST
**Impact**: 50-80% reduction in hangs
**Risk**: Medium (need thorough testing)

#### Files to Update:
1. `/app/backend/services/api_services.py`
   - Replace `requests.post` → `httpx.AsyncClient().post`
   - Add timeouts (5-10s)
   
2. `/app/backend/services/shipping_service.py`
   - Replace `requests.post/get` → `httpx.AsyncClient().post/get`
   
3. `/app/backend/server.py`
   - Replace all `requests` → `httpx`

#### Implementation:
```python
# Before (BLOCKS event loop!)
import requests
response = requests.post(url, json=data, timeout=10)

# After (NON-BLOCKING)
import httpx
async with httpx.AsyncClient(timeout=10.0) as client:
    response = await client.post(url, json=data)
```

#### Testing:
- Unit tests with `AsyncMock`
- Load test: 50 concurrent users
- Monitor: No event loop blocks

---

### Phase 2: Rate Limiting (HIGH - 1-2 hours)

**Priority**: 🟡 HIGH
**Impact**: 30-50% reduction in peak hangs
**Risk**: Low

#### Implementation:

**Option A: Simple In-Memory Rate Limiter**
```python
# /app/backend/middleware/rate_limiter.py
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.requests = defaultdict(list)
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
    
    def is_allowed(self, user_id: int) -> bool:
        now = datetime.now()
        # Clean old requests
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if now - req_time < self.window
        ]
        
        # Check limit
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        self.requests[user_id].append(now)
        return True
```

**Option B: PTB Built-in (if using PTB v20+)**
```python
from telegram.ext import MessageHandler, filters
from telegram.ext import ConversationHandler

# Add rate limit to handlers
@rate_limit(max_calls=5, window=60)  # 5 calls per minute
async def handle_message(update, context):
    ...
```

#### Integration:
- Add to all handlers
- Return friendly message: "⏳ Слишком много запросов, подождите 30 сек"

---

### Phase 3: Background Tasks with Celery (MEDIUM - 3-4 hours)

**Priority**: 🟢 MEDIUM
**Impact**: 40% reduction in hangs for heavy ops
**Risk**: Medium (new dependency)

#### Setup:
```bash
# Install dependencies
pip install celery redis

# Add to requirements.txt
celery==5.3.4
redis==5.0.1
```

#### Tasks to Move to Background:
1. **Label Generation** (slow, 2-5 seconds)
2. **Webhook processing from payment providers**
3. **Email/SMS notifications** (if any)

#### Implementation:
```python
# /app/backend/celery_app.py
from celery import Celery

celery_app = Celery(
    'telegram_bot',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# /app/backend/tasks/label_tasks.py
from celery_app import celery_app

@celery_app.task(bind=True, max_retries=3)
def generate_label_async(self, order_id, telegram_id):
    try:
        # Heavy label generation logic
        label = create_shipping_label(order_id)
        send_label_to_user(telegram_id, label)
        return {'success': True, 'label_id': label.id}
    except Exception as e:
        # Retry on failure
        raise self.retry(exc=e, countdown=60)
```

#### Handler Update:
```python
# Before (blocks bot)
label = await create_and_send_label(order_id, telegram_id, message)

# After (non-blocking)
from tasks.label_tasks import generate_label_async
task = generate_label_async.delay(order_id, telegram_id)
await message.reply_text("✅ Заказ создан! Label будет готов через 1-2 минуты.")
```

---

### Phase 4: Monitoring with Sentry (LOW - 1 hour)

**Priority**: 🟢 LOW (but important for production)
**Impact**: Early detection of hangs/errors
**Risk**: Low

#### Setup:
```bash
pip install sentry-sdk
```

#### Implementation:
```python
# /app/backend/server.py (at startup)
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastAPIIntegration

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[FastAPIIntegration()],
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)
```

#### Alerts:
- Slow transactions (>5s)
- Error rate spikes
- Memory leaks

---

### Phase 5: Additional Measures (Optional)

#### A. Event Loop Monitoring
```python
# /app/backend/utils/event_loop_monitor.py
import asyncio
import logging

logger = logging.getLogger(__name__)

async def monitor_event_loop():
    """Monitor event loop for blockage"""
    while True:
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(1)
        elapsed = asyncio.get_event_loop().time() - start
        
        if elapsed > 1.5:  # Should be ~1s
            logger.warning(f"⚠️ Event loop blocked for {elapsed:.2f}s!")
        
        await asyncio.sleep(10)
```

#### B. Scaling with Multiple Workers
```bash
# Gunicorn with Uvicorn workers
gunicorn server:app \
  -w 4 \
  --worker-class=uvicorn.workers.UvicornWorker \
  --bind=0.0.0.0:8001
```

#### C. Profiling
```bash
# Find bottlenecks
python -m cProfile -o profile.stats server.py
```

---

## 📊 Expected Results

| Measure | Hang Reduction | Latency Improvement |
|---------|----------------|---------------------|
| Async HTTP (Phase 1) | 50-80% | 200-500ms → 50-100ms |
| Rate Limiting (Phase 2) | 30-50% | Prevents overload spikes |
| Background Tasks (Phase 3) | 40% | 2-5s → instant response |
| Monitoring (Phase 4) | - | Early detection |

**Total Expected Impact**: 80-90% reduction in hangs

---

## 🧪 Testing Plan

### Load Testing
```python
# tests/load/test_concurrent_orders.py
import asyncio
import aiohttp

async def simulate_user(user_id):
    async with aiohttp.ClientSession() as session:
        # Simulate order creation
        async with session.post(
            f"{API_URL}/orders",
            json={"telegram_id": user_id, ...}
        ) as resp:
            return await resp.json()

async def test_50_concurrent_users():
    tasks = [simulate_user(i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    
    # Check: No timeouts, all succeeded
    assert all(r.get('success') for r in results)
```

### Metrics to Monitor
- ✅ Event loop latency < 100ms
- ✅ HTTP call duration < 500ms
- ✅ DB query duration < 100ms
- ✅ No timeout errors
- ✅ Memory usage stable

---

## 🚀 Rollout Strategy

**Week 1:**
- ✅ Phase 1 (Async HTTP) - CRITICAL
- ✅ Phase 2 (Rate Limiting)
- ✅ Testing with 50 users

**Week 2:**
- ✅ Phase 3 (Celery) - if needed
- ✅ Phase 4 (Sentry)
- ✅ Production rollout

---

## 📝 Maintenance

### Daily Checks
- Monitor Sentry for errors/slow transactions
- Check Celery queue length (`celery -A celery_app inspect active`)
- Review rate limit logs

### Weekly Reviews
- Analyze slow query logs
- Check MongoDB Atlas alerts
- Review event loop monitor logs

---

**Last Updated**: 2025-11-14
**Status**: 🚧 IN PROGRESS (Phase 1 starting)
