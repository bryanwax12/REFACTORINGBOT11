"""
MongoDB-based persistence for Telegram Bot ConversationHandler
Stores conversation state in MongoDB instead of in-memory
"""
from telegram.ext import BasePersistence
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class MongoPersistence(BasePersistence):
    """MongoDB-based persistence for ConversationHandler state with in-memory caching"""
    
    def __init__(self, db, update_interval: float = 60):
        super().__init__(
            store_data=None,  # Store all data
            update_interval=update_interval
        )
        self.db = db
        self.collection = db['bot_persistence']
        
        # In-memory cache for fast access
        self._conversations_cache = {}
        self._user_data_cache = {}
        self._chat_data_cache = {}
        
        logger.info("✅ MongoPersistence initialized with in-memory caching")
    
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
        """Load conversation state from cache or MongoDB"""
        try:
            # Check cache first (instant!)
            if name in self._conversations_cache:
                logger.debug(f"⚡ Cache hit for {name}")
                return self._conversations_cache[name]
            
            # Load from MongoDB
            doc = await self.collection.find_one({"_id": f"conversation_{name}"})
            if doc and 'data' in doc:
                # Convert string keys back to tuples
                conversations = {}
                for key_str, state in doc['data'].items():
                    # Parse string back to tuple: "(123, 456)" -> (123, 456)
                    key = eval(key_str)  # Safe here as we control the format
                    conversations[key] = state
                
                # Cache it
                self._conversations_cache[name] = conversations
                logger.info(f"📥 Loaded & cached conversation state for {name}: {conversations}")
                return conversations
            
            # Empty state
            self._conversations_cache[name] = {}
            logger.info(f"📭 No conversation state found for {name}")
            return {}
        except Exception as e:
            logger.error(f"Error loading conversations for {name}: {e}")
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
        """Save conversation state to MongoDB"""
        try:
            conversations = await self.get_conversations(name)
            
            # Convert key tuple to string for MongoDB storage
            key_str = str(key)
            
            if new_state is None:
                # Remove conversation
                if key_str in conversations:
                    del conversations[key_str]
                    logger.info(f"🗑️ Removed conversation state for {name}, key: {key_str}")
            else:
                # Update conversation
                conversations[key_str] = new_state
                logger.info(f"💾 Saved conversation state for {name}, key: {key_str}, state: {new_state}")
            
            await self.collection.update_one(
                {"_id": f"conversation_{name}"},
                {"$set": {"data": conversations, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving conversation for {name}: {e}")
    
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
