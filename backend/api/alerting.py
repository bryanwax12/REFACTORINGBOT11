"""
Alerting System
Monitors system health and triggers alerts based on thresholds
"""
from fastapi import APIRouter, BackgroundTasks
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import logging
import asyncio

router = APIRouter(prefix="/api/alerts", tags=["alerting"])
logger = logging.getLogger(__name__)


# Alert Models
class Alert(BaseModel):
    """Alert model"""
    id: str
    severity: str  # critical, warning, info
    title: str
    message: str
    timestamp: datetime
    resolved: bool = False
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


class AlertRule(BaseModel):
    """Alert rule configuration"""
    name: str
    metric: str
    condition: str  # gt, lt, eq
    threshold: float
    severity: str
    enabled: bool = True


# In-memory alert storage (in production, use database)
active_alerts: List[Alert] = []
alert_rules: List[AlertRule] = [
    # CPU Alert
    AlertRule(
        name="High CPU Usage",
        metric="cpu_percent",
        condition="gt",
        threshold=80.0,
        severity="warning"
    ),
    AlertRule(
        name="Critical CPU Usage",
        metric="cpu_percent",
        condition="gt",
        threshold=95.0,
        severity="critical"
    ),
    # Memory Alerts
    AlertRule(
        name="High Memory Usage",
        metric="memory_percent",
        condition="gt",
        threshold=85.0,
        severity="warning"
    ),
    AlertRule(
        name="Critical Memory Usage",
        metric="memory_percent",
        condition="gt",
        threshold=95.0,
        severity="critical"
    ),
    # Disk Alerts
    AlertRule(
        name="Low Disk Space",
        metric="disk_percent",
        condition="gt",
        threshold=90.0,
        severity="warning"
    ),
    AlertRule(
        name="Critical Disk Space",
        metric="disk_percent",
        condition="gt",
        threshold=95.0,
        severity="critical"
    ),
    # Order Processing
    AlertRule(
        name="Low Order Success Rate",
        metric="order_success_rate",
        condition="lt",
        threshold=90.0,
        severity="warning"
    ),
    # Payment Processing
    AlertRule(
        name="High Payment Failure Rate",
        metric="payment_failure_rate",
        condition="gt",
        threshold=10.0,
        severity="warning"
    )
]


def check_condition(value: float, condition: str, threshold: float) -> bool:
    """Check if condition is met"""
    if condition == "gt":
        return value > threshold
    elif condition == "lt":
        return value < threshold
    elif condition == "eq":
        return value == threshold
    return False


def create_alert(rule: AlertRule, value: float) -> Alert:
    """Create an alert from a rule"""
    alert_id = f"{rule.name}_{datetime.now().timestamp()}"
    
    return Alert(
        id=alert_id,
        severity=rule.severity,
        title=rule.name,
        message=f"{rule.metric} is {value:.2f} (threshold: {rule.threshold})",
        timestamp=datetime.now(timezone.utc),
        metric_name=rule.metric,
        metric_value=value,
        threshold=rule.threshold
    )


async def check_system_metrics():
    """Check system metrics and trigger alerts"""
    import psutil
    
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent
        }
        
        # Check each rule
        new_alerts = []
        for rule in alert_rules:
            if not rule.enabled:
                continue
            
            if rule.metric in metrics:
                value = metrics[rule.metric]
                
                if check_condition(value, rule.condition, rule.threshold):
                    # Check if alert already exists
                    existing = any(
                        a.title == rule.name and not a.resolved
                        for a in active_alerts
                    )
                    
                    if not existing:
                        alert = create_alert(rule, value)
                        new_alerts.append(alert)
                        logger.warning(f"🚨 ALERT: {alert.title} - {alert.message}")
        
        # Add new alerts
        active_alerts.extend(new_alerts)
        
        # Auto-resolve old alerts (older than 5 minutes)
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        for alert in active_alerts:
            if alert.timestamp < five_min_ago and not alert.resolved:
                alert.resolved = True
                logger.info(f"✅ Auto-resolved: {alert.title}")
        
        return len(new_alerts)
        
    except Exception as e:
        logger.error(f"Error checking metrics: {e}")
        return 0


async def check_business_metrics():
    """Check business metrics and trigger alerts"""
    from server import db
    from datetime import timedelta
    
    try:
        # Check recent order success rate
        day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        total_orders = await db.orders.count_documents({
            "created_at": {"$gte": day_ago}
        })
        
        if total_orders > 0:
            successful_orders = await db.orders.count_documents({
                "created_at": {"$gte": day_ago},
                "payment_status": "paid"
            })
            
            success_rate = (successful_orders / total_orders) * 100
            
            # Check success rate alert
            for rule in alert_rules:
                if rule.metric == "order_success_rate" and rule.enabled:
                    if check_condition(success_rate, rule.condition, rule.threshold):
                        existing = any(
                            a.metric_name == "order_success_rate" and not a.resolved
                            for a in active_alerts
                        )
                        
                        if not existing:
                            alert = create_alert(rule, success_rate)
                            active_alerts.append(alert)
                            logger.warning(f"🚨 ALERT: {alert.title} - {alert.message}")
        
        # Check payment failure rate
        total_payments = await db.payments.count_documents({
            "created_at": {"$gte": day_ago}
        })
        
        if total_payments > 0:
            failed_payments = await db.payments.count_documents({
                "created_at": {"$gte": day_ago},
                "status": "failed"
            })
            
            failure_rate = (failed_payments / total_payments) * 100
            
            for rule in alert_rules:
                if rule.metric == "payment_failure_rate" and rule.enabled:
                    if check_condition(failure_rate, rule.condition, rule.threshold):
                        existing = any(
                            a.metric_name == "payment_failure_rate" and not a.resolved
                            for a in active_alerts
                        )
                        
                        if not existing:
                            alert = create_alert(rule, failure_rate)
                            active_alerts.append(alert)
                            logger.warning(f"🚨 ALERT: {alert.title} - {alert.message}")
    
    except Exception as e:
        logger.error(f"Error checking business metrics: {e}")


@router.get("/active")
async def get_active_alerts() -> Dict:
    """Get all active (unresolved) alerts"""
    unresolved = [a for a in active_alerts if not a.resolved]
    
    return {
        "count": len(unresolved),
        "alerts": [
            {
                "id": a.id,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "timestamp": a.timestamp.isoformat(),
                "metric": a.metric_name,
                "value": a.metric_value,
                "threshold": a.threshold
            }
            for a in unresolved
        ]
    }


@router.get("/history")
async def get_alert_history(limit: int = 50) -> Dict:
    """Get alert history"""
    recent = sorted(active_alerts, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    return {
        "count": len(recent),
        "alerts": [
            {
                "id": a.id,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "timestamp": a.timestamp.isoformat(),
                "resolved": a.resolved,
                "metric": a.metric_name,
                "value": a.metric_value
            }
            for a in recent
        ]
    }


@router.get("/rules")
async def get_alert_rules() -> Dict:
    """Get configured alert rules"""
    return {
        "count": len(alert_rules),
        "rules": [
            {
                "name": r.name,
                "metric": r.metric,
                "condition": r.condition,
                "threshold": r.threshold,
                "severity": r.severity,
                "enabled": r.enabled
            }
            for r in alert_rules
        ]
    }


@router.post("/check")
async def trigger_alert_check(background_tasks: BackgroundTasks) -> Dict:
    """Manually trigger alert check"""
    background_tasks.add_task(check_system_metrics)
    background_tasks.add_task(check_business_metrics)
    
    return {
        "status": "Alert check triggered",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/resolve/{alert_id}")
async def resolve_alert(alert_id: str) -> Dict:
    """Manually resolve an alert"""
    for alert in active_alerts:
        if alert.id == alert_id:
            alert.resolved = True
            return {
                "status": "Alert resolved",
                "alert_id": alert_id
            }
    
    return {
        "status": "Alert not found",
        "alert_id": alert_id
    }


@router.get("/summary")
async def get_alert_summary() -> Dict:
    """Get alert summary statistics"""
    active = [a for a in active_alerts if not a.resolved]
    
    by_severity = {
        "critical": sum(1 for a in active if a.severity == "critical"),
        "warning": sum(1 for a in active if a.severity == "warning"),
        "info": sum(1 for a in active if a.severity == "info")
    }
    
    recent_24h = [
        a for a in active_alerts
        if a.timestamp > datetime.now(timezone.utc) - timedelta(hours=24)
    ]
    
    return {
        "active_alerts": len(active),
        "by_severity": by_severity,
        "alerts_last_24h": len(recent_24h),
        "total_rules": len(alert_rules),
        "enabled_rules": sum(1 for r in alert_rules if r.enabled)
    }


# Background task to periodically check alerts
async def periodic_alert_check():
    """Run periodic alert checks"""
    while True:
        try:
            await check_system_metrics()
            await check_business_metrics()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error in periodic alert check: {e}")
            await asyncio.sleep(60)
