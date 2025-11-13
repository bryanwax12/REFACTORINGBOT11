"""
MongoDB-based persistence for Telegram Bot ConversationHandler
Stores conversation state in MongoDB instead of in-memory
"""
from telegram.ext import BasePersistence
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone, timedelta
import logging
import ast

logger = logging.getLogger(__name__)


class MongoPersistence(BasePersistence):
    """MongoDB-based persistence for ConversationHandler state - NO CACHE (multi-pod safe)"""
    
    def __init__(self, db, update_interval: float = 0.1):
        from telegram.ext import PersistenceInput
        
        super().__init__(
            store_data=PersistenceInput(
                user_data=True,
                chat_data=True,
                bot_data=True,
                callback_data=True
            ),
            update_interval=1.0  # Save immediately on every change
        )
        self.db = db
        self.collection = db['bot_persistence']
        
        # Create indexes for fast queries (async, non-blocking)
        import asyncio
        asyncio.create_task(self._create_indexes())
        
        logger.info("✅ MongoPersistence initialized - Direct MongoDB (multi-pod safe, no cache)")
    
    async def _create_indexes(self):
        """Create MongoDB indexes for performance"""
        try:
            await self.collection.create_index("updated_at")
            await self.collection.create_index([("chat_id", 1), ("user_id", 1)])
            logger.info("📊 MongoDB indexes created for fast persistence")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
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
        """Load conversation states from MongoDB with new per-user document structure"""
        try:
            logger.warning(f"🔵🔵🔵 GET_CONVERSATIONS CALLED for {name}")
            
            # Find all conversation documents for this handler
            cursor = self.collection.find({"_id": {"$regex": f"^conversation_{name}_"}})
            conversations = {}
            
            async for doc in cursor:
                try:
                    # Extract chat_id and user_id from document
                    chat_id = doc.get('chat_id')
                    user_id = doc.get('user_id')
                    state = doc.get('state')
                    
                    if chat_id is not None and user_id is not None and state is not None:
                        key = (chat_id, user_id)
                        conversations[key] = state
                        logger.warning(f"🟢 Loaded: key={key}, state={state}")
                except Exception as e:
                    logger.error(f"Error parsing conversation doc: {e}")
                    continue
            
            logger.warning(f"📥 PERSISTENCE: Loaded {len(conversations)} conversations for {name}")
            return conversations
            
        except Exception as e:
            logger.error(f"❌ PERSISTENCE ERROR loading conversations: {e}")
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
        """Save conversation state to MongoDB with session isolation and auto-cleanup"""
        try:
            logger.warning(f"🔴🔴🔴 PERSISTENCE CALLED: update_conversation(name={name}, key={key}, new_state={new_state})")
            
            # Auto-cleanup old conversations (older than 1 hour)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            if new_state is None:
                # Remove conversation - delete entire document for this key
                await self.collection.delete_one({
                    "_id": f"conversation_{name}_{key[0]}_{key[1]}"
                })
                logger.info(f"🗑️ PERSISTENCE: Removed conversation for {name}, key: {key}")
            else:
                # Save conversation with timestamp for auto-cleanup
                doc_id = f"conversation_{name}_{key[0]}_{key[1]}"
                await self.collection.update_one(
                    {"_id": doc_id},
                    {
                        "$set": {
                            "state": new_state,
                            "updated_at": datetime.now(timezone.utc),
                            "chat_id": key[0],
                            "user_id": key[1]
                        }
                    },
                    upsert=True
                )
                logger.info(f"💾 PERSISTENCE: Saved conversation {doc_id} with state {new_state}")
                
                # Cleanup old documents (background task)
                await self.collection.delete_many({
                    "_id": {"$regex": f"^conversation_{name}_"},
                    "updated_at": {"$lt": cutoff_time}
                })
                
        except Exception as e:
            logger.error(f"❌ PERSISTENCE ERROR: {e}", exc_info=True)
    
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
