# Monitoring & Metrics Guide

## Overview
Performance monitoring endpoints provide real-time insights into application health, performance, and usage statistics.

## Available Endpoints

### Health Check
```
GET /api/monitoring/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-14T12:00:00Z",
  "service": "telegram-shipping-bot",
  "version": "1.0.0"
}
```

**Use Case:** Load balancer health checks, uptime monitoring

---

### System Metrics
```
GET /api/monitoring/metrics
```

**Response:**
```json
{
  "timestamp": "2025-11-14T12:00:00Z",
  "system": {
    "cpu_percent": 15.3,
    "memory": {
      "total_mb": 8192,
      "available_mb": 4096,
      "used_percent": 50.0
    },
    "disk": {
      "total_gb": 100,
      "used_gb": 45,
      "free_gb": 55,
      "percent": 45.0
    }
  },
  "database": {
    "collections": {
      "users": 1250,
      "orders": 3450,
      "templates": 890,
      "payments": 4120,
      "user_sessions": 45
    }
  }
}
```

**Use Case:** System resource monitoring, capacity planning

---

### User Statistics
```
GET /api/monitoring/stats/users
```

**Response:**
```json
{
  "total_users": 1250,
  "users_with_balance": 450,
  "admin_users": 5,
  "blocked_users": 12,
  "new_users_last_7_days": 87
}
```

**Use Case:** User growth tracking, user management

---

### Order Statistics
```
GET /api/monitoring/stats/orders
```

**Response:**
```json
{
  "total_orders": 3450,
  "paid_orders": 3200,
  "pending_orders": 150,
  "shipped_orders": 2800,
  "delivered_orders": 2500,
  "orders_last_24h": 45,
  "total_revenue_usd": 52500.75
}
```

**Use Case:** Business metrics, revenue tracking

---

### Template Statistics
```
GET /api/monitoring/stats/templates
```

**Response:**
```json
{
  "total_templates": 890,
  "popular_template_names": [
    {"name": "Home to Office", "count": 125},
    {"name": "Family Package", "count": 98},
    {"name": "Business", "count": 76}
  ]
}
```

**Use Case:** Feature usage analytics

---

### Payment Statistics
```
GET /api/monitoring/stats/payments
```

**Response:**
```json
{
  "total_payments": 4120,
  "paid": 3850,
  "pending": 200,
  "failed": 70,
  "topups": 1200,
  "order_payments": 2920,
  "payments_last_24h": 67
}
```

**Use Case:** Payment processing monitoring, revenue analysis

---

### Database Indexes
```
GET /api/monitoring/db/indexes
```

**Response:**
```json
{
  "timestamp": "2025-11-14T12:00:00Z",
  "indexes": {
    "users": [
      {
        "name": "_id_",
        "keys": "{'_id': 1}",
        "unique": false
      },
      {
        "name": "telegram_id_1",
        "keys": "{'telegram_id': 1}",
        "unique": true
      }
    ]
  }
}
```

**Use Case:** Database optimization verification

---

### Slow Queries
```
GET /api/monitoring/performance/slow-queries
```

**Response:**
```json
{
  "slow_queries_count": 3,
  "queries": [
    {
      "namespace": "telegram_shipping_bot.orders",
      "operation": "query",
      "duration_ms": 156,
      "timestamp": "2025-11-14T11:45:00Z"
    }
  ]
}
```

**Use Case:** Query performance optimization, bottleneck identification

**Note:** Requires MongoDB profiling to be enabled (run `optimize_database.py`)

---

## Monitoring Best Practices

### 1. Regular Health Checks
Set up automated health checks every 30 seconds:
```bash
*/30 * * * * curl -f https://your-domain.com/api/monitoring/health || alert
```

### 2. Resource Monitoring
Monitor system resources and set alerts:
- **CPU > 80%**: Scale up or optimize code
- **Memory > 85%**: Investigate memory leaks
- **Disk > 90%**: Clean up logs, archive data

### 3. Business Metrics
Track key metrics daily:
- New users (growth rate)
- Order volume (revenue)
- Payment success rate
- Average order value

### 4. Performance Metrics
Monitor query performance:
- Slow queries (> 100ms)
- Index usage
- Database connection pool

---

## Integration with Monitoring Tools

### Prometheus (Example)
```yaml
scrape_configs:
  - job_name: 'telegram-bot'
    metrics_path: '/api/monitoring/metrics'
    static_configs:
      - targets: ['your-domain.com']
```

### Grafana Dashboard
Create dashboards with panels for:
1. System Resources (CPU, Memory, Disk)
2. Database Collections Count
3. Order Volume (daily)
4. Revenue Trends
5. User Growth

### Alerting Rules

**High CPU Alert:**
```yaml
alert: HighCPUUsage
expr: system_cpu_percent > 80
for: 5m
labels:
  severity: warning
annotations:
  summary: "High CPU usage detected"
```

**Low Disk Space:**
```yaml
alert: LowDiskSpace
expr: system_disk_percent > 90
for: 1m
labels:
  severity: critical
annotations:
  summary: "Disk space critically low"
```

---

## Performance Benchmarks

### Expected Response Times
| Endpoint | Target | Acceptable | Slow |
|----------|--------|------------|------|
| /health | < 10ms | < 50ms | > 100ms |
| /metrics | < 100ms | < 300ms | > 500ms |
| /stats/* | < 200ms | < 500ms | > 1000ms |

### Database Query Times (with indexes)
| Operation | Target | Acceptable | Slow |
|-----------|--------|------------|------|
| User lookup | < 1ms | < 5ms | > 10ms |
| Order history | < 5ms | < 20ms | > 50ms |
| Stats aggregation | < 50ms | < 200ms | > 500ms |

---

## Troubleshooting

### High Response Times
1. Check slow queries endpoint
2. Verify indexes are being used
3. Check system resources (CPU, memory)
4. Review application logs

### Missing Metrics
1. Verify database connection
2. Check permissions for system metrics
3. Ensure profiling is enabled for slow queries

### Incorrect Statistics
1. Verify MongoDB aggregation queries
2. Check data consistency
3. Review timezone handling

---

## Security Considerations

### Access Control
Monitoring endpoints should be protected:
```python
# Add authentication middleware
@router.get("/metrics")
async def get_metrics(api_key: str = Depends(verify_api_key)):
    # ... metrics code
```

### Sensitive Data
Never expose:
- User personal information
- API keys or secrets
- Detailed error messages (in production)
- Database connection strings

### Rate Limiting
Implement rate limiting on monitoring endpoints:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.get("/metrics")
@limiter.limit("10/minute")
async def get_metrics():
    # ... metrics code
```

---

## Future Enhancements

1. **Real-time Metrics**: WebSocket endpoint for live updates
2. **Custom Metrics**: User-defined metrics and dimensions
3. **Log Aggregation**: Centralized logging with search
4. **Distributed Tracing**: Request flow visualization
5. **Alerting System**: Built-in alert configuration

---

Last Updated: November 14, 2025
