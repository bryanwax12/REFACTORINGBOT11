"""
MongoDB-based persistence for Telegram Bot ConversationHandler
Stores conversation state in MongoDB instead of in-memory
"""
from telegram.ext import BasePersistence
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
import logging
import ast

logger = logging.getLogger(__name__)


class MongoPersistence(BasePersistence):
    """MongoDB-based persistence for ConversationHandler state - NO CACHE (multi-pod safe)"""
    
    def __init__(self, db, update_interval: float = 0.1):
        super().__init__(
            store_data=None,  # Store all data
            update_interval=update_interval  # Update every 0.1s for fast persistence
        )
        self.db = db
        self.collection = db['bot_persistence']
        
        logger.info("✅ MongoPersistence initialized - Direct MongoDB (multi-pod safe, no cache)")
    
    async def get_user_data(self) -> Dict[int, Dict]:
        """Load user_data from MongoDB"""
        try:
            doc = await self.collection.find_one({"_id": "user_data"})
            if doc and 'data' in doc:
                return doc['data']
            return {}
        except Exception as e:
            logger.error(f"Error loading user_data: {e}")
            return {}
    
    async def get_chat_data(self) -> Dict[int, Dict]:
        """Load chat_data from MongoDB"""
        try:
            doc = await self.collection.find_one({"_id": "chat_data"})
            if doc and 'data' in doc:
                return doc['data']
            return {}
        except Exception as e:
            logger.error(f"Error loading chat_data: {e}")
            return {}
    
    async def get_bot_data(self) -> Dict:
        """Load bot_data from MongoDB"""
        return {}
    
    async def get_callback_data(self) -> Optional[Tuple]:
        """Load callback_data from MongoDB"""
        return None
    
    async def get_conversations(self, name: str) -> Dict:
        """Load conversation state directly from MongoDB (no cache, multi-pod safe)"""
        try:
            # Always load from MongoDB for consistency across pods
            doc = await self.collection.find_one({"_id": f"conversation_{name}"})
            if doc and 'data' in doc:
                # Convert string keys back to tuples
                conversations = {}
                for key_str, state in doc['data'].items():
                    # Parse string back to tuple: "(123, 456)" -> (123, 456)
                    key = eval(key_str)  # Safe here as we control the format
                    conversations[key] = state
                
                logger.info(f"📥 PERSISTENCE: Loaded from MongoDB for {name}: {len(conversations)} entries, states: {conversations}")
                return conversations
            
            # Empty state
            logger.info(f"📭 PERSISTENCE: No conversation state in MongoDB for {name}, starting fresh")
            return {}
        except Exception as e:
            logger.error(f"❌ PERSISTENCE ERROR loading conversations for {name}: {e}")
            return {}
    
    async def update_user_data(self, user_id: int, data: Dict) -> None:
        """Save user_data to MongoDB"""
        try:
            all_user_data = await self.get_user_data()
            all_user_data[user_id] = data
            await self.collection.update_one(
                {"_id": "user_data"},
                {"$set": {"data": all_user_data, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )
            logger.debug(f"💾 Saved user_data for {user_id}")
        except Exception as e:
            logger.error(f"Error saving user_data for {user_id}: {e}")
    
    async def update_chat_data(self, chat_id: int, data: Dict) -> None:
        """Save chat_data to MongoDB"""
        try:
            all_chat_data = await self.get_chat_data()
            all_chat_data[chat_id] = data
            await self.collection.update_one(
                {"_id": "chat_data"},
                {"$set": {"data": all_chat_data, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )
            logger.debug(f"💾 Saved chat_data for {chat_id}")
        except Exception as e:
            logger.error(f"Error saving chat_data for {chat_id}: {e}")
    
    async def update_bot_data(self, data: Dict) -> None:
        """Save bot_data to MongoDB"""
        pass
    
    async def update_callback_data(self, data: Tuple) -> None:
        """Save callback_data to MongoDB"""
        pass
    
    async def update_conversation(self, name: str, key: Tuple, new_state: Optional[int]) -> None:
        """Save conversation state directly to MongoDB (no cache, multi-pod safe)"""
        try:
            # Load current conversations from MongoDB
            conversations = await self.get_conversations(name)
            
            if new_state is None:
                # Remove conversation
                if key in conversations:
                    del conversations[key]
                    logger.info(f"🗑️ PERSISTENCE: Removed conversation state for {name}, key: {key}")
            else:
                # Update conversation
                conversations[key] = new_state
                logger.info(f"💾 PERSISTENCE: Updating conversation - name: {name}, key: {key}, state: {new_state}")
            
            # Prepare for MongoDB (convert keys to strings)
            conversations_for_db = {str(k): v for k, v in conversations.items()}
            
            # Save to MongoDB IMMEDIATELY (blocking for consistency)
            await self.collection.update_one(
                {"_id": f"conversation_{name}"},
                {"$set": {"data": conversations_for_db, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )
            logger.info(f"💾 PERSISTENCE: Saved to MONGODB - name: {name}, entries: {len(conversations_for_db)}, all_states: {conversations_for_db}")
        except Exception as e:
            logger.error(f"❌ PERSISTENCE ERROR saving conversation for {name}: {e}")
    
    async def drop_user_data(self, user_id: int) -> None:
        """Delete user_data from MongoDB"""
        try:
            all_user_data = await self.get_user_data()
            if user_id in all_user_data:
                del all_user_data[user_id]
                await self.collection.update_one(
                    {"_id": "user_data"},
                    {"$set": {"data": all_user_data}},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Error dropping user_data for {user_id}: {e}")
    
    async def drop_chat_data(self, chat_id: int) -> None:
        """Delete chat_data from MongoDB"""
        try:
            all_chat_data = await self.get_chat_data()
            if chat_id in all_chat_data:
                del all_chat_data[chat_id]
                await self.collection.update_one(
                    {"_id": "chat_data"},
                    {"$set": {"data": all_chat_data}},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Error dropping chat_data for {chat_id}: {e}")
    
    async def refresh_user_data(self, user_id: int, user_data: Dict) -> None:
        """Refresh user_data (called by framework)"""
        pass
    
    async def refresh_chat_data(self, chat_id: int, chat_data: Dict) -> None:
        """Refresh chat_data (called by framework)"""
        pass
    
    async def refresh_bot_data(self, bot_data: Dict) -> None:
        """Refresh bot_data (called by framework)"""
        pass
    
    async def flush(self) -> None:
        """Flush all data to MongoDB"""
        logger.debug("💾 Flushing all data to MongoDB")
