"""
Payment Repository
Репозиторий для работы с платежами
"""
from typing import Dict, List, Optional
from repositories.base_repository import BaseRepository
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class PaymentRepository(BaseRepository):
    """Репозиторий для коллекции payments"""
    
    def __init__(self, db):
        super().__init__(db.payments, "payments")
    
    async def create_payment(
        self,
        user_id: int,
        amount: float,
        currency: str,
        provider: str,
        invoice_id: str,
        order_id: Optional[str] = None,
        payment_data: Optional[Dict] = None
    ) -> Dict:
        """
        Создать запись о платеже
        
        Args:
            user_id: Telegram ID пользователя
            amount: Сумма
            currency: Валюта
            provider: Провайдер (oxapay, cryptobot)
            invoice_id: ID инвойса
            order_id: ID заказа (опционально)
            payment_data: Дополнительные данные
            
        Returns:
            Созданный платеж
        """
        payment_doc = {
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "provider": provider,
            "invoice_id": invoice_id,
            "order_id": order_id,
            "status": "pending",
            "payment_data": payment_data or {},
            "paid_at": None
        }
        
        return await self.insert_one(payment_doc)
    
    async def find_by_invoice_id(
        self,
        invoice_id: str,
        provider: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Найти платеж по invoice_id
        
        Args:
            invoice_id: ID инвойса
            provider: Провайдер (опционально)
            
        Returns:
            Документ платежа или None
        """
        filter_query = {"invoice_id": invoice_id}
        
        if provider:
            filter_query["provider"] = provider
        
        return await self.find_one(filter_query)
    
    async def find_by_order_id(self, order_id: str) -> Optional[Dict]:
        """
        Найти платеж по order_id
        
        Args:
            order_id: ID заказа
            
        Returns:
            Документ платежа или None
        """
        return await self.find_one({"order_id": order_id})
    
    async def get_user_payments(
        self,
        user_id: int,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Получить платежи пользователя
        
        Args:
            user_id: Telegram ID пользователя
            limit: Максимальное количество
            status: Фильтр по статусу
            
        Returns:
            Список платежей
        """
        filter_query = {"user_id": user_id}
        
        if status:
            filter_query["status"] = status
        
        return await self.find_many(
            filter_query,
            sort=[("created_at", -1)],
            limit=limit
        )
    
    async def update_status(
        self,
        invoice_id: str,
        new_status: str,
        paid_at: Optional[datetime] = None
    ) -> bool:
        """
        Обновить статус платежа
        
        Args:
            invoice_id: ID инвойса
            new_status: Новый статус (pending, paid, failed, expired)
            paid_at: Дата оплаты (для status=paid)
            
        Returns:
            True если обновлено
        """
        update_data = {
            "$set": {
                "status": new_status,
                "status_updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
        if paid_at:
            update_data["$set"]["paid_at"] = paid_at.isoformat()
        elif new_status == "paid":
            update_data["$set"]["paid_at"] = datetime.now(timezone.utc).isoformat()
        
        return await self.update_one(
            {"invoice_id": invoice_id},
            update_data
        )
    
    async def get_pending_payments(
        self,
        older_than_minutes: Optional[int] = None
    ) -> List[Dict]:
        """
        Получить pending платежи
        
        Args:
            older_than_minutes: Старше указанного времени
            
        Returns:
            Список платежей
        """
        filter_query = {"status": "pending"}
        
        if older_than_minutes:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
            filter_query["created_at"] = {"$lt": cutoff_time.isoformat()}
        
        return await self.find_many(
            filter_query,
            sort=[("created_at", 1)]
        )
    
    async def get_successful_payments(
        self,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict]:
        """
        Получить успешные платежи за период
        
        Args:
            days: За последние N дней
            limit: Максимальное количество
            
        Returns:
            Список платежей
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        return await self.find_many(
            {
                "status": "paid",
                "paid_at": {"$gte": cutoff_time.isoformat()}
            },
            sort=[("paid_at", -1)],
            limit=limit
        )
    
    async def get_stats(self, days: int = 30) -> Dict:
        """
        Получить статистику по платежам
        
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
                    "total_payments": {"$sum": 1},
                    "successful_payments": {
                        "$sum": {"$cond": [{"$eq": ["$status", "paid"]}, 1, 0]}
                    },
                    "pending_payments": {
                        "$sum": {"$cond": [{"$eq": ["$status", "pending"]}, 1, 0]}
                    },
                    "failed_payments": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                    "total_amount": {
                        "$sum": {"$cond": [{"$eq": ["$status", "paid"]}, "$amount", 0]}
                    },
                    "avg_payment": {
                        "$avg": {"$cond": [{"$eq": ["$status", "paid"]}, "$amount", None]}
                    },
                    "by_provider": {"$push": "$provider"}
                }
            }
        ]
        
        results = await self.aggregate(pipeline)
        
        if results:
            stats = results[0]
            stats.pop('_id', None)
            
            # Подсчитать по провайдерам
            provider_counts = {}
            for provider in stats.get('by_provider', []):
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            stats['by_provider'] = provider_counts
            
            # Success rate
            total = stats['total_payments']
            successful = stats['successful_payments']
            stats['success_rate'] = f"{(successful/total*100):.1f}%" if total > 0 else "0%"
            
            return stats
        
        return {
            "total_payments": 0,
            "successful_payments": 0,
            "pending_payments": 0,
            "failed_payments": 0,
            "total_amount": 0.0,
            "avg_payment": 0.0,
            "success_rate": "0%",
            "by_provider": {}
        }
    
    async def get_revenue(self, days: int = 30) -> float:
        """
        Получить выручку за период
        
        Args:
            days: За последние N дней
            
        Returns:
            Общая сумма успешных платежей
        """
        stats = await self.get_stats(days)
        return stats.get('total_amount', 0.0)
    
    async def expire_old_pending_payments(self, hours: int = 24) -> int:
        """
        Пометить старые pending платежи как expired
        
        Args:
            hours: Старше N часов
            
        Returns:
            Количество обновленных платежей
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        return await self.update_many(
            {
                "status": "pending",
                "created_at": {"$lt": cutoff_time.isoformat()}
            },
            {
                "$set": {
                    "status": "expired",
                    "expired_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )


"""
ИСПОЛЬЗОВАНИЕ:
=============

1. Создание платежа:
   ```python
   from repositories import get_payment_repo
   
   payment_repo = get_payment_repo()
   
   payment = await payment_repo.create_payment(
       user_id=12345,
       amount=50.0,
       currency="USDT",
       provider="oxapay",
       invoice_id="INV123",
       order_id="ORDER456"
   )
   ```

2. Обновление статуса после webhook:
   ```python
   await payment_repo.update_status("INV123", "paid")
   ```

3. Получить историю платежей пользователя:
   ```python
   payments = await payment_repo.get_user_payments(12345, limit=10)
   ```

4. Статистика:
   ```python
   stats = await payment_repo.get_stats(days=30)
   revenue = await payment_repo.get_revenue(days=30)
   ```

5. Cleanup старых pending:
   ```python
   expired_count = await payment_repo.expire_old_pending_payments(hours=24)
   ```
"""
