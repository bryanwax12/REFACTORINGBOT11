"""
Bot Management Router
Эндпоинты для управления ботом
"""
from fastapi import APIRouter, HTTPException, Depends
from handlers.admin_handlers import verify_admin_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot", tags=["bot"])


@router.get("/health")
async def bot_health():
    """Check bot health status"""
    from server import bot_instance, application
    
    try:
        if not bot_instance:
            return {"status": "error", "message": "Bot not initialized"}
        
        bot_info = await bot_instance.get_me()
        
        return {
            "status": "healthy",
            "bot_username": bot_info.username,
            "bot_id": bot_info.id,
            "bot_name": bot_info.first_name,
            "application_running": application is not None
        }
    except Exception as e:
        logger.error(f"Error checking bot health: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/status")
async def telegram_status():
    """Get detailed Telegram bot status"""
    from server import bot_instance, application, BOT_MODE
    
    try:
        if not bot_instance:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        
        bot_info = await bot_instance.get_me()
        
        webhook_info = None
        if BOT_MODE == "webhook":
            webhook_info = await bot_instance.get_webhook_info()
        
        return {
            "bot_id": bot_info.id,
            "username": bot_info.username,
            "first_name": bot_info.first_name,
            "mode": BOT_MODE,
            "webhook_info": {
                "url": webhook_info.url if webhook_info else None,
                "has_custom_certificate": webhook_info.has_custom_certificate if webhook_info else False,
                "pending_update_count": webhook_info.pending_update_count if webhook_info else 0
            } if BOT_MODE == "webhook" else None,
            "application_initialized": application is not None
        }
    except Exception as e:
        logger.error(f"Error getting telegram status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart", dependencies=[Depends(verify_admin_key)])
async def restart_bot():
    """Restart bot (supervisor restart) - ADMIN ONLY"""
    import subprocess
    
    try:
        # Restart backend service via supervisor
        result = subprocess.run(
            ['sudo', 'supervisorctl', 'restart', 'backend'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return {
            "status": "restarting",
            "message": "Bot restart initiated",
            "output": result.stdout
        }
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_bot_logs(lines: int = 100):
    """Get recent bot logs"""
    import subprocess
    import re
    from datetime import datetime
    
    try:
        result = subprocess.run(
            ['tail', '-n', str(lines), '/var/log/supervisor/backend.out.log'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Parse logs into structured format
        log_lines = result.stdout.strip().split('\n')
        parsed_logs = []
        
        for line in log_lines:
            if not line.strip():
                continue
            
            # Try to parse structured logs (level:module:message format)
            log_entry = {
                "timestamp": "",
                "level": "INFO",
                "category": "system",
                "message": line
            }
            
            # Match pattern: LEVEL:module:message or LEVEL - message
            level_match = re.match(r'^(INFO|WARNING|ERROR|DEBUG|CRITICAL)[:\s-]+(.+)$', line)
            if level_match:
                log_entry["level"] = level_match.group(1)
                log_entry["message"] = level_match.group(2)
                
                # Try to extract timestamp if present
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})', line)
                if time_match:
                    log_entry["timestamp"] = time_match.group(1)
                else:
                    log_entry["timestamp"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                
                # Try to extract category/module
                if "order" in line.lower():
                    log_entry["category"] = "orders"
                elif "user" in line.lower():
                    log_entry["category"] = "users"
                elif "payment" in line.lower():
                    log_entry["category"] = "payments"
                elif "telegram" in line.lower() or "bot" in line.lower():
                    log_entry["category"] = "telegram"
                elif "uvicorn" in line.lower() or "GET" in line or "POST" in line:
                    log_entry["category"] = "api"
                else:
                    log_entry["category"] = "system"
            else:
                # Plain text line
                log_entry["timestamp"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                log_entry["category"] = "system"
            
            parsed_logs.append(log_entry)
        
        return {
            "logs": parsed_logs,
            "total": len(parsed_logs)
        }
    except Exception as e:
        logger.error(f"Error getting bot logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_bot_metrics():
    """Get bot metrics and statistics"""
    from server import db
    from repositories import get_user_repo, get_order_repo
    from datetime import datetime, timedelta
    
    try:
        user_repo = get_user_repo()
        order_repo = get_order_repo()
        
        # Get basic metrics
        total_users = await user_repo.count()
        total_orders = await order_repo.count()
        
        # Get recent activity
        active_sessions = await db.user_sessions.count_documents({})
        
        # Get users with balance > 0
        premium_users = await db.users.count_documents({"balance": {"$gt": 0}})
        
        # Get active users today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = await db.orders.distinct("telegram_id", {
            "created_at": {"$gte": today_start.isoformat()}
        })
        
        # Calculate revenue
        orders = await db.orders.find(
            {"payment_status": "paid"},
            {"_id": 0, "amount": 1}
        ).to_list(10000)
        
        total_revenue = sum(order.get("amount", 0) for order in orders)
        average_order = total_revenue / len(orders) if orders else 0
        
        # Get pending/completed orders
        pending_orders = await db.orders.count_documents({"shipping_status": {"$in": ["pending", "processing"]}})
        completed_orders = await db.orders.count_documents({"shipping_status": "label_created"})
        
        return {
            "users": {
                "total": total_users,
                "premium": premium_users,
                "active_today": len(active_today)
            },
            "orders": {
                "total": total_orders,
                "pending": pending_orders,
                "completed": completed_orders
            },
            "revenue": {
                "total": round(total_revenue, 2),
                "average_order": round(average_order, 2)
            },
            "sessions": {
                "active": active_sessions
            }
        }
    except Exception as e:
        logger.error(f"Error getting bot metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
