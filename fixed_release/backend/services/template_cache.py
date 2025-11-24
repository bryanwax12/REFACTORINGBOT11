"""
Template Caching
Кэширование шаблонов заказов в памяти для ускорения работы
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class TemplateCache:
    """
    Кэш для шаблонов заказов
    Кэширует часто используемые шаблоны в памяти
    """
    
    def __init__(self, cache_duration_minutes: int = 120):
        """
        Args:
            cache_duration_minutes: Время жизни кэша в минутах (по умолчанию 120 = 2 часа)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._user_templates_cache: Dict[int, Dict[str, Any]] = {}
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.hits = 0
        self.misses = 0
    
    def get(self, template_id: str) -> Optional[Dict]:
        """
        Получить шаблон по ID из кэша
        
        Args:
            template_id: ID шаблона
            
        Returns:
            Dict с данными шаблона или None
        """
        if template_id not in self._cache:
            self.misses += 1
            return None
        
        cached_item = self._cache[template_id]
        
        # Проверяем, не истек ли кэш
        if datetime.now(timezone.utc) > cached_item['expires_at']:
            logger.debug(f"Template cache expired for {template_id}")
            del self._cache[template_id]
            self.misses += 1
            return None
        
        self.hits += 1
        logger.debug(f"Template cache HIT for {template_id}")
        return cached_item['data']
    
    def get_user_templates(self, user_id: int) -> Optional[List[Dict]]:
        """
        Получить список шаблонов пользователя из кэша
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            List шаблонов или None
        """
        if user_id not in self._user_templates_cache:
            self.misses += 1
            return None
        
        cached_item = self._user_templates_cache[user_id]
        
        # Проверяем срок действия
        if datetime.now(timezone.utc) > cached_item['expires_at']:
            logger.debug(f"User templates cache expired for {user_id}")
            del self._user_templates_cache[user_id]
            self.misses += 1
            return None
        
        self.hits += 1
        logger.debug(f"User templates cache HIT for user {user_id}")
        return cached_item['data']
    
    def set(self, template_id: str, template_data: Dict) -> None:
        """
        Сохранить шаблон в кэш
        
        Args:
            template_id: ID шаблона
            template_data: Данные шаблона
        """
        self._cache[template_id] = {
            'data': template_data,
            'cached_at': datetime.now(timezone.utc),
            'expires_at': datetime.now(timezone.utc) + self.cache_duration
        }
        logger.debug(f"Template cached: {template_id}")
    
    def set_user_templates(self, user_id: int, templates: List[Dict]) -> None:
        """
        Сохранить список шаблонов пользователя в кэш
        
        Args:
            user_id: Telegram ID пользователя
            templates: Список шаблонов
        """
        self._user_templates_cache[user_id] = {
            'data': templates,
            'cached_at': datetime.now(timezone.utc),
            'expires_at': datetime.now(timezone.utc) + self.cache_duration
        }
        logger.debug(f"User templates cached for user {user_id}: {len(templates)} templates")
    
    def invalidate(self, template_id: str = None, user_id: int = None) -> None:
        """
        Инвалидировать кэш
        
        Args:
            template_id: ID конкретного шаблона (опционально)
            user_id: ID пользователя для очистки его списка шаблонов (опционально)
        """
        if template_id:
            if template_id in self._cache:
                del self._cache[template_id]
                logger.debug(f"Template cache invalidated: {template_id}")
        
        if user_id:
            if user_id in self._user_templates_cache:
                del self._user_templates_cache[user_id]
                logger.debug(f"User templates cache invalidated for user {user_id}")
        
        if not template_id and not user_id:
            # Очистить весь кэш
            self._cache.clear()
            self._user_templates_cache.clear()
            logger.info("All template cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кэша
        
        Returns:
            Dict со статистикой
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.hits,
            'misses': self.misses,
            'total_requests': total_requests,
            'hit_rate': f"{hit_rate:.1f}%",
            'cached_templates': len(self._cache),
            'cached_user_lists': len(self._user_templates_cache)
        }


# Глобальный экземпляр кэша (синглтон)
template_cache = TemplateCache(cache_duration_minutes=120)  # 2 часа
