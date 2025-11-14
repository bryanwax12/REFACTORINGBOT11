"""
User Admin Service
Handles all user management operations for admin
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class UserAdminService:
    """Service for managing users from admin panel"""
    
    @staticmethod
    async def get_all_users(
        db,
        limit: int = 100,
        skip: int = 0,
        blocked_only: bool = False
    ) -> List[Dict]:
        """
        Get all users with pagination
        
        Args:
            db: Database instance
            limit: Maximum users to return
            skip: Number of users to skip
            blocked_only: Filter blocked users only
        
        Returns:
            List of user documents
        """
        query = {}
        if blocked_only:
            query["blocked"] = True
        
        projection = {
            "_id": 0,
            "id": 1,
            "telegram_id": 1,
            "balance": 1,
            "discount": 1,
            "blocked": 1,
            "is_admin": 1,
            "created_at": 1
        }
        
        users = await db.users.find(query, projection).skip(skip).limit(limit).to_list(limit)
        return users
    
    
    @staticmethod
    async def get_user_by_telegram_id(
        db,
        telegram_id: int,
        find_user_func
    ) -> Optional[Dict]:
        """
        Get user by telegram ID
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            find_user_func: Function to find user
        
        Returns:
            User document or None
        """
        return await find_user_func(telegram_id)
    
    
    @staticmethod
    async def block_user(
        db,
        telegram_id: int,
        bot_instance,
        send_notification: bool = True
    ) -> Tuple[bool, str]:
        """
        Block a user from using the bot
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            bot_instance: Telegram bot instance
            send_notification: Whether to notify user
        
        Returns:
            Tuple of (success, message)
        """
        try:
            result = await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {
                    "blocked": True,
                    "blocked_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            if result.modified_count > 0:
                # Send notification if enabled
                if send_notification and bot_instance:
                    try:
                        from handlers.common_handlers import safe_telegram_call
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=telegram_id,
                            text="⛔️ *Вы были заблокированы администратором.*\n\nДоступ к боту ограничен.",
                            parse_mode='Markdown'
                        ))
                    except Exception as e:
                        logger.error(f"Failed to send block notification: {e}")
                
                logger.info(f"User {telegram_id} blocked successfully")
                return True, "User blocked successfully"
            else:
                return False, "User already blocked or not found"
        
        except Exception as e:
            logger.error(f"Error blocking user {telegram_id}: {e}")
            return False, f"Error: {str(e)}"
    
    
    @staticmethod
    async def unblock_user(
        db,
        telegram_id: int,
        bot_instance,
        send_notification: bool = True
    ) -> Tuple[bool, str]:
        """
        Unblock a user to allow bot usage
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            bot_instance: Telegram bot instance
            send_notification: Whether to notify user
        
        Returns:
            Tuple of (success, message)
        """
        try:
            result = await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {
                    "blocked": False,
                    "unblocked_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            if result.modified_count > 0:
                # Send notification if enabled
                if send_notification and bot_instance:
                    try:
                        from handlers.common_handlers import safe_telegram_call
                        await safe_telegram_call(bot_instance.send_message(
                            chat_id=telegram_id,
                            text="✅ *Вы были разблокированы!*\n\nТеперь вы можете снова использовать бот.",
                            parse_mode='Markdown'
                        ))
                    except Exception as e:
                        logger.error(f"Failed to send unblock notification: {e}")
                
                logger.info(f"User {telegram_id} unblocked successfully")
                return True, "User unblocked successfully"
            else:
                return False, "User already unblocked or not found"
        
        except Exception as e:
            logger.error(f"Error unblocking user {telegram_id}: {e}")
            return False, f"Error: {str(e)}"
    
    
    @staticmethod
    async def update_user_balance(
        db,
        telegram_id: int,
        amount: float,
        operation: str = "add"  # add or set
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Update user balance
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            amount: Amount to add or set
            operation: "add" to add amount, "set" to set amount
        
        Returns:
            Tuple of (success, new_balance, error)
        """
        try:
            if operation == "add":
                result = await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {"$inc": {"balance": amount}}
                )
            else:  # set
                result = await db.users.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {"balance": amount}}
                )
            
            if result.modified_count > 0:
                # Get new balance
                user = await db.users.find_one({"telegram_id": telegram_id}, {"balance": 1})
                new_balance = user.get("balance", 0)
                return True, new_balance, None
            else:
                return False, 0, "User not found"
        
        except Exception as e:
            logger.error(f"Error updating balance for {telegram_id}: {e}")
            return False, 0, str(e)
    
    
    @staticmethod
    async def update_user_discount(
        db,
        telegram_id: int,
        discount: float
    ) -> Tuple[bool, str]:
        """
        Update user discount percentage
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
            discount: Discount percentage (0-100)
        
        Returns:
            Tuple of (success, message)
        """
        try:
            if discount < 0 or discount > 100:
                return False, "Discount must be between 0 and 100"
            
            result = await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {"discount": discount}}
            )
            
            if result.modified_count > 0:
                return True, f"Discount set to {discount}%"
            else:
                return False, "User not found"
        
        except Exception as e:
            logger.error(f"Error updating discount for {telegram_id}: {e}")
            return False, str(e)
    
    
    @staticmethod
    async def get_user_stats(db, telegram_id: int) -> Dict:
        """
        Get statistics for a specific user
        
        Args:
            db: Database instance
            telegram_id: Telegram user ID
        
        Returns:
            User statistics
        """
        try:
            # Get user
            user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
            if not user:
                return {"error": "User not found"}
            
            # Get orders count
            orders_count = await db.orders.count_documents({"telegram_id": telegram_id})
            
            # Get total spent
            pipeline = [
                {"$match": {"telegram_id": telegram_id, "payment_status": "paid"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            spent_result = await db.orders.aggregate(pipeline).to_list(1)
            total_spent = spent_result[0]["total"] if spent_result else 0
            
            # Get templates count
            templates_count = await db.templates.count_documents({"telegram_id": telegram_id})
            
            return {
                "user": user,
                "statistics": {
                    "total_orders": orders_count,
                    "total_spent": round(total_spent, 2),
                    "templates_count": templates_count,
                    "current_balance": user.get("balance", 0),
                    "discount": user.get("discount", 0)
                }
            }
        
        except Exception as e:
            logger.error(f"Error getting user stats for {telegram_id}: {e}")
            return {"error": str(e)}


# Singleton instance
user_admin_service = UserAdminService()
