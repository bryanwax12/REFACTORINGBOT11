"""
Optimized Database Queries
Provides optimized query functions with proper projections and indexes
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class OptimizedQueries:
    """Optimized database query utilities"""
    
    @staticmethod
    async def find_user_by_telegram_id_optimized(db, telegram_id: int, projection: Optional[Dict] = None) -> Optional[Dict]:
        """
        Optimized user lookup with projection
        Uses idx_telegram_id_unique index
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            projection: Fields to return (None = all fields)
        
        Returns:
            User document or None
        """
        if projection is None:
            # Default projection: exclude MongoDB _id, include commonly used fields
            projection = {
                "_id": 0,
                "id": 1,
                "telegram_id": 1,
                "balance": 1,
                "discount": 1,
                "is_admin": 1,
                "is_blocked": 1,
                "created_at": 1
            }
        
        return await db.users.find_one(
            {"telegram_id": telegram_id},
            projection
        )
    
    
    @staticmethod
    async def get_user_orders_paginated(
        db,
        telegram_id: int,
        limit: int = 10,
        skip: int = 0,
        include_fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Get user's orders with pagination
        Uses idx_user_orders compound index (telegram_id + created_at)
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            limit: Maximum number of orders to return
            skip: Number of orders to skip (for pagination)
            include_fields: Specific fields to include (None = basic fields only)
        
        Returns:
            List of order documents
        """
        projection = {"_id": 0}
        
        if include_fields:
            # Include only specified fields
            for field in include_fields:
                projection[field] = 1
        else:
            # Default: basic order info
            projection.update({
                "id": 1,
                "order_number": 1,
                "created_at": 1,
                "payment_status": 1,
                "shipping_status": 1,
                "tracking_number": 1,
                "carrier": 1,
                "amount": 1
            })
        
        return await db.orders.find(
            {"telegram_id": telegram_id},
            projection
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    
    
    @staticmethod
    async def get_user_templates_optimized(
        db,
        telegram_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get user's templates
        Uses idx_user_templates compound index (telegram_id + created_at)
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            limit: Maximum number of templates
        
        Returns:
            List of template documents
        """
        projection = {
            "_id": 0,
            "id": 1,
            "name": 1,
            "from_name": 1,
            "from_city": 1,
            "from_state": 1,
            "to_name": 1,
            "to_city": 1,
            "to_state": 1,
            "created_at": 1
        }
        
        return await db.templates.find(
            {"telegram_id": telegram_id},
            projection
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    
    @staticmethod
    async def find_pending_order_optimized(db, telegram_id: int) -> Optional[Dict]:
        """
        Find user's pending order
        Uses idx_pending_user_unique index
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
        
        Returns:
            Pending order document or None
        """
        return await db.pending_orders.find_one(
            {"telegram_id": telegram_id},
            {"_id": 0}
        )
    
    
    @staticmethod
    async def find_payment_by_invoice_optimized(db, invoice_id: str) -> Optional[Dict]:
        """
        Find payment by invoice ID
        Uses idx_invoice_id index
        
        Args:
            db: Database instance
            invoice_id: Oxapay invoice/track ID
        
        Returns:
            Payment document or None
        """
        return await db.payments.find_one(
            {"invoice_id": invoice_id},
            {"_id": 0}
        )
    
    
    @staticmethod
    async def get_recent_payments(
        db,
        telegram_id: int,
        limit: int = 5
    ) -> List[Dict]:
        """
        Get user's recent payments
        Uses idx_user_payments compound index (telegram_id + created_at)
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            limit: Number of recent payments
        
        Returns:
            List of payment documents
        """
        projection = {
            "_id": 0,
            "order_id": 1,
            "amount": 1,
            "status": 1,
            "created_at": 1,
            "type": 1
        }
        
        return await db.payments.find(
            {"telegram_id": telegram_id},
            projection
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    
    @staticmethod
    async def count_user_templates_fast(db, telegram_id: int) -> int:
        """
        Fast count of user templates using index
        Uses idx_user_templates index
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
        
        Returns:
            Count of templates
        """
        return await db.templates.count_documents(
            {"telegram_id": telegram_id}
        )
    
    
    @staticmethod
    async def get_orders_by_status(
        db,
        payment_status: Optional[str] = None,
        shipping_status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get orders filtered by status (admin function)
        Uses idx_payment_status, idx_shipping_status indexes
        
        Args:
            db: Database instance
            payment_status: Filter by payment status
            shipping_status: Filter by shipping status
            limit: Maximum orders to return
        
        Returns:
            List of order documents
        """
        query = {}
        if payment_status:
            query["payment_status"] = payment_status
        if shipping_status:
            query["shipping_status"] = shipping_status
        
        projection = {
            "_id": 0,
            "id": 1,
            "telegram_id": 1,
            "order_number": 1,
            "created_at": 1,
            "payment_status": 1,
            "shipping_status": 1,
            "amount": 1
        }
        
        return await db.orders.find(
            query,
            projection
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    
    @staticmethod
    async def bulk_update_order_status(
        db,
        order_ids: List[str],
        status_update: Dict
    ) -> int:
        """
        Bulk update order statuses
        
        Args:
            db: Database instance
            order_ids: List of order IDs to update
            status_update: Status fields to update
        
        Returns:
            Number of updated documents
        """
        result = await db.orders.update_many(
            {"id": {"$in": order_ids}},
            {"$set": {
                **status_update,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return result.modified_count


# Convenience singleton
optimized_queries = OptimizedQueries()


# Export commonly used functions
find_user_optimized = optimized_queries.find_user_by_telegram_id_optimized
get_user_orders = optimized_queries.get_user_orders_paginated
get_user_templates = optimized_queries.get_user_templates_optimized
find_pending_order = optimized_queries.find_pending_order_optimized
find_payment_by_invoice = optimized_queries.find_payment_by_invoice_optimized
count_templates_fast = optimized_queries.count_user_templates_fast


__all__ = [
    'OptimizedQueries',
    'optimized_queries',
    'find_user_optimized',
    'get_user_orders',
    'get_user_templates',
    'find_pending_order',
    'find_payment_by_invoice',
    'count_templates_fast'
]
