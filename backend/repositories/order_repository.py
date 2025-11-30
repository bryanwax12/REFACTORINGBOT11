"""
Order Repository
Репозиторий для работы с заказами
"""
from typing import Dict, List, Optional
from repositories.base_repository import BaseRepository
from datetime import datetime, timezone, timedelta
from utils.order_utils import generate_order_id
import logging

logger = logging.getLogger(__name__)


class OrderRepository(BaseRepository):
    """Репозиторий для коллекции orders"""
    
    def __init__(self, db):
        super().__init__(db.orders, "orders")
    
    async def create_order(
        self,
        user_id: int,
        order_data: Dict,
        auto_generate_id: bool = True
    ) -> Dict:
        """
        Создать новый заказ
        
        Args:
            user_id: Telegram ID пользователя
            order_data: Данные заказа
            auto_generate_id: Автоматически генерировать order_id
            
        Returns:
            Созданный заказ
        """
        # Генерировать order_id если нужно
        if auto_generate_id and 'order_id' not in order_data:
            order_data['order_id'] = generate_order_id()
        
        # Добавить обязательные поля
        order_data.setdefault('user_id', user_id)
        order_data.setdefault('status', 'pending')
        order_data.setdefault('payment_status', 'unpaid')
        
        return await self.insert_one(order_data)
    
    async def find_by_id(self, order_id: str) -> Optional[Dict]:
        """
        Найти заказ по UUID id
        
        Args:
            order_id: UUID заказа (поле 'id' в БД)
            
        Returns:
            Документ заказа или None
        """
        return await self.find_one({"id": order_id})
    
    async def find_by_order_id(self, order_id: str) -> Optional[Dict]:
        """
        Найти заказ по order_id (tracking ID)
        
        Args:
            order_id: ID заказа (поле 'order_id' в БД)
            
        Returns:
            Документ заказа или None
        """
        return await self.find_one({"order_id": order_id})
    
    async def find_by_user(
        self,
        user_id: int,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Найти заказы пользователя
        
        Args:
            user_id: Telegram ID пользователя
            limit: Максимальное количество
            status: Фильтр по статусу
            
        Returns:
            Список заказов
        """
        filter_query = {"user_id": user_id}
        
        if status:
            filter_query['status'] = status
        
        return await self.find_many(
            filter_query,
            sort=[("created_at", -1)],
            limit=limit
        )
    
    async def find_by_telegram_id(
        self,
        telegram_id: int,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Найти заказы пользователя по telegram_id
        
        Args:
            telegram_id: Telegram ID пользователя
            limit: Максимальное количество
            status: Фильтр по статусу
            
        Returns:
            Список заказов
        """
        filter_query = {"telegram_id": telegram_id}
        
        if status:
            filter_query['status'] = status
        
        return await self.find_many(
            filter_query,
            sort=[("created_at", -1)],
            limit=limit
        )
    
    async def update_by_id(
        self,
        order_id: str,
        update_data: Dict
    ) -> bool:
        """
        Обновить заказ по UUID id
        
        Args:
            order_id: UUID заказа (поле 'id')
            update_data: Данные для обновления
            
        Returns:
            True если обновлено
        """
        result = await self.update_one(
            {"id": order_id},
            {"$set": update_data}
        )
        return result
    
    async def update_by_order_id(
        self,
        order_id: str,
        update_data: Dict
    ) -> bool:
        """
        Обновить заказ по order_id (ORD-...)
        
        Args:
            order_id: Order ID заказа (поле 'order_id')
            update_data: Данные для обновления
            
        Returns:
            True если обновлено
        """
        result = await self.update_one(
            {"order_id": order_id},
            {"$set": update_data}
        )
        return result
    
    async def update_status(
        self,
        order_id: str,
        new_status: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Обновить статус заказа
        
        Args:
            order_id: ID заказа
            new_status: Новый статус
            notes: Примечания (опционально)
            
        Returns:
            True если обновлено
        """
        update_data = {
            "$set": {
                "status": new_status,
                "status_updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
        if notes:
            update_data["$set"]["status_notes"] = notes
        
        return await self.update_one({"order_id": order_id}, update_data)
    
    async def update_payment_status(
        self,
        order_id: str,
        payment_status: str,
        payment_data: Optional[Dict] = None
    ) -> bool:
        """
        Обновить статус оплаты
        
        Args:
            order_id: ID заказа
            payment_status: Статус оплаты (paid, unpaid, refunded)
            payment_data: Дополнительные данные об оплате
            
        Returns:
            True если обновлено
        """
        update_data = {
            "$set": {
                "payment_status": payment_status,
                "payment_updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
        if payment_data:
            update_data["$set"]["payment_data"] = payment_data
        
        if payment_status == 'paid' and not payment_data:
            update_data["$set"]["paid_at"] = datetime.now(timezone.utc).isoformat()
        
        return await self.update_one({"order_id": order_id}, update_data)
    
    async def add_tracking_info(
        self,
        order_id: str,
        tracking_number: str,
        carrier: Optional[str] = None,
        label_url: Optional[str] = None
    ) -> bool:
        """
        Добавить информацию о трекинге
        
        Args:
            order_id: ID заказа
            tracking_number: Номер трекинга
            carrier: Название перевозчика
            label_url: URL лейбла
            
        Returns:
            True если обновлено
        """
        update_data = {
            "$set": {
                "tracking_number": tracking_number,
                "tracking_added_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
        if carrier:
            update_data["$set"]["carrier"] = carrier
        
        if label_url:
            update_data["$set"]["label_url"] = label_url
        
        return await self.update_one({"order_id": order_id}, update_data)
    
    async def find_with_filter(
        self,
        filter_dict: Dict,
        sort_by: str = "created_at",
        sort_order: int = -1,
        limit: int = 100
    ) -> List[Dict]:
        """
        Универсальный поиск заказов с фильтрами
        
        Args:
            filter_dict: Словарь фильтров
            sort_by: Поле для сортировки
            sort_order: Порядок сортировки (1 или -1)
            limit: Максимальное количество
            
        Returns:
            Список заказов
        """
        return await self.find_many(
            filter_dict,
            sort=[(sort_by, sort_order)],
            limit=limit
        )
    
    async def count_orders(self, filter_dict: Optional[Dict] = None) -> int:
        """
        Подсчет количества заказов
        
        Args:
            filter_dict: Фильтр для подсчета (опционально)
            
        Returns:
            Количество заказов
        """
        filter_dict = filter_dict or {}
        return await self.collection.count_documents(filter_dict)
    
    async def count_by_telegram_id(self, telegram_id: int) -> int:
        """
        Подсчет количества заказов пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Количество заказов пользователя
        """
        return await self.collection.count_documents({"telegram_id": telegram_id})
    
    async def aggregate_orders(self, pipeline: List[Dict]) -> List[Dict]:
        """
        Агрегация заказов
        
        Args:
            pipeline: Pipeline для агрегации
            
        Returns:
            Результат агрегации
        """
        return await self.collection.aggregate(pipeline).to_list(None)
    
    async def get_orders_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Получить заказы по статусу
        
        Args:
            status: Статус заказа
            limit: Максимальное количество
            
        Returns:
            Список заказов
        """
        return await self.find_many(
            {"status": status},
            sort=[("created_at", -1)],
            limit=limit
        )
    
    async def get_unpaid_orders(
        self,
        older_than_minutes: Optional[int] = None
    ) -> List[Dict]:
        """
        Получить неоплаченные заказы
        
        Args:
            older_than_minutes: Старше указанного количества минут
            
        Returns:
            Список заказов
        """
        filter_query = {"payment_status": "unpaid"}
        
        if older_than_minutes:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
            filter_query['created_at'] = {"$lt": cutoff_time.isoformat()}
        
        return await self.find_many(filter_query, sort=[("created_at", 1)])
    
    async def get_recent_orders(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict]:
        """
        Получить недавние заказы
        
        Args:
            hours: За последние N часов
            limit: Максимальное количество
            
        Returns:
            Список заказов
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        return await self.find_many(
            {"created_at": {"$gte": cutoff_time.isoformat()}},
            sort=[("created_at", -1)],
            limit=limit
        )
    
    async def get_stats(self, days: int = 30) -> Dict:
        """
        Получить статистику по заказам
        
        Args:
            days: За последние N дней
            
        Returns:
            Статистика
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": cutoff_time.isoformat()}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_orders": {"$sum": 1},
                    "paid_orders": {
                        "$sum": {"$cond": [{"$eq": ["$payment_status", "paid"]}, 1, 0]}
                    },
                    "unpaid_orders": {
                        "$sum": {"$cond": [{"$eq": ["$payment_status", "unpaid"]}, 1, 0]}
                    },
                    "pending_orders": {
                        "$sum": {"$cond": [{"$eq": ["$status", "pending"]}, 1, 0]}
                    },
                    "completed_orders": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                    "total_amount": {"$sum": "$total_cost"},
                    "avg_order_value": {"$avg": "$total_cost"}
                }
            }
        ]
        
        results = await self.aggregate(pipeline)
        
        if results:
            stats = results[0]
            stats.pop('_id', None)
            return stats
        
        return {
            "total_orders": 0,
            "paid_orders": 0,
            "unpaid_orders": 0,
            "pending_orders": 0,
            "completed_orders": 0,
            "total_amount": 0.0,
            "avg_order_value": 0.0
        }
    
    async def delete_old_unpaid_orders(self, days: int = 7) -> int:
        """
        Удалить старые неоплаченные заказы
        
        Args:
            days: Старше N дней
            
        Returns:
            Количество удаленных заказов
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        return await self.delete_many({
            "payment_status": "unpaid",
            "created_at": {"$lt": cutoff_time.isoformat()}
        })
