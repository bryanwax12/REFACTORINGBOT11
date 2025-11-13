"""
Session Manager for Telegram Bot
MongoDB-optimized with atomic operations and TTL index
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SessionManager:
    """
    MongoDB-оптимизированный Session Manager
    
    Ключевые улучшения:
    - TTL индекс для автоматической очистки
    - find_one_and_update для атомарных операций
    - $set для частичных обновлений без race conditions
    """
    
    def __init__(self, db):
        self.db = db
        self.sessions = db['user_sessions']
        self.completed_labels = db['completed_labels']
        
        # Create indexes for performance
        import asyncio
        asyncio.create_task(self._create_indexes())
    
    async def _create_indexes(self):
        """Create MongoDB indexes including TTL"""
        try:
            # Unique index on user_id
            await self.sessions.create_index("user_id", unique=True)
            
            # TTL index: автоматически удаляет документы старше 15 минут
            await self.sessions.create_index(
                "timestamp", 
                expireAfterSeconds=900  # 15 минут = 900 секунд
            )
            logger.info("✅ Session indexes created (including TTL)")
            
            # Indexes for completed labels
            await self.completed_labels.create_index("user_id")
            await self.completed_labels.create_index("created_at")
            
        except Exception as e:
            logger.error(f"Error creating session indexes: {e}")
    
    async def get_or_create_session(self, user_id: int, initial_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Атомарно получить существующую сессию или создать новую
        
        Использует find_one_and_update с upsert=True
        
        Args:
            user_id: ID пользователя
            initial_data: Начальные данные (используется только при создании)
        
        Returns:
            dict: Сессия (существующая или новая)
        """
        try:
            # Атомарная операция: найти и обновить timestamp ИЛИ создать новую
            session = await self.sessions.find_one_and_update(
                {"user_id": user_id},  # Фильтр
                {
                    "$set": {
                        "timestamp": datetime.now(timezone.utc)  # Обновить timestamp
                    },
                    "$setOnInsert": {  # Только при создании нового документа
                        "user_id": user_id,
                        "current_step": "START",
                        "temp_data": initial_data or {},
                        "created_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True,  # Создать если не существует
                return_document=True  # Вернуть документ ПОСЛЕ обновления
            )
            
            if session:
                logger.info(f"📖 Session loaded/created for user {user_id}: step {session.get('current_step')}")
            
            return session
            
        except Exception as e:
            logger.error(f"Error getting/creating session: {e}")
            return None
    
    async def update_session_atomic(self, 
                                   user_id: int, 
                                   step: str = None, 
                                   data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Атомарное обновление сессии без race conditions
        
        Использует $set для обновления полей напрямую в MongoDB
        
        Args:
            user_id: ID пользователя
            step: Новый шаг (опционально)
            data: Данные для добавления в temp_data (опционально)
        
        Returns:
            dict: Обновленная сессия или None
        """
        try:
            update_ops = {
                "$set": {
                    "timestamp": datetime.now(timezone.utc)
                }
            }
            
            # Обновить current_step
            if step:
                update_ops["$set"]["current_step"] = step
            
            # Обновить поля в temp_data (атомарно!)
            if data:
                for key, value in data.items():
                    update_ops["$set"][f"temp_data.{key}"] = value
            
            # Атомарная операция: обновить и вернуть результат
            session = await self.sessions.find_one_and_update(
                {"user_id": user_id},
                update_ops,
                return_document=True  # Вернуть ПОСЛЕ обновления
            )
            
            if session:
                logger.info(f"💾 Session updated atomically for user {user_id}: step={step}, data_keys={list(data.keys()) if data else []}")
            else:
                logger.warning(f"⚠️ Session not found for user {user_id} during update")
            
            return session
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return None
    
    async def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить сессию (read-only)
        
        Returns:
            dict: Сессия или None
        """
        try:
            session = await self.sessions.find_one({"user_id": user_id}, {"_id": 0})
            return session
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    async def clear_session(self, user_id: int) -> bool:
        """Удалить сессию пользователя"""
        try:
            result = await self.sessions.delete_one({"user_id": user_id})
            logger.info(f"🗑️ Session cleared for user {user_id}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False
    
    async def save_completed_label(self, user_id: int, label_data: Dict[str, Any]) -> bool:
        """
        Сохранить готовый лейбл и удалить сессию
        
        Использует транзакции если Replica Set, иначе fallback на последовательные операции
        
        Args:
            user_id: ID пользователя
            label_data: Данные лейбла
        
        Returns:
            bool: True если успешно
        """
        try:
            label_record = {
                "user_id": user_id,
                "label_data": label_data,
                "created_at": datetime.now(timezone.utc)
            }
            
            # Попытка использовать транзакции (работает только с Replica Set)
            try:
                async with await self.db.client.start_session() as session:
                    async with session.start_transaction():
                        # 1. Сохранить лейбл
                        await self.completed_labels.insert_one(label_record, session=session)
                        
                        # 2. Удалить сессию
                        await self.sessions.delete_one({"user_id": user_id}, session=session)
                
                logger.info(f"✅ Label saved and session cleared with TRANSACTION for user {user_id}")
                return True
                
            except Exception as tx_error:
                # Fallback для Standalone mode (нет Replica Set)
                if "Transaction numbers are only allowed on a replica set" in str(tx_error) or \
                   "Standalone mode" in str(tx_error):
                    
                    logger.warning(f"⚠️ Transactions not supported (Standalone mode) - using fallback for user {user_id}")
                    
                    # Fallback: Последовательные операции (не атомарные, но лучше чем ничего)
                    # 1. Сохранить лейбл
                    await self.completed_labels.insert_one(label_record)
                    
                    # 2. Удалить сессию
                    await self.sessions.delete_one({"user_id": user_id})
                    
                    logger.info(f"✅ Label saved and session cleared with FALLBACK for user {user_id}")
                    return True
                else:
                    # Другая ошибка - пробросить
                    raise
            
        except Exception as e:
            logger.error(f"Error saving completed label: {e}")
            return False
    
    async def get_user_labels(self, user_id: int, limit: int = 10) -> list:
        """Получить список лейблов пользователя"""
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
        Откатить сессию к предыдущему шагу при ошибке
        
        Returns:
            str: Предыдущий шаг
        """
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
            "CARRIER_SELECTION": "CONFIRM_DATA",
            "PAYMENT_METHOD": "CARRIER_SELECTION"
        }
        
        try:
            previous_step = step_map.get(current_step, "START")
            
            # Атомарное обновление с информацией об ошибке
            await self.update_session_atomic(
                user_id,
                step=previous_step,
                data={
                    'last_error': error_message or 'Unknown error',
                    'error_step': current_step,
                    'error_timestamp': datetime.now(timezone.utc).isoformat(),
                    'reverted_from': current_step,
                    'reverted_to': previous_step
                }
            )
            
            logger.warning(f"🔙 Session reverted for user {user_id}: {current_step} → {previous_step}")
            return previous_step
            
        except Exception as e:
            logger.error(f"Error reverting session: {e}")
            return None
    
    async def cleanup_old_sessions(self, timeout_minutes: int = 15) -> int:
        """
        Ручная очистка старых сессий (опционально, TTL делает это автоматически)
        
        Note: С TTL индексом эта функция избыточна, но оставлена для совместимости
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            result = await self.sessions.delete_many({
                "timestamp": {"$lt": cutoff_time}
            })
            
            if result.deleted_count > 0:
                logger.info(f"🧹 Manually cleaned up {result.deleted_count} old sessions")
            
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0
