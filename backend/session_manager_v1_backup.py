"""
Session Manager for Telegram Bot
Manages user sessions in MongoDB with step tracking and data persistence
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions for order creation process"""
    
    def __init__(self, db):
        self.db = db
        self.sessions = db['user_sessions']
        self.completed_labels = db['completed_labels']
        
        # Create indexes for performance
        import asyncio
        asyncio.create_task(self._create_indexes())
    
    async def _create_indexes(self):
        """Create MongoDB indexes for fast queries"""
        try:
            await self.sessions.create_index("user_id", unique=True)
            await self.sessions.create_index("timestamp")
            await self.completed_labels.create_index("user_id")
            await self.completed_labels.create_index("created_at")
            logger.info("✅ Session indexes created")
        except Exception as e:
            logger.error(f"Error creating session indexes: {e}")
    
    async def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get active session for user"""
        try:
            session = await self.sessions.find_one({"user_id": user_id}, {"_id": 0})
            if session:
                logger.info(f"📖 Session loaded for user {user_id}: step {session.get('current_step')}")
            return session
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    async def create_session(self, user_id: int, initial_data: Dict[str, Any] = None) -> bool:
        """Create new session for user"""
        try:
            session = {
                "user_id": user_id,
                "current_step": "START",
                "temp_data": initial_data or {},
                "timestamp": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc)
            }
            
            # Upsert: create or replace existing session
            await self.sessions.update_one(
                {"user_id": user_id},
                {"$set": session},
                upsert=True
            )
            
            logger.info(f"🆕 New session created for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return False
    
    async def update_session(self, user_id: int, step: str = None, data: Dict[str, Any] = None) -> bool:
        """Update session step and/or data"""
        try:
            update_fields = {
                "timestamp": datetime.now(timezone.utc)
            }
            
            if step:
                update_fields["current_step"] = step
            
            if data:
                # Merge new data with existing temp_data
                session = await self.get_session(user_id)
                if session:
                    existing_data = session.get("temp_data", {})
                    existing_data.update(data)
                    update_fields["temp_data"] = existing_data
                else:
                    update_fields["temp_data"] = data
            
            result = await self.sessions.update_one(
                {"user_id": user_id},
                {"$set": update_fields}
            )
            
            logger.info(f"💾 Session updated for user {user_id}: step={step}, data_keys={list(data.keys()) if data else []}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    async def clear_session(self, user_id: int) -> bool:
        """Clear/delete user session"""
        try:
            result = await self.sessions.delete_one({"user_id": user_id})
            logger.info(f"🗑️ Session cleared for user {user_id}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False
    
    async def save_completed_label(self, user_id: int, label_data: Dict[str, Any]) -> bool:
        """Save completed label to permanent storage"""
        try:
            label_record = {
                "user_id": user_id,
                "label_data": label_data,
                "created_at": datetime.now(timezone.utc)
            }
            
            await self.completed_labels.insert_one(label_record)
            logger.info(f"✅ Label saved for user {user_id}")
            
            # Clear session after saving label
            await self.clear_session(user_id)
            return True
        except Exception as e:
            logger.error(f"Error saving completed label: {e}")
            return False
    
    async def cleanup_old_sessions(self, timeout_minutes: int = 15) -> int:
        """Remove sessions older than timeout_minutes"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            result = await self.sessions.delete_many({
                "timestamp": {"$lt": cutoff_time}
            })
            
            if result.deleted_count > 0:
                logger.info(f"🧹 Cleaned up {result.deleted_count} old sessions")
            
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0
    
    async def get_user_labels(self, user_id: int, limit: int = 10) -> list:
        """Get user's completed labels"""
        try:
            cursor = self.completed_labels.find(
                {"user_id": user_id},
                {"_id": 0}
            ).sort("created_at", -1).limit(limit)
            
            labels = await cursor.to_list(length=limit)
            return labels
        except Exception as e:
            logger.error(f"Error getting user labels: {e}")
            return []
    
    async def revert_to_previous_step(self, user_id: int, current_step: str, error_message: str = None) -> Optional[str]:
        """
        Revert session to previous step when error occurs
        Returns the previous step to return to
        """
        # Step progression mapping (current_step -> previous_step)
        step_map = {
            "FROM_ADDRESS": "FROM_NAME",
            "FROM_ADDRESS2": "FROM_ADDRESS",
            "FROM_CITY": "FROM_ADDRESS2",
            "FROM_STATE": "FROM_CITY",
            "FROM_ZIP": "FROM_STATE",
            "FROM_PHONE": "FROM_ZIP",
            "TO_NAME": "FROM_PHONE",
            "TO_ADDRESS": "TO_NAME",
            "TO_ADDRESS2": "TO_ADDRESS",
            "TO_CITY": "TO_ADDRESS2",
            "TO_STATE": "TO_CITY",
            "TO_ZIP": "TO_STATE",
            "TO_PHONE": "TO_ZIP",
            "PARCEL_WEIGHT": "TO_PHONE",
            "PARCEL_LENGTH": "PARCEL_WEIGHT",
            "PARCEL_WIDTH": "PARCEL_LENGTH",
            "PARCEL_HEIGHT": "PARCEL_WIDTH",
            "CONFIRM_DATA": "PARCEL_HEIGHT",
            "CARRIER_SELECTION": "CONFIRM_DATA",  # After rates fetched
            "PAYMENT_METHOD": "CARRIER_SELECTION"
        }
        
        try:
            previous_step = step_map.get(current_step, "START")
            
            # Save error information in session
            error_data = {
                'last_error': error_message or 'Unknown error',
                'error_step': current_step,
                'error_timestamp': datetime.now(timezone.utc).isoformat(),
                'reverted_from': current_step,
                'reverted_to': previous_step
            }
            
            # Update session to previous step
            await self.update_session(user_id, step=previous_step, data=error_data)
            
            logger.warning(f"🔙 Session reverted for user {user_id}: {current_step} → {previous_step} (error: {error_message})")
            return previous_step
            
        except Exception as e:
            logger.error(f"Error reverting session: {e}")
            return None
