"""
Base Repository Pattern
Базовый класс для всех репозиториев БД
"""
from abc import ABC
from typing import Dict, List, Optional, TypeVar, Generic
from motor.motor_asyncio import AsyncIOMotorCollection
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Базовый репозиторий для MongoDB коллекций
    
    Предоставляет стандартные CRUD операции и утилиты
    """
    
    def __init__(self, collection: AsyncIOMotorCollection, collection_name: str):
        """
        Инициализация репозитория
        
        Args:
            collection: MongoDB коллекция
            collection_name: Имя коллекции для логирования
        """
        self.collection = collection
        self.collection_name = collection_name
        logger.debug(f"📦 Repository initialized: {collection_name}")
    
    def _exclude_id(self, projection: Optional[Dict] = None) -> Dict:
        """
        Добавить исключение _id в projection
        
        Args:
            projection: Существующий projection или None
            
        Returns:
            Projection с исключенным _id
        """
        if projection is None:
            return {"_id": 0}
        
        if "_id" not in projection:
            projection["_id"] = 0
        
        return projection
    
    def _add_timestamps(self, document: Dict, update: bool = False) -> Dict:
        """
        Добавить timestamps в документ
        
        Args:
            document: Документ для обновления
            update: True если это update операция
            
        Returns:
            Документ с timestamps
        """
        now = datetime.now(timezone.utc).isoformat()
        
        if not update:
            document['created_at'] = now
        
        document['updated_at'] = now
        
        return document
    
    async def find_one(
        self,
        filter_query: Dict,
        projection: Optional[Dict] = None,
        exclude_id: bool = True
    ) -> Optional[Dict]:
        """
        Найти один документ
        
        Args:
            filter_query: Фильтр для поиска
            projection: Поля для возврата
            exclude_id: Исключить _id из результата
            
        Returns:
            Документ или None
        """
        if exclude_id:
            projection = self._exclude_id(projection)
        
        try:
            result = await self.collection.find_one(filter_query, projection)
            
            if result:
                logger.debug(f"✅ {self.collection_name}.find_one: Found")
            else:
                logger.debug(f"❌ {self.collection_name}.find_one: Not found")
            
            return result
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.find_one error: {e}")
            raise
    
    async def find_many(
        self,
        filter_query: Dict,
        projection: Optional[Dict] = None,
        limit: int = 1000,
        skip: int = 0,
        sort: Optional[List[tuple]] = None,
        exclude_id: bool = True
    ) -> List[Dict]:
        """
        Найти несколько документов
        
        Args:
            filter_query: Фильтр для поиска
            projection: Поля для возврата
            limit: Максимальное количество документов
            skip: Количество документов для пропуска
            sort: Сортировка [(field, direction)]
            exclude_id: Исключить _id из результатов
            
        Returns:
            Список документов
        """
        if exclude_id:
            projection = self._exclude_id(projection)
        
        try:
            cursor = self.collection.find(filter_query, projection)
            
            if sort:
                cursor = cursor.sort(sort)
            
            if skip > 0:
                cursor = cursor.skip(skip)
            
            if limit > 0:
                cursor = cursor.limit(limit)
            
            results = await cursor.to_list(length=limit)
            
            logger.debug(f"✅ {self.collection_name}.find_many: Found {len(results)} documents")
            
            return results
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.find_many error: {e}")
            raise
    
    async def insert_one(
        self,
        document: Dict,
        add_timestamps: bool = True
    ) -> Dict:
        """
        Вставить один документ
        
        Args:
            document: Документ для вставки
            add_timestamps: Добавить created_at/updated_at
            
        Returns:
            Вставленный документ
        """
        try:
            if add_timestamps:
                document = self._add_timestamps(document, update=False)
            
            result = await self.collection.insert_one(document)
            
            logger.info(f"✅ {self.collection_name}.insert_one: Success")
            
            return document
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.insert_one error: {e}")
            raise
    
    async def insert_many(
        self,
        documents: List[Dict],
        add_timestamps: bool = True
    ) -> List[Dict]:
        """
        Вставить несколько документов
        
        Args:
            documents: Список документов
            add_timestamps: Добавить timestamps
            
        Returns:
            Список вставленных документов
        """
        try:
            if add_timestamps:
                documents = [
                    self._add_timestamps(doc.copy(), update=False)
                    for doc in documents
                ]
            
            result = await self.collection.insert_many(documents)
            
            logger.info(f"✅ {self.collection_name}.insert_many: Inserted {len(documents)} documents")
            
            return documents
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.insert_many error: {e}")
            raise
    
    async def update_one(
        self,
        filter_query: Dict,
        update_data: Dict,
        upsert: bool = False,
        add_timestamps: bool = True
    ) -> bool:
        """
        Обновить один документ
        
        Args:
            filter_query: Фильтр для поиска
            update_data: Данные для обновления (с $set, $inc и т.д.)
            upsert: Создать если не существует
            add_timestamps: Добавить updated_at
            
        Returns:
            True если документ обновлен
        """
        try:
            # Добавить updated_at если требуется
            if add_timestamps and '$set' in update_data:
                update_data['$set']['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            result = await self.collection.update_one(
                filter_query,
                update_data,
                upsert=upsert
            )
            
            if result.modified_count > 0 or (upsert and result.upserted_id):
                logger.info(f"✅ {self.collection_name}.update_one: Success")
                return True
            else:
                logger.debug(f"❌ {self.collection_name}.update_one: No changes")
                return False
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.update_one error: {e}")
            raise
    
    async def update_many(
        self,
        filter_query: Dict,
        update_data: Dict,
        add_timestamps: bool = True
    ) -> int:
        """
        Обновить несколько документов
        
        Args:
            filter_query: Фильтр для поиска
            update_data: Данные для обновления
            add_timestamps: Добавить updated_at
            
        Returns:
            Количество обновленных документов
        """
        try:
            if add_timestamps and '$set' in update_data:
                update_data['$set']['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            result = await self.collection.update_many(filter_query, update_data)
            
            logger.info(f"✅ {self.collection_name}.update_many: Updated {result.modified_count} documents")
            
            return result.modified_count
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.update_many error: {e}")
            raise
    
    async def delete_one(self, filter_query: Dict) -> bool:
        """
        Удалить один документ
        
        Args:
            filter_query: Фильтр для поиска
            
        Returns:
            True если документ удален
        """
        try:
            result = await self.collection.delete_one(filter_query)
            
            if result.deleted_count > 0:
                logger.info(f"✅ {self.collection_name}.delete_one: Deleted")
                return True
            else:
                logger.debug(f"❌ {self.collection_name}.delete_one: Not found")
                return False
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.delete_one error: {e}")
            raise
    
    async def delete_many(self, filter_query: Dict) -> int:
        """
        Удалить несколько документов
        
        Args:
            filter_query: Фильтр для поиска
            
        Returns:
            Количество удаленных документов
        """
        try:
            result = await self.collection.delete_many(filter_query)
            
            logger.info(f"✅ {self.collection_name}.delete_many: Deleted {result.deleted_count} documents")
            
            return result.deleted_count
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.delete_many error: {e}")
            raise
    
    async def count(self, filter_query: Optional[Dict] = None) -> int:
        """
        Подсчитать документы
        
        Args:
            filter_query: Фильтр для поиска (если None, считает все)
            
        Returns:
            Количество документов
        """
        try:
            if filter_query is None:
                filter_query = {}
            
            count = await self.collection.count_documents(filter_query)
            
            logger.debug(f"✅ {self.collection_name}.count: {count} documents")
            
            return count
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.count error: {e}")
            raise
    
    async def exists(self, filter_query: Dict) -> bool:
        """
        Проверить существование документа
        
        Args:
            filter_query: Фильтр для поиска
            
        Returns:
            True если документ существует
        """
        try:
            count = await self.collection.count_documents(filter_query, limit=1)
            return count > 0
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.exists error: {e}")
            raise
    
    async def aggregate(self, pipeline: List[Dict]) -> List[Dict]:
        """
        Выполнить aggregation pipeline
        
        Args:
            pipeline: Aggregation pipeline
            
        Returns:
            Результаты aggregation
        """
        try:
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)
            
            logger.debug(f"✅ {self.collection_name}.aggregate: {len(results)} results")
            
            return results
        except Exception as e:
            logger.error(f"❌ {self.collection_name}.aggregate error: {e}")
            raise
