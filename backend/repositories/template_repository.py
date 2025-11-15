"""
Template Repository
Репозиторий для работы с шаблонами
"""
from typing import Dict, List, Optional
from repositories.base_repository import BaseRepository
import logging

logger = logging.getLogger(__name__)


class TemplateRepository(BaseRepository):
    """Репозиторий для коллекции templates"""
    
    def __init__(self, db):
        super().__init__(db.templates, "templates")
    
    async def create_template(
        self,
        name: str,
        template_type: str,
        template_data: Dict,
        user_id: Optional[int] = None,
        is_public: bool = False
    ) -> Dict:
        """
        Создать шаблон
        
        Args:
            name: Название шаблона
            template_type: Тип (label, message, product)
            template_data: Данные шаблона
            user_id: ID пользователя (если personal template)
            is_public: Публичный шаблон
            
        Returns:
            Созданный шаблон
        """
        template_doc = {
            "name": name,
            "type": template_type,
            "data": template_data,
            "user_id": user_id,
            "is_public": is_public,
            "is_active": True,
            "usage_count": 0
        }
        
        return await self.insert_one(template_doc)
    
    async def find_by_name(
        self,
        name: str,
        user_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Найти шаблон по имени
        
        Args:
            name: Название шаблона
            user_id: ID пользователя (для personal templates)
            
        Returns:
            Документ шаблона или None
        """
        filter_query = {"name": name, "is_active": True}
        
        if user_id:
            # Искать личный или публичный шаблон
            filter_query = {
                "$and": [
                    {"name": name},
                    {"is_active": True},
                    {
                        "$or": [
                            {"user_id": user_id},
                            {"is_public": True}
                        ]
                    }
                ]
            }
        else:
            # Только публичные
            filter_query["is_public"] = True
        
        return await self.find_one(filter_query)
    
    async def get_user_templates(
        self,
        user_id: int,
        template_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Получить шаблоны пользователя
        
        Args:
            user_id: Telegram ID пользователя
            template_type: Фильтр по типу
            
        Returns:
            Список шаблонов
        """
        filter_query = {
            "user_id": user_id,
            "is_active": True
        }
        
        if template_type:
            filter_query["type"] = template_type
        
        return await self.find_many(
            filter_query,
            sort=[("created_at", -1)]
        )
    
    async def get_public_templates(
        self,
        template_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Получить публичные шаблоны
        
        Args:
            template_type: Фильтр по типу
            limit: Максимальное количество
            
        Returns:
            Список публичных шаблонов
        """
        filter_query = {
            "is_public": True,
            "is_active": True
        }
        
        if template_type:
            filter_query["type"] = template_type
        
        return await self.find_many(
            filter_query,
            sort=[("usage_count", -1)],
            limit=limit
        )
    
    async def update_template(
        self,
        template_id: str,
        template_data: Dict
    ) -> bool:
        """
        Обновить данные шаблона
        
        Args:
            template_id: ID шаблона
            template_data: Новые данные
            
        Returns:
            True если обновлено
        """
        # Предполагаем что template_id это name
        return await self.update_one(
            {"name": template_id, "is_active": True},
            {"$set": {"data": template_data}}
        )
    
    async def increment_usage(self, template_name: str) -> bool:
        """
        Увеличить счетчик использования шаблона
        
        Args:
            template_name: Название шаблона
            
        Returns:
            True если обновлено
        """
        return await self.update_one(
            {"name": template_name, "is_active": True},
            {"$inc": {"usage_count": 1}}
        )
    
    async def delete_template(self, template_name: str, user_id: int) -> bool:
        """
        Удалить шаблон (soft delete)
        
        Args:
            template_name: Название шаблона
            user_id: ID владельца
            
        Returns:
            True если удалено
        """
        return await self.update_one(
            {
                "name": template_name,
                "user_id": user_id
            },
            {"$set": {"is_active": False}}
        )
    
    async def get_popular_templates(
        self,
        limit: int = 10,
        template_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Получить популярные шаблоны
        
        Args:
            limit: Количество шаблонов
            template_type: Фильтр по типу
            
        Returns:
            Список популярных шаблонов
        """
        filter_query = {
            "is_public": True,
            "is_active": True,
            "usage_count": {"$gt": 0}
        }
        
        if template_type:
            filter_query["type"] = template_type
        
        return await self.find_many(
            filter_query,
            sort=[("usage_count", -1)],
            limit=limit
        )
    
    async def search_templates(
        self,
        search_term: str,
        user_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Поиск шаблонов по названию
        
        Args:
            search_term: Поисковый запрос
            user_id: ID пользователя (для personal + public)
            limit: Максимальное количество
            
        Returns:
            Список найденных шаблонов
        """
        filter_query = {
            "name": {"$regex": search_term, "$options": "i"},
            "is_active": True
        }
        
        if user_id:
            filter_query = {
                "$and": [
                    {"name": {"$regex": search_term, "$options": "i"}},
                    {"is_active": True},
                    {
                        "$or": [
                            {"user_id": user_id},
                            {"is_public": True}
                        ]
                    }
                ]
            }
        else:
            filter_query["is_public"] = True
        
        return await self.find_many(
            filter_query,
            sort=[("usage_count", -1)],
            limit=limit
        )
    
    async def find_by_id(self, template_id: str) -> Optional[Dict]:
        """
        Найти шаблон по UUID
        
        Args:
            template_id: UUID шаблона
            
        Returns:
            Шаблон или None
        """
        return await self.find_one({"id": template_id})
    
    async def update_by_id(self, template_id: str, update_data: Dict) -> bool:
        """
        Обновить шаблон по UUID
        
        Args:
            template_id: UUID шаблона
            update_data: Данные для обновления
            
        Returns:
            True если обновлено
        """
        return await self.update_one({"id": template_id}, {"$set": update_data})
    
    async def delete_by_id(self, template_id: str) -> bool:
        """
        Удалить шаблон по UUID
        
        Args:
            template_id: UUID шаблона
            
        Returns:
            True если удалено
        """
        result = await self.collection.delete_one({"id": template_id})
        return result.deleted_count > 0
    
    async def count_user_templates(self, telegram_id: int) -> int:
        """
        Подсчитать количество шаблонов пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Количество шаблонов
        """
        return await self.collection.count_documents({"telegram_id": telegram_id})
    
    async def get_stats(self) -> Dict:
        """
        Получить статистику по шаблонам
        
        Returns:
            Статистика
        """
        pipeline = [
            {
                "$match": {"is_active": True}
            },
            {
                "$group": {
                    "_id": None,
                    "total_templates": {"$sum": 1},
                    "public_templates": {
                        "$sum": {"$cond": ["$is_public", 1, 0]}
                    },
                    "private_templates": {
                        "$sum": {"$cond": [{"$not": "$is_public"}, 1, 0]}
                    },
                    "total_usage": {"$sum": "$usage_count"},
                    "by_type": {"$push": "$type"}
                }
            }
        ]
        
        results = await self.aggregate(pipeline)
        
        if results:
            stats = results[0]
            stats.pop('_id', None)
            
            # Подсчитать по типам
            type_counts = {}
            for template_type in stats.get('by_type', []):
                type_counts[template_type] = type_counts.get(template_type, 0) + 1
            
            stats['by_type'] = type_counts
            
            return stats
        
        return {
            "total_templates": 0,
            "public_templates": 0,
            "private_templates": 0,
            "total_usage": 0,
            "by_type": {}
        }


"""
ИСПОЛЬЗОВАНИЕ:
=============

1. Создание шаблона:
   ```python
   from repositories import get_template_repo
   
   template_repo = get_template_repo()
   
   template = await template_repo.create_template(
       name="Express Shipping",
       template_type="label",
       template_data={
           "from_address": {...},
           "parcel": {"weight": 1.0}
       },
       user_id=12345,
       is_public=False
   )
   ```

2. Найти шаблон:
   ```python
   template = await template_repo.find_by_name("Express Shipping", user_id=12345)
   ```

3. Использовать шаблон:
   ```python
   template = await template_repo.find_by_name("Express Shipping")
   await template_repo.increment_usage("Express Shipping")
   
   # Использовать данные
   label_data = template['data']
   ```

4. Получить популярные:
   ```python
   popular = await template_repo.get_popular_templates(limit=10)
   ```

5. Поиск:
   ```python
   results = await template_repo.search_templates("express", user_id=12345)
   ```
"""
