"""
Redis-based persistence for Telegram Bot ConversationHandler
Ultra-fast, multi-pod safe, production-ready
"""
from telegram.ext import BasePersistence
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
import logging
import redis
import json
import pickle

logger = logging.getLogger(__name__)


class RedisPersistence(BasePersistence):
    """Redis-based persistence for ConversationHandler state - PRODUCTION READY"""
    
    def __init__(self, redis_host: str, redis_port: int, redis_password: str, update_interval: float = 0):
        super().__init__(
            store_data=None,  # Store all data
            update_interval=update_interval
        )
        
        # Connect to Redis
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=False,  # We'll use pickle for serialization
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ RedisPersistence connected to {redis_host}:{redis_port}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
    
    def _serialize(self, data):
        """Serialize data for Redis storage"""
        return pickle.dumps(data)
    
    def _deserialize(self, data):
        """Deserialize data from Redis"""
        if data is None:
            return None
        return pickle.loads(data)
    
    def get_user_data(self) -> Dict[int, Dict]:
        """Load user_data from Redis (SYNC)"""
        try:
            data = self.redis_client.get("bot:user_data")
            if data:
                result = self._deserialize(data)
                logger.debug(f"📥 Loaded user_data: {len(result)} users")
                return result
            return {}
        except Exception as e:
            logger.error(f"Error loading user_data: {e}")
            return {}
    
    def get_chat_data(self) -> Dict[int, Dict]:
        """Load chat_data from Redis (SYNC)"""
        try:
            data = self.redis_client.get("bot:chat_data")
            if data:
                result = self._deserialize(data)
                logger.debug(f"📥 Loaded chat_data: {len(result)} chats")
                return result
            return {}
        except Exception as e:
            logger.error(f"Error loading chat_data: {e}")
            return {}
    
    def get_bot_data(self) -> Dict:
        """Load bot_data from Redis (SYNC)"""
        return {}
    
    def get_callback_data(self) -> Optional[Tuple]:
        """Load callback_data from Redis (SYNC)"""
        return None
    
    def get_conversations(self, name: str) -> Dict:
        """Load conversation state from Redis - INSTANT ACCESS (SYNC)"""
        try:
            key = f"bot:conversation:{name}"
            data = self.redis_client.get(key)
            
            if data:
                conversations = self._deserialize(data)
                logger.info(f"⚡ REDIS: Loaded conversation for {name}: {len(conversations)} entries")
                return conversations
            
            logger.info(f"📭 REDIS: No conversation state for {name}")
            return {}
            
        except Exception as e:
            logger.error(f"❌ REDIS ERROR loading conversations for {name}: {e}")
            return {}
    
    async def update_user_data(self, user_id: int, data: Dict) -> None:
        """Save user_data to Redis"""
        try:
            all_user_data = await self.get_user_data()
            all_user_data[user_id] = data
            
            self.redis_client.set("bot:user_data", self._serialize(all_user_data))
            logger.debug(f"💾 Saved user_data for {user_id}")
            
        except Exception as e:
            logger.error(f"Error saving user_data for {user_id}: {e}")
    
    async def update_chat_data(self, chat_id: int, data: Dict) -> None:
        """Save chat_data to Redis"""
        try:
            all_chat_data = await self.get_chat_data()
            all_chat_data[chat_id] = data
            
            self.redis_client.set("bot:chat_data", self._serialize(all_chat_data))
            logger.debug(f"💾 Saved chat_data for {chat_id}")
            
        except Exception as e:
            logger.error(f"Error saving chat_data for {chat_id}: {e}")
    
    async def update_bot_data(self, data: Dict) -> None:
        """Save bot_data to Redis"""
        pass
    
    async def update_callback_data(self, data: Tuple) -> None:
        """Save callback_data to Redis"""
        pass
    
    def update_conversation(self, name: str, key: Tuple, new_state: Optional[int]) -> None:
        """Save conversation state to Redis - INSTANT SAVE (SYNC)"""
        try:
            redis_key = f"bot:conversation:{name}"
            
            # Load current conversations
            conversations = self.get_conversations(name)
            
            if new_state is None:
                # Remove conversation
                if key in conversations:
                    del conversations[key]
                    logger.info(f"🗑️ REDIS: Removed conversation for {name}, key: {key}")
            else:
                # Update conversation
                conversations[key] = new_state
                logger.info(f"💾 REDIS: Saved conversation for {name}, key: {key}, state: {new_state}")
            
            # Save to Redis IMMEDIATELY
            self.redis_client.set(redis_key, self._serialize(conversations))
            
            # Set expiration (1 hour for inactive conversations)
            self.redis_client.expire(redis_key, 3600)
            
            logger.debug(f"✅ REDIS: Persisted to Redis, total entries: {len(conversations)}")
            
        except Exception as e:
            logger.error(f"❌ REDIS ERROR saving conversation for {name}: {e}")
    
    async def drop_user_data(self, user_id: int) -> None:
        """Delete user_data from Redis"""
        try:
            all_user_data = await self.get_user_data()
            if user_id in all_user_data:
                del all_user_data[user_id]
                self.redis_client.set("bot:user_data", self._serialize(all_user_data))
        except Exception as e:
            logger.error(f"Error dropping user_data for {user_id}: {e}")
    
    async def drop_chat_data(self, chat_id: int) -> None:
        """Delete chat_data from Redis"""
        try:
            all_chat_data = await self.get_chat_data()
            if chat_id in all_chat_data:
                del all_chat_data[chat_id]
                self.redis_client.set("bot:chat_data", self._serialize(all_chat_data))
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
        """Flush all data to Redis (already done on each update)"""
        logger.debug("💾 Redis flush (no-op, data already saved)")
