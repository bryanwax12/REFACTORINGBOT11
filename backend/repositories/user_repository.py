"""
User Repository
Репозиторий для работы с пользователями
"""
from typing import Dict, List, Optional
from repositories.base_repository import BaseRepository
from utils.simple_cache import cached, cache, clear_user_cache
import logging

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Репозиторий для коллекции users"""
    
    def __init__(self, db):
        super().__init__(db.users, "users")
    
    @cached(ttl=30, key_prefix="user")
    async def find_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """
        Найти пользователя по Telegram ID (with 30s cache)
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Документ пользователя или None
        """
        return await self.find_one({"telegram_id": telegram_id})
    
    async def find_by_username(self, username: str) -> Optional[Dict]:
        """
        Найти пользователя по username
        
        Args:
            username: Telegram username
            
        Returns:
            Документ пользователя или None
        """
        return await self.find_one({"username": username})
    
    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        initial_balance: float = 0.0
    ) -> Dict:
        """
        Создать нового пользователя
        
        Args:
            telegram_id: Telegram ID
            username: Username
            first_name: Имя
            last_name: Фамилия
            initial_balance: Начальный баланс
            
        Returns:
            Созданный пользователь
        """
        user_doc = {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "balance": initial_balance,
            "is_admin": False,
            "is_blocked": False,
            "total_spent": 0.0,
            "orders_count": 0
        }
        
        return await self.insert_one(user_doc)
    
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict:
        """
        Получить или создать пользователя
        
        Args:
            telegram_id: Telegram ID
            username: Username
            first_name: Имя
            last_name: Фамилия
            
        Returns:
            Документ пользователя
        """
        # Попытаться найти
        user = await self.find_by_telegram_id(telegram_id)
        
        if user:
            # Обновить username/name если изменились
            updates = {}
            if username and user.get('username') != username:
                updates['username'] = username
            if first_name and user.get('first_name') != first_name:
                updates['first_name'] = first_name
            if last_name and user.get('last_name') != last_name:
                updates['last_name'] = last_name
            
            if updates:
                await self.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": updates}
                )
                user.update(updates)
            
            return user
        
        # Создать нового
        return await self.create_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
    
    async def update_balance(
        self,
        telegram_id: int,
        amount: float,
        operation: str = "add"
    ) -> bool:
        """
        Обновить баланс пользователя (атомарно)
        
        Args:
            telegram_id: Telegram ID
            amount: Сумма
            operation: "add" или "subtract"
            
        Returns:
            True если обновлено успешно
        """
        if operation == "subtract":
            amount = -abs(amount)
        else:
            amount = abs(amount)
        
        result = await self.update_one(
            {"telegram_id": telegram_id},
            {"$inc": {"balance": amount}}
        )
        
        return result
    
    async def get_balance(self, telegram_id: int) -> float:
        """
        Получить баланс пользователя
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            Баланс или 0.0
        """
        user = await self.find_one(
            {"telegram_id": telegram_id},
            projection={"balance": 1}
        )
        
        return user.get('balance', 0.0) if user else 0.0
    
    async def set_admin(self, telegram_id: int, is_admin: bool = True) -> bool:
        """
        Установить/снять admin статус
        
        Args:
            telegram_id: Telegram ID
            is_admin: True для админа
            
        Returns:
            True если обновлено
        """
        return await self.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"is_admin": is_admin}}
        )
    
    async def is_admin(self, telegram_id: int) -> bool:
        """
        Проверить является ли пользователь админом
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            True если админ
        """
        user = await self.find_one(
            {"telegram_id": telegram_id},
            projection={"is_admin": 1}
        )
        
        return user.get('is_admin', False) if user else False
    
    async def block_user(self, telegram_id: int) -> bool:
        """
        Заблокировать пользователя
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            True если заблокирован
        """
        return await self.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": True, "is_blocked": True}}  # Set both for compatibility
        )
    
    async def unblock_user(self, telegram_id: int) -> bool:
        """
        Разблокировать пользователя
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            True если разблокирован
        """
        return await self.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"blocked": False, "is_blocked": False}}  # Set both for compatibility
        )
    
    async def is_blocked(self, telegram_id: int) -> bool:
        """
        Проверить заблокирован ли пользователь
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            True если заблокирован
        """
        user = await self.find_one(
            {"telegram_id": telegram_id},
            projection={"is_blocked": 1, "blocked": 1}
        )
        
        # Check BOTH fields for compatibility (admin panel uses 'blocked', old code uses 'is_blocked')
        if not user:
            return False
        
        return user.get('is_blocked', False) or user.get('blocked', False)
    
    async def increment_orders_count(self, telegram_id: int) -> bool:
        """
        Увеличить счетчик заказов
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            True если обновлено
        """
        return await self.update_one(
            {"telegram_id": telegram_id},
            {"$inc": {"orders_count": 1}}
        )
    
    async def add_to_spent(self, telegram_id: int, amount: float) -> bool:
        """
        Добавить к общей сумме потраченного
        
        Args:
            telegram_id: Telegram ID
            amount: Сумма
            
        Returns:
            True если обновлено
        """
        return await self.update_one(
            {"telegram_id": telegram_id},
            {"$inc": {"total_spent": abs(amount)}}
        )
    
    async def count_users(self, filter_dict: Optional[Dict] = None) -> int:
        """
        Подсчитать количество пользователей
        
        Args:
            filter_dict: Фильтр (опционально)
            
        Returns:
            Количество пользователей
        """
        filter_dict = filter_dict or {}
        return await self.collection.count_documents(filter_dict)
    
    async def get_all_users(self, filter_dict: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Получить всех пользователей
        
        Args:
            filter_dict: Фильтр (опционально)
            limit: Ограничение количества
            
        Returns:
            Список пользователей
        """
        filter_dict = filter_dict or {}
        if limit:
            return await self.find_many(filter_dict, limit=limit)
        else:
            # No limit - get all
            return await self.collection.find(filter_dict, {"_id": 0}).to_list(None)
    
    async def aggregate_users(self, pipeline: List[Dict]) -> List[Dict]:
        """
        Агрегация пользователей
        
        Args:
            pipeline: Pipeline для агрегации
            
        Returns:
            Результат агрегации
        """
        return await self.collection.aggregate(pipeline).to_list(None)
    
    async def update_user_field(self, telegram_id: int, field: str, value: any) -> bool:
        """
        Обновить поле пользователя
        
        Args:
            telegram_id: Telegram ID
            field: Название поля
            value: Значение
            
        Returns:
            True если обновлено
        """
        result = await self.update_one(
            {"telegram_id": telegram_id},
            {"$set": {field: value}}
        )
        # Clear cache for this user after update
        if result:
            clear_user_cache(telegram_id)
        return result
    
    async def get_users_with_balance(self, min_balance: float = 0.01) -> List[Dict]:
        """
        Получить пользователей с балансом
        
        Args:
            min_balance: Минимальный баланс
            
        Returns:
            Список пользователей
        """
        return await self.find_many(
            {"balance": {"$gte": min_balance}},
            sort=[("balance", -1)]
        )
    
    async def get_top_spenders(self, limit: int = 10) -> List[Dict]:
        """
        Получить топ пользователей по потраченной сумме
        
        Args:
            limit: Количество пользователей
            
        Returns:
            Список пользователей
        """
        return await self.find_many(
            {"total_spent": {"$gt": 0}},
            sort=[("total_spent", -1)],
            limit=limit
        )
    
    async def get_stats(self) -> Dict:
        """
        Получить статистику по пользователям
        
        Returns:
            Статистика
        """
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_users": {"$sum": 1},
                    "users_with_balance": {
                        "$sum": {"$cond": [{"$gt": ["$balance", 0]}, 1, 0]}
                    },
                    "admin_users": {
                        "$sum": {"$cond": ["$is_admin", 1, 0]}
                    },
                    "blocked_users": {
                        "$sum": {"$cond": ["$is_blocked", 1, 0]}
                    },
                    "total_balance": {"$sum": "$balance"},
                    "total_spent": {"$sum": "$total_spent"},
                    "total_orders": {"$sum": "$orders_count"}
                }
            }
        ]
        
        results = await self.aggregate(pipeline)
        
        if results:
            stats = results[0]
            stats.pop('_id', None)
            return stats
        
        return {
            "total_users": 0,
            "users_with_balance": 0,
            "admin_users": 0,
            "blocked_users": 0,
            "total_balance": 0.0,
            "total_spent": 0.0,
            "total_orders": 0
        }
