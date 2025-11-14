"""
Stats Admin Service
Handles statistics and analytics for admin panel
"""
import logging
from typing import Dict, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class StatsAdminService:
    """Service for generating admin statistics"""
    
    @staticmethod
    async def get_dashboard_stats(db) -> Dict:
        """
        Get main dashboard statistics
        
        Args:
            db: Database instance
        
        Returns:
            Dashboard statistics
        """
        try:
            # User statistics
            total_users = await db.users.count_documents({})
            blocked_users = await db.users.count_documents({"blocked": True})
            users_with_balance = await db.users.count_documents({"balance": {"$gt": 0}})
            
            # Order statistics
            total_orders = await db.orders.count_documents({})
            paid_orders = await db.orders.count_documents({"payment_status": "paid"})
            pending_orders = await db.orders.count_documents({"payment_status": "pending"})
            
            # Revenue
            revenue_pipeline = [
                {"$match": {"payment_status": "paid"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            revenue_result = await db.orders.aggregate(revenue_pipeline).to_list(1)
            total_revenue = revenue_result[0]["total"] if revenue_result else 0
            
            # Recent activity (last 24h)
            day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            new_users_24h = await db.users.count_documents({"created_at": {"$gte": day_ago}})
            new_orders_24h = await db.orders.count_documents({"created_at": {"$gte": day_ago}})
            
            return {
                "users": {
                    "total": total_users,
                    "blocked": blocked_users,
                    "with_balance": users_with_balance,
                    "new_24h": new_users_24h
                },
                "orders": {
                    "total": total_orders,
                    "paid": paid_orders,
                    "pending": pending_orders,
                    "new_24h": new_orders_24h
                },
                "revenue": {
                    "total": round(total_revenue, 2),
                    "currency": "USD"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {"error": str(e)}
    
    
    @staticmethod
    async def get_expense_stats(db, days: int = 30) -> Dict:
        """
        Get expense statistics for specified period
        
        Args:
            db: Database instance
            days: Number of days to analyze
        
        Returns:
            Expense statistics
        """
        try:
            start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            # Get all paid orders in period
            orders = await db.orders.find({
                "payment_status": "paid",
                "created_at": {"$gte": start_date}
            }, {"_id": 0, "amount": 1, "created_at": 1, "carrier": 1}).to_list(1000)
            
            if not orders:
                return {
                    "period_days": days,
                    "total_expenses": 0,
                    "total_orders": 0,
                    "average_per_order": 0,
                    "by_carrier": {}
                }
            
            # Calculate totals
            total_expenses = sum(o.get("amount", 0) for o in orders)
            total_orders = len(orders)
            average_per_order = total_expenses / total_orders if total_orders > 0 else 0
            
            # Group by carrier
            by_carrier = {}
            for order in orders:
                carrier = order.get("carrier", "Unknown")
                if carrier not in by_carrier:
                    by_carrier[carrier] = {"count": 0, "total": 0}
                by_carrier[carrier]["count"] += 1
                by_carrier[carrier]["total"] += order.get("amount", 0)
            
            # Calculate averages
            for carrier, data in by_carrier.items():
                data["average"] = round(data["total"] / data["count"], 2)
                data["total"] = round(data["total"], 2)
            
            return {
                "period_days": days,
                "total_expenses": round(total_expenses, 2),
                "total_orders": total_orders,
                "average_per_order": round(average_per_order, 2),
                "by_carrier": by_carrier,
                "start_date": start_date
            }
        
        except Exception as e:
            logger.error(f"Error getting expense stats: {e}")
            return {"error": str(e)}
    
    
    @staticmethod
    async def get_topup_stats(db, limit: int = 50) -> Dict:
        """
        Get recent top-up statistics
        
        Args:
            db: Database instance
            limit: Number of recent top-ups
        
        Returns:
            Top-up statistics
        """
        try:
            # Get recent top-ups
            topups = await db.payments.find(
                {"type": "topup", "status": "paid"},
                {"_id": 0}
            ).sort("created_at", -1).limit(limit).to_list(limit)
            
            if not topups:
                return {
                    "recent_topups": [],
                    "total_amount": 0,
                    "count": 0
                }
            
            # Calculate total
            total_amount = sum(t.get("amount", 0) for t in topups)
            
            return {
                "recent_topups": topups,
                "total_amount": round(total_amount, 2),
                "count": len(topups)
            }
        
        except Exception as e:
            logger.error(f"Error getting topup stats: {e}")
            return {"error": str(e)}
    
    
    @staticmethod
    async def get_performance_stats(db) -> Dict:
        """
        Get performance statistics
        
        Args:
            db: Database instance
        
        Returns:
            Performance statistics
        """
        try:
            # Active sessions
            active_sessions = await db.user_sessions.count_documents({})
            
            # Pending orders
            pending_orders = await db.pending_orders.count_documents({})
            
            # Payment success rate (last 24h)
            day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            total_payments = await db.payments.count_documents({"created_at": {"$gte": day_ago}})
            successful_payments = await db.payments.count_documents({
                "created_at": {"$gte": day_ago},
                "status": "paid"
            })
            
            success_rate = (successful_payments / total_payments * 100) if total_payments > 0 else 0
            
            return {
                "active_sessions": active_sessions,
                "pending_orders": pending_orders,
                "payment_stats_24h": {
                    "total": total_payments,
                    "successful": successful_payments,
                    "success_rate": round(success_rate, 2)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {"error": str(e)}


# Singleton instance
stats_admin_service = StatsAdminService()
