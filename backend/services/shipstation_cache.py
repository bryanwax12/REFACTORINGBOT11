"""
ShipStation API Response Caching
Кэширование результатов запросов тарифов для ускорения работы
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ShipStationCache:
    """
    Кэш для результатов ShipStation API
    Кэширует тарифы доставки на основе маршрута и веса посылки
    """
    
    def __init__(self, cache_duration_minutes: int = 60):
        """
        Args:
            cache_duration_minutes: Время жизни кэша в минутах (по умолчанию 60)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.hits = 0
        self.misses = 0
    
    def _generate_cache_key(self, 
                           from_zip: str,
                           to_zip: str,
                           weight: float,
                           length: float = 10,
                           width: float = 10,
                           height: float = 10) -> str:
        """
        Генерирует уникальный ключ кэша на основе параметров доставки
        
        Args:
            from_zip: ZIP код отправителя
            to_zip: ZIP код получателя
            weight: Вес в фунтах
            length, width, height: Размеры в дюймах
        
        Returns:
            str: MD5 хэш параметров
        """
        # Округляем weight до 0.1, размеры до целого для лучшего кэширования
        key_data = {
            'from_zip': from_zip,
            'to_zip': to_zip,
            'weight': round(weight, 1),
            'dimensions': f"{int(length)}x{int(width)}x{int(height)}"
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, 
            from_zip: str,
            to_zip: str,
            weight: float,
            length: float = 10,
            width: float = 10,
            height: float = 10) -> Optional[list]:
        """
        Получить закэшированные тарифы
        
        Returns:
            list: Список тарифов или None если кэш устарел/не найден
        """
        cache_key = self._generate_cache_key(from_zip, to_zip, weight, length, width, height)
        
        if cache_key not in self._cache:
            self.misses += 1
            logger.debug(f"❌ Cache MISS for route {from_zip} → {to_zip}")
            return None
        
        cache_entry = self._cache[cache_key]
        cached_time = cache_entry['timestamp']
        
        # Проверяем, не устарел ли кэш
        if datetime.now(timezone.utc) - cached_time > self.cache_duration:
            # Кэш устарел - удаляем
            del self._cache[cache_key]
            self.misses += 1
            logger.debug(f"⏰ Cache EXPIRED for route {from_zip} → {to_zip}")
            return None
        
        self.hits += 1
        logger.info(f"✅ Cache HIT for route {from_zip} → {to_zip} (age: {(datetime.now(timezone.utc) - cached_time).seconds}s)")
        return cache_entry['rates']
    
    def set(self,
            from_zip: str,
            to_zip: str,
            weight: float,
            rates: list,
            length: float = 10,
            width: float = 10,
            height: float = 10) -> None:
        """
        Сохранить тарифы в кэш
        
        Args:
            from_zip: ZIP код отправителя
            to_zip: ZIP код получателя
            weight: Вес в фунтах
            rates: Список тарифов от ShipStation
            length, width, height: Размеры в дюймах
        """
        cache_key = self._generate_cache_key(from_zip, to_zip, weight, length, width, height)
        
        self._cache[cache_key] = {
            'rates': rates,
            'timestamp': datetime.now(timezone.utc),
            'route': f"{from_zip} → {to_zip}",
            'weight': weight
        }
        
        logger.info(f"💾 Cached {len(rates)} rates for route {from_zip} → {to_zip}")
    
    def delete(self,
               from_zip: str,
               to_zip: str,
               weight: float,
               length: float = 10,
               width: float = 10,
               height: float = 10) -> bool:
        """
        Удалить конкретную запись из кэша
        
        Args:
            from_zip: ZIP код отправителя
            to_zip: ZIP код получателя
            weight: Вес в фунтах
            length, width, height: Размеры в дюймах
        
        Returns:
            bool: True если запись была удалена, False если не найдена
        """
        cache_key = self._generate_cache_key(from_zip, to_zip, weight, length, width, height)
        
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.info(f"🗑️ Deleted cache entry for route {from_zip} → {to_zip}")
            return True
        
        logger.debug(f"❌ Cache entry not found for route {from_zip} → {to_zip}")
        return False
    
    def clear(self) -> None:
        """Очистить весь кэш"""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("🧹 Cache cleared")
    
    def cleanup_expired(self) -> int:
        """
        Удалить устаревшие записи из кэша
        
        Returns:
            int: Количество удаленных записей
        """
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, entry in self._cache.items()
            if now - entry['timestamp'] > self.cache_duration
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"🧹 Removed {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кэша
        
        Returns:
            dict: Статистика (hits, misses, hit_rate, size)
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'cache_size': len(self._cache)
        }


# Глобальный инстанс кэша (singleton)
# Время жизни: 60 минут (тарифы не меняются часто)
shipstation_cache = ShipStationCache(cache_duration_minutes=60)
