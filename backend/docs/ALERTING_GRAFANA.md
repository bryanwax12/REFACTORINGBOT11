# Alerting & Grafana Setup Guide

## Alerting System

### Overview
The built-in alerting system monitors key metrics and triggers alerts when thresholds are exceeded.

### Alert Endpoints

#### Get Active Alerts
```bash
GET /api/alerts/active
```

**Response:**
```json
{
  "count": 2,
  "alerts": [
    {
      "id": "High CPU Usage_1699999999",
      "severity": "warning",
      "title": "High CPU Usage",
      "message": "cpu_percent is 85.30 (threshold: 80.0)",
      "timestamp": "2025-11-14T12:00:00Z",
      "metric": "cpu_percent",
      "value": 85.3,
      "threshold": 80.0
    }
  ]
}
```

#### Get Alert Rules
```bash
GET /api/alerts/rules
```

#### Manual Alert Check
```bash
POST /api/alerts/check
```

#### Resolve Alert
```bash
POST /api/alerts/resolve/{alert_id}
```

### Pre-configured Alert Rules

#### System Alerts
1. **High CPU Usage** (Warning at 80%, Critical at 95%)
2. **High Memory Usage** (Warning at 85%, Critical at 95%)
3. **Low Disk Space** (Warning at 90%, Critical at 95%)

#### Business Alerts
1. **Low Order Success Rate** (Warning < 90%)
2. **High Payment Failure Rate** (Warning > 10%)

### Alert Severity Levels
- **Critical**: Immediate action required
- **Warning**: Should be investigated soon
- **Info**: Informational, no action needed

---

## Grafana Integration

### Installation (External)

**Note**: Grafana must be installed separately as it's not available within the Emergent platform.

#### Docker Installation
```bash
# Run Grafana in Docker
docker run -d \
  --name=grafana \
  -p 3000:3000 \
  grafana/grafana
```

#### Access Grafana
1. Open browser: `http://localhost:3000`
2. Default credentials: `admin` / `admin`
3. Change password on first login

### Connecting to Your Bot

#### Step 1: Add Data Source
1. Go to Configuration → Data Sources
2. Click "Add data source"
3. Select "JSON API" or "Infinity" plugin
4. Configure URL: `https://your-domain.com/api/monitoring/metrics`

#### Step 2: Import Dashboard
1. Go to Dashboards → Import
2. Upload `/app/backend/config/grafana_dashboard.json`
3. Select your data source
4. Click "Import"

### Dashboard Panels

The pre-configured dashboard includes:

#### 1. System Metrics
- CPU Usage (with alerts)
- Memory Usage
- Disk Usage

#### 2. Database Metrics
- Collection counts
- Query performance
- Slow queries

#### 3. Business Metrics
- Orders (24h)
- Total Revenue
- Payment Success Rate
- Active Users

#### 4. Performance Metrics
- Response times (P50, P95, P99)
- Request rate
- Error rate

### Custom Queries

#### Example: Orders Over Time
```
Query: /api/monitoring/stats/orders
Metric Path: orders_last_24h
Refresh: 30s
```

#### Example: User Growth
```
Query: /api/monitoring/stats/users
Metric Path: new_users_last_7_days
Refresh: 5m
```

### Alert Configuration in Grafana

#### CPU Alert Example
```json
{
  "alert": {
    "name": "High CPU Alert",
    "conditions": [
      {
        "evaluator": {
          "params": [80],
          "type": "gt"
        },
        "query": {
          "params": ["A", "5m", "now"]
        },
        "reducer": {
          "type": "avg"
        }
      }
    ],
    "executionErrorState": "alerting",
    "frequency": "1m",
    "handler": 1,
    "noDataState": "no_data",
    "notifications": []
  }
}
```

### Notification Channels

#### Email Notifications
1. Go to Alerting → Notification channels
2. Add notification channel
3. Select "Email"
4. Configure SMTP settings

#### Slack Notifications
1. Create Slack webhook URL
2. Add notification channel in Grafana
3. Select "Slack"
4. Paste webhook URL

#### Telegram Notifications
1. Create Telegram bot
2. Get bot token and chat ID
3. Add notification channel
4. Select "Telegram"
5. Configure bot settings

---

## Alternative: Simple Monitoring Dashboard

### Built-in Dashboard (No Grafana Required)

Create a simple HTML dashboard using our API:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Bot Monitor</title>
    <script>
        async function updateMetrics() {
            const response = await fetch('/api/monitoring/metrics');
            const data = await response.json();
            
            document.getElementById('cpu').textContent = 
                data.system.cpu_percent.toFixed(1) + '%';
            document.getElementById('memory').textContent = 
                data.system.memory.used_percent.toFixed(1) + '%';
            
            // Update every 5 seconds
            setTimeout(updateMetrics, 5000);
        }
        
        async function updateAlerts() {
            const response = await fetch('/api/alerts/active');
            const data = await response.json();
            
            const alertsDiv = document.getElementById('alerts');
            alertsDiv.innerHTML = data.alerts.map(a => 
                `<div class="alert ${a.severity}">
                    ${a.title}: ${a.message}
                </div>`
            ).join('');
            
            setTimeout(updateAlerts, 10000);
        }
        
        window.onload = () => {
            updateMetrics();
            updateAlerts();
        };
    </script>
    <style>
        body { font-family: Arial, sans-serif; }
        .metric { padding: 20px; margin: 10px; background: #f0f0f0; }
        .alert.critical { background: #ff4444; color: white; }
        .alert.warning { background: #ffaa00; }
    </style>
</head>
<body>
    <h1>System Monitor</h1>
    <div class="metric">
        CPU: <span id="cpu">-</span>
    </div>
    <div class="metric">
        Memory: <span id="memory">-</span>
    </div>
    <div id="alerts"></div>
</body>
</html>
```

---

## Best Practices

### 1. Alert Fatigue Prevention
- Set appropriate thresholds
- Implement alert grouping
- Add cooldown periods
- Auto-resolve old alerts

### 2. Dashboard Organization
- Group related metrics
- Use consistent time ranges
- Add descriptions to panels
- Set up drill-down views

### 3. Monitoring Strategy
- Monitor key business metrics
- Track technical metrics
- Set SLAs and SLOs
- Review alerts weekly

### 4. Performance
- Cache dashboard queries
- Use appropriate refresh intervals
- Limit data retention
- Archive old alerts

---

## Troubleshooting

### Grafana Can't Connect
1. Verify bot is running
2. Check firewall rules
3. Verify API endpoint URLs
4. Check CORS settings

### No Data Showing
1. Verify data source configuration
2. Check query syntax
3. Review time range
4. Check API response format

### Alerts Not Triggering
1. Verify alert rules are enabled
2. Check threshold values
3. Review notification channel config
4. Check alert evaluation frequency

---

Last Updated: November 14, 2025
