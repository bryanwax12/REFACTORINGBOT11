"""
Session Repository
Репозиторий для работы с пользовательскими сессиями
"""
from typing import Dict, List, Optional
from repositories.base_repository import BaseRepository
from datetime import datetime, timezone, timedelta
import logging
from asyncio import Lock

logger = logging.getLogger(__name__)


class SessionRepository(BaseRepository):
    """Репозиторий для коллекции user_sessions"""
    
    def __init__(self, db):
        super().__init__(db.user_sessions, "user_sessions")
        # CRITICAL: Per-user locks to prevent race conditions during fast input
        self.user_locks: Dict[int, Lock] = {}
    
    async def get_or_create_session(
        self,
        user_id: int,
        session_type: str = "conversation",
        initial_data: Optional[Dict] = None
    ) -> Dict:
        """
        Получить или создать сессию для пользователя
        
        Args:
            user_id: Telegram ID пользователя
            session_type: Тип сессии (conversation, order, payment)
            initial_data: Начальные данные сессии
            
        Returns:
            Документ сессии
        """
        # Попытаться найти активную сессию
        session = await self.find_one({
            "user_id": user_id,
            "session_type": session_type,
            "is_active": True
        })
        
        if session:
            logger.debug(f"✅ Found active session for user {user_id}, type {session_type}")
            return session
        
        # Создать новую сессию
        session_id = f"{user_id}_{session_type}_{int(datetime.now(timezone.utc).timestamp())}"
        session_data = {
            "user_id": user_id,
            "session_id": session_id,
            "session_type": session_type,
            "is_active": True,
            "current_step": "START",
            "session_data": initial_data or {},
            "temp_data": {},
            "started_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Use update_one with upsert to avoid duplicate key errors
        await self.collection.update_one(
            {"user_id": user_id, "session_type": session_type},
            {"$set": session_data},
            upsert=True
        )
        
        logger.info(f"✅ Created/updated session for user {user_id}, type {session_type}")
        
        return session_data
    
    async def get_session(
        self,
        user_id: int,
        session_type: str = "conversation"
    ) -> Optional[Dict]:
        """
        Получить активную сессию пользователя
        
        Args:
            user_id: Telegram ID пользователя
            session_type: Тип сессии
            
        Returns:
            Документ сессии или None
        """
        return await self.find_one({
            "user_id": user_id,
            "session_type": session_type,
            "is_active": True
        })
    
    async def update_session_data(
        self,
        user_id: int,
        data: Dict,
        session_type: str = "conversation",
        merge: bool = True
    ) -> bool:
        """
        Обновить данные сессии
        
        Args:
            user_id: Telegram ID пользователя
            data: Данные для обновления
            session_type: Тип сессии
            merge: True - объединить с существующими, False - заменить
            
        Returns:
            True если обновлено
        """
        # CRITICAL: Get or create lock for this user to prevent race conditions
        lock = self.user_locks.setdefault(user_id, Lock())
        
        async with lock:  # One user = one write at a time
            if merge:
                # Объединить с существующими данными
                update_query = {
                    "$set": {
                        f"session_data.{key}": value
                        for key, value in data.items()
                    }
                }
            else:
                # Заменить полностью
                update_query = {"$set": {"session_data": data}}
            
            return await self.update_one(
                {
                    "user_id": user_id,
                    "session_type": session_type,
                    "is_active": True
                },
                update_query
            )
    
    async def update_temp_data(
        self,
        user_id: int,
        data: Dict,
        session_type: str = "conversation"
    ) -> bool:
        """
        Обновить временные данные сессии
        
        Args:
            user_id: Telegram ID пользователя
            data: Временные данные
            session_type: Тип сессии
            
        Returns:
            True если обновлено
        """
        # CRITICAL: Lock to prevent race conditions
        lock = self.user_locks.setdefault(user_id, Lock())
        
        async with lock:
            update_query = {
                "$set": {
                    f"temp_data.{key}": value
                    for key, value in data.items()
                }
            }
            
            return await self.update_one(
                {
                    "user_id": user_id,
                    "session_type": session_type,
                    "is_active": True
                },
                update_query
            )
    
    async def update_step(
        self,
        user_id: int,
        new_step: str,
        session_type: str = "conversation"
    ) -> bool:
        """
        Обновить текущий шаг сессии
        
        Args:
            user_id: Telegram ID пользователя
            new_step: Новый шаг
            session_type: Тип сессии
            
        Returns:
            True если обновлено
        """
        return await self.update_one(
            {
                "user_id": user_id,
                "session_type": session_type,
                "is_active": True
            },
            {"$set": {"current_step": new_step}}
        )
    
    async def clear_session(
        self,
        user_id: int,
        session_type: Optional[str] = None
    ) -> bool:
        """
        Очистить сессию пользователя
        
        Args:
            user_id: Telegram ID пользователя
            session_type: Тип сессии (если None, очистить все)
            
        Returns:
            True если очищено
        """
        filter_query = {"user_id": user_id, "is_active": True}
        
        if session_type:
            filter_query["session_type"] = session_type
        
        return await self.update_one(
            filter_query,
            {
                "$set": {
                    "is_active": False,
                    "ended_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    async def get_session_data(
        self,
        user_id: int,
        session_type: str = "conversation"
    ) -> Dict:
        """
        Получить только данные сессии
        
        Args:
            user_id: Telegram ID пользователя
            session_type: Тип сессии
            
        Returns:
            Словарь с данными сессии или пустой словарь
        """
        session = await self.get_session(user_id, session_type)
        
        if session:
            return session.get('session_data', {})
        
        return {}
    
    async def get_temp_data(
        self,
        user_id: int,
        session_type: str = "conversation"
    ) -> Dict:
        """
        Получить только временные данные сессии
        
        Args:
            user_id: Telegram ID пользователя
            session_type: Тип сессии
            
        Returns:
            Словарь с временными данными или пустой словарь
        """
        session = await self.get_session(user_id, session_type)
        
        if session:
            return session.get('temp_data', {})
        
        return {}
    
    async def get_current_step(
        self,
        user_id: int,
        session_type: str = "conversation"
    ) -> Optional[str]:
        """
        Получить текущий шаг сессии
        
        Args:
            user_id: Telegram ID пользователя
            session_type: Тип сессии
            
        Returns:
            Текущий шаг или None
        """
        session = await self.get_session(user_id, session_type)
        
        if session:
            return session.get('current_step')
        
        return None
    
    async def get_active_sessions(
        self,
        user_id: int
    ) -> List[Dict]:
        """
        Получить все активные сессии пользователя
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Список активных сессий
        """
        return await self.find_many({
            "user_id": user_id,
            "is_active": True
        })
    
    async def delete_old_sessions(self, days: int = 7) -> int:
        """
        Удалить старые неактивные сессии
        
        Args:
            days: Старше N дней
            
        Returns:
            Количество удаленных сессий
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        return await self.delete_many({
            "is_active": False,
            "ended_at": {"$lt": cutoff_time.isoformat()}
        })
    
    async def get_session_stats(self) -> Dict:
        """
        Получить статистику по сессиям
        
        Returns:
            Статистика
        """
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_sessions": {"$sum": 1},
                    "active_sessions": {
                        "$sum": {"$cond": ["$is_active", 1, 0]}
                    },
                    "inactive_sessions": {
                        "$sum": {"$cond": [{"$not": "$is_active"}, 1, 0]}
                    },
                    "by_type": {
                        "$push": "$session_type"
                    }
                }
            }
        ]
        
        results = await self.aggregate(pipeline)
        
        if results:
            stats = results[0]
            stats.pop('_id', None)
            
            # Подсчитать по типам
            type_counts = {}
            for session_type in stats.get('by_type', []):
                type_counts[session_type] = type_counts.get(session_type, 0) + 1
            
            stats['by_type'] = type_counts
            
            return stats
        
        return {
            "total_sessions": 0,
            "active_sessions": 0,
            "inactive_sessions": 0,
            "by_type": {}
        }


"""
ИСПОЛЬЗОВАНИЕ:
=============

1. В handlers:
   ```python
   from repositories import get_session_repo
   
   async def my_handler(update, context):
       session_repo = get_session_repo()
       user_id = update.effective_user.id
       
       # Получить или создать сессию
       session = await session_repo.get_or_create_session(user_id, "order")
       
       # Обновить данные
       await session_repo.update_session_data(
           user_id,
           {"product_id": "ABC123", "quantity": 2}
       )
       
       # Обновить шаг
       await session_repo.update_step(user_id, "CONFIRM")
       
       # Получить данные
       data = await session_repo.get_session_data(user_id)
       
       # Очистить сессию
       await session_repo.clear_session(user_id)
   ```

2. Интеграция с существующим session_manager:
   ```python
   # Постепенная миграция
   # Старый код:
   session = await session_manager.get_or_create_session(user_id)
   
   # Новый код:
   session = await get_session_repo().get_or_create_session(user_id)
   ```

ПРЕИМУЩЕСТВА:
=============

- ✅ Централизованное управление сессиями
- ✅ Типизированные методы
- ✅ Логирование всех операций
- ✅ Автоматические timestamps
- ✅ Статистика сессий
- ✅ Cleanup старых сессий
- ✅ Легко тестировать
"""
