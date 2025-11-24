# Load Testing Guide

## Overview
Load testing helps identify performance bottlenecks and ensures the application can handle expected traffic.

## Running Load Tests

### Quick Test
```bash
cd /app/backend
python tests/load/test_load_performance.py quick
```

### Full Test Suite
```bash
cd /app/backend
python tests/load/test_load_performance.py
```

### Custom Test
```python
from tests.load.test_load_performance import LoadTester
import asyncio

async def custom_test():
    tester = LoadTester('https://your-domain.com')
    await tester.test_endpoint_load(
        '/api/monitoring/metrics',
        concurrent=20,
        total=100
    )

asyncio.run(custom_test())
```

## Test Scenarios

### 1. Light Load (Baseline)
- **Concurrent**: 5 requests
- **Total**: 50 requests
- **Purpose**: Establish baseline performance

### 2. Medium Load
- **Concurrent**: 10 requests
- **Total**: 100 requests
- **Purpose**: Simulate normal traffic

### 3. Heavy Load
- **Concurrent**: 20 requests
- **Total**: 200 requests
- **Purpose**: Stress test under peak load

### 4. Burst Load
- **Concurrent**: 50 requests
- **Total**: 500 requests
- **Purpose**: Test system resilience

## Performance Metrics

### Response Time Targets

| Endpoint | Target (P95) | Acceptable | Critical |
|----------|--------------|------------|----------|
| /health | < 50ms | < 100ms | > 200ms |
| /metrics | < 200ms | < 500ms | > 1000ms |
| /stats/* | < 300ms | < 800ms | > 1500ms |

### Success Rate Targets
- **Excellent**: > 99.9%
- **Good**: > 99%
- **Acceptable**: > 95%
- **Critical**: < 95%

## Interpreting Results

### Example Output
```
📊 Results for /api/monitoring/health:
   Success Rate: 100.0%
   Mean Response: 15.3ms
   Median: 12.1ms
   P95: 25.4ms
   P99: 32.8ms
```

### Analysis
- **Mean < Target**: Good average performance
- **P95 < Target**: 95% of requests perform well
- **P99 < 2x Target**: Acceptable for worst-case
- **Success Rate 100%**: No failures under load

## Common Issues & Solutions

### High Response Times
**Symptoms**: P95 > 500ms
**Causes**:
- Slow database queries
- Unoptimized code
- Resource contention

**Solutions**:
1. Check slow queries: `/api/monitoring/performance/slow-queries`
2. Verify indexes are used
3. Profile code with cProfile
4. Scale resources

### Low Success Rate
**Symptoms**: < 95% success
**Causes**:
- Connection limits
- Timeouts
- Database connection pool exhausted

**Solutions**:
1. Increase connection pool size
2. Implement connection retry logic
3. Add request timeout handling
4. Scale horizontally

### Memory Growth
**Symptoms**: Memory usage increasing during test
**Causes**:
- Memory leaks
- Unclosed connections
- Large response caching

**Solutions**:
1. Profile memory usage
2. Verify proper resource cleanup
3. Implement response streaming
4. Add memory limits

## Best Practices

### 1. Test in Staging First
Never run heavy load tests in production without testing in staging.

### 2. Monitor During Tests
Watch system metrics while running load tests:
```bash
# Terminal 1: Run load test
python tests/load/test_load_performance.py

# Terminal 2: Monitor metrics
watch -n 1 curl -s http://localhost:8001/api/monitoring/metrics
```

### 3. Gradual Increase
Increase load gradually:
- Start with 10 concurrent
- Double each test
- Find breaking point

### 4. Document Results
Keep a log of load test results over time to track performance trends.

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Load Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Load Tests
        run: |
          cd backend
          python tests/load/test_load_performance.py
      - name: Check Results
        run: |
          # Fail if P95 > threshold
          # Parse results and compare
```

## Advanced Scenarios

### Spike Testing
Sudden increase in load:
```python
# Gradually increase, then spike
await tester.test_endpoint_load(endpoint, concurrent=10, total=100)
await tester.test_endpoint_load(endpoint, concurrent=50, total=500)  # Spike
```

### Soak Testing
Prolonged load to detect memory leaks:
```python
# Run for extended period
for i in range(60):  # 60 minutes
    await tester.test_endpoint_load(endpoint, concurrent=10, total=100)
    await asyncio.sleep(60)
```

### Stress Testing
Find breaking point:
```python
concurrency = 10
while success_rate > 95:
    results = await tester.test_endpoint_load(
        endpoint,
        concurrent=concurrency,
        total=concurrency * 10
    )
    concurrency += 10
    
print(f"Breaking point: {concurrency} concurrent requests")
```

---

Last Updated: November 14, 2025
