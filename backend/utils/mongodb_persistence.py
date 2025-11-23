"""
MongoDB Persistence for ConversationHandler
Replaces PicklePersistence with MongoDB storage
"""
import logging
from typing import Dict, Optional
from telegram.ext import BasePersistence, PersistenceInput
from telegram.ext._utils.types import ConversationDict

logger = logging.getLogger(__name__)


class MongoDBPersistence(BasePersistence):
    """
    Minimal MongoDB persistence for ConversationHandler states only
    Does NOT persist user_data, chat_data, or bot_data (we use MongoDB sessions for that)
    """
    
    def __init__(self, db):
        super().__init__(
            store_data=PersistenceInput(
                user_data=False,  # We handle this via session_service
                chat_data=False,
                bot_data=False,
                callback_data=False
            ),
            update_interval=0  # Immediate writes
        )
        self.db = db
        self._conversations: Dict[str, Dict[tuple, object]] = {}
        logger.info("✅ MongoDBPersistence initialized (conversations only)")
    
    async def get_conversations(self, name: str) -> ConversationDict:
        """Restore conversation states from MongoDB"""
        try:
            # Load all active conversations for this handler
            sessions = await self.db.user_sessions.find(
                {"is_active": True},
                {"user_id": 1, "session_data.conversation_state": 1}
            ).to_list(1000)
            
            conversations = {}
            for session in sessions:
                user_id = session.get("user_id")
                state = session.get("session_data", {}).get("conversation_state")
                
                if user_id and state is not None:
                    # ConversationHandler uses (chat_id, user_id) as key
                    key = (user_id, user_id)  # For private chats, chat_id == user_id
                    conversations[key] = state
            
            logger.info(f"📥 Loaded {len(conversations)} conversations from MongoDB")
            return conversations
            
        except Exception as e:
            logger.error(f"❌ Failed to load conversations: {e}")
            return {}
    
    async def update_conversation(
        self, name: str, key: tuple, new_state: Optional[object]
    ) -> None:
        """Save conversation state to MongoDB"""
        try:
            chat_id, user_id = key
            
            if new_state is None:
                # Conversation ended - clear state
                await self.db.user_sessions.update_one(
                    {"user_id": user_id, "is_active": True},
                    {"$unset": {"session_data.conversation_state": ""}}
                )
                logger.info(f"🗑️ Cleared conversation for user {user_id}")
            else:
                # Save new state
                await self.db.user_sessions.update_one(
                    {"user_id": user_id, "is_active": True},
                    {"$set": {"session_data.conversation_state": new_state}}
                )
                logger.info(f"💾 Saved conversation state={new_state} for user {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to save conversation: {e}")
    
    # Required abstract methods (we don't use these):
    async def get_user_data(self) -> Dict: return {}
    async def get_chat_data(self) -> Dict: return {}
    async def get_bot_data(self) -> Dict: return {}
    async def get_callback_data(self) -> Optional[tuple]: return None
    async def update_user_data(self, user_id: int, data: Dict) -> None: pass
    async def update_chat_data(self, chat_id: int, data: Dict) -> None: pass
    async def update_bot_data(self, data: Dict) -> None: pass
    async def update_callback_data(self, data: tuple) -> None: pass
    async def drop_chat_data(self, chat_id: int) -> None: pass
    async def drop_user_data(self, user_id: int) -> None: pass
    async def refresh_user_data(self, user_id: int, user_data: Dict) -> None: pass
    async def refresh_chat_data(self, chat_id: int, chat_data: Dict) -> None: pass
    async def refresh_bot_data(self, bot_data: Dict) -> None: pass
    async def flush(self) -> None: pass
