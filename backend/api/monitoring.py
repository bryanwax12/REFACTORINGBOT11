"""
Performance Monitoring API Endpoints
Provides metrics and health checks for the application
"""
from fastapi import APIRouter, Depends
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
import asyncio
import psutil
import os
from handlers.admin_handlers import verify_admin_key

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/health")
async def health_check() -> Dict:
    """
    Basic health check endpoint
    Returns service status, uptime and database connection status
    """
    from server import db
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "telegram-shipping-bot",
        "version": "1.0.0",
        "database": {}
    }
    
    # Check MongoDB connection
    try:
        await db.command('ping')
        health_status["database"]["status"] = "healthy"
        health_status["database"]["connected"] = True
    except Exception as e:
        health_status["database"]["status"] = "unhealthy"
        health_status["database"]["connected"] = False
        health_status["database"]["error"] = str(e)
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/metrics")
async def get_metrics(authenticated: bool = Depends(verify_admin_key)) -> Dict:
    """
    Get application performance metrics
    Requires admin authentication via X-API-Key header
    """
    from server import db
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Database metrics
    try:
        collections_stats = {}
        for coll_name in ['users', 'orders', 'templates', 'payments', 'user_sessions']:
            count = await db[coll_name].count_documents({})
            collections_stats[coll_name] = count
    except Exception as e:
        collections_stats = {"error": str(e)}
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory": {
                "total_mb": memory.total / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024),
                "used_percent": memory.percent
            },
            "disk": {
                "total_gb": disk.total / (1024 * 1024 * 1024),
                "used_gb": disk.used / (1024 * 1024 * 1024),
                "free_gb": disk.free / (1024 * 1024 * 1024),
                "percent": disk.percent
            }
        },
        "database": {
            "collections": collections_stats
        }
    }


@router.get("/stats/users")
async def get_user_stats(authenticated: bool = Depends(verify_admin_key)) -> Dict:
    """Get user statistics (requires admin authentication)"""
    from server import db
    
    try:
        total_users = await db.users.count_documents({})
        
        # Users with balance > 0
        users_with_balance = await db.users.count_documents({"balance": {"$gt": 0}})
        
        # Admin users
        admin_count = await db.users.count_documents({"is_admin": True})
        
        # Blocked users
        blocked_count = await db.users.count_documents({"is_blocked": True})
        
        # New users (last 7 days)
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        new_users_week = await db.users.count_documents({
            "created_at": {"$gte": week_ago}
        })
        
        return {
            "total_users": total_users,
            "users_with_balance": users_with_balance,
            "admin_users": admin_count,
            "blocked_users": blocked_count,
            "new_users_last_7_days": new_users_week
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats/orders")
async def get_order_stats(authenticated: bool = Depends(verify_admin_key)) -> Dict:
    """Get order statistics (requires admin authentication)"""
    from server import db
    
    try:
        total_orders = await db.orders.count_documents({})
        
        # Orders by payment status
        paid_orders = await db.orders.count_documents({"payment_status": "paid"})
        pending_orders = await db.orders.count_documents({"payment_status": "pending"})
        
        # Orders by shipping status
        shipped = await db.orders.count_documents({"shipping_status": "shipped"})
        delivered = await db.orders.count_documents({"shipping_status": "delivered"})
        
        # Recent orders (last 24h)
        day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent_orders = await db.orders.count_documents({
            "created_at": {"$gte": day_ago}
        })
        
        # Revenue (approximation)
        pipeline = [
            {"$match": {"payment_status": "paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        revenue_result = await db.orders.aggregate(pipeline).to_list(1)
        total_revenue = revenue_result[0]["total"] if revenue_result else 0
        
        return {
            "total_orders": total_orders,
            "paid_orders": paid_orders,
            "pending_orders": pending_orders,
            "shipped_orders": shipped,
            "delivered_orders": delivered,
            "orders_last_24h": recent_orders,
            "total_revenue_usd": round(total_revenue, 2)
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats/templates")
async def get_template_stats(authenticated: bool = Depends(verify_admin_key)) -> Dict:
    """Get template statistics (requires admin authentication)"""
    from server import db
    
    try:
        total_templates = await db.templates.count_documents({})
        
        # Most popular template names (aggregation)
        pipeline = [
            {"$group": {
                "_id": "$name",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        popular_names = await db.templates.aggregate(pipeline).to_list(5)
        
        return {
            "total_templates": total_templates,
            "popular_template_names": [
                {"name": item["_id"], "count": item["count"]}
                for item in popular_names
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats/payments")
async def get_payment_stats(authenticated: bool = Depends(verify_admin_key)) -> Dict:
    """Get payment statistics (requires admin authentication)"""
    from server import db
    
    try:
        total_payments = await db.payments.count_documents({})
        
        # By status
        paid_count = await db.payments.count_documents({"status": "paid"})
        pending_count = await db.payments.count_documents({"status": "pending"})
        failed_count = await db.payments.count_documents({"status": "failed"})
        
        # By type
        topup_count = await db.payments.count_documents({"type": "topup"})
        order_count = await db.payments.count_documents({"type": "order"})
        
        # Recent payments (last 24h)
        day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent_payments = await db.payments.count_documents({
            "created_at": {"$gte": day_ago}
        })
        
        return {
            "total_payments": total_payments,
            "paid": paid_count,
            "pending": pending_count,
            "failed": failed_count,
            "topups": topup_count,
            "order_payments": order_count,
            "payments_last_24h": recent_payments
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/db/indexes")
async def get_database_indexes(authenticated: bool = Depends(verify_admin_key)) -> Dict:
    """Get information about database indexes (requires admin authentication)"""
    from server import db
    
    try:
        collections = ['users', 'orders', 'templates', 'payments', 'user_sessions', 'pending_orders']
        indexes_info = {}
        
        for coll_name in collections:
            indexes = await db[coll_name].list_indexes().to_list(None)
            indexes_info[coll_name] = [
                {
                    "name": idx.get("name"),
                    "keys": str(idx.get("key")),
                    "unique": idx.get("unique", False)
                }
                for idx in indexes
            ]
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "indexes": indexes_info
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/performance/slow-queries")
async def get_slow_queries() -> Dict:
    """
    Get slow queries from MongoDB profiler
    Note: Profiling must be enabled
    """
    from server import db
    
    try:
        # Get slow queries (> 100ms)
        slow_queries = await db.system.profile.find({
            "millis": {"$gt": 100}
        }).sort("ts", -1).limit(10).to_list(10)
        
        return {
            "slow_queries_count": len(slow_queries),
            "queries": [
                {
                    "namespace": q.get("ns"),
                    "operation": q.get("op"),
                    "duration_ms": q.get("millis"),
                    "timestamp": q.get("ts")
                }
                for q in slow_queries
            ] if slow_queries else []
        }
    except Exception as e:
        return {
            "error": str(e),
            "note": "Profiling may not be enabled. Run optimize_database.py to enable."
        }


@router.get("/performance/cache-stats")
async def get_cache_stats() -> Dict:
    """Get caching statistics (if implemented)"""
    return {
        "note": "Cache statistics not yet implemented",
        "suggestion": "Consider implementing Redis for caching (if available on platform)"
    }
