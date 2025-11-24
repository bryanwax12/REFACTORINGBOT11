"""
API Configuration Manager
Централизованное управление API ключами для всех внешних сервисов
"""
import os
import logging
from typing import Optional, Dict, Literal

logger = logging.getLogger(__name__)

APIEnvironment = Literal["test", "production"]


class APIConfigManager:
    """
    Менеджер конфигурации для всех внешних API
    
    Управляет:
    - ShipStation API (test/production ключи)
    - Oxapay API
    - CryptoBot Token
    - Другие внешние сервисы
    """
    
    def __init__(self):
        """Инициализация конфигурации из переменных окружения"""
        # ShipStation API keys
        self.shipstation_test_key = os.environ.get('SHIPSTATION_API_KEY_TEST', '')
        self.shipstation_prod_key = os.environ.get('SHIPSTATION_API_KEY_PROD', '')
        self.shipstation_default_key = os.environ.get('SHIPSTATION_API_KEY', '')
        
        # Oxapay API key
        self.oxapay_api_key = os.environ.get('OXAPAY_API_KEY', '')
        
        # CryptoBot Token
        self.cryptobot_token = os.environ.get('CRYPTOBOT_TOKEN', '')
        
        # Current environment (default to TEST for sandbox mode)
        self._current_environment: APIEnvironment = "test"  # ⚠️ SANDBOX MODE ENABLED
        
        # Cache для текущих активных ключей
        self._active_keys_cache: Dict[str, str] = {}
        
        logger.info("🔑 API Configuration Manager initialized")
        self._validate_config()
    
    def _validate_config(self):
        """Валидация конфигурации при инициализации"""
        warnings = []
        
        # Проверка ShipStation ключей
        if not self.shipstation_test_key and not self.shipstation_prod_key and not self.shipstation_default_key:
            warnings.append("⚠️ No ShipStation API keys configured")
        
        if not self.shipstation_test_key:
            warnings.append("⚠️ SHIPSTATION_API_KEY_TEST not set (test mode unavailable)")
        
        if not self.shipstation_prod_key:
            warnings.append("⚠️ SHIPSTATION_API_KEY_PROD not set (production mode unavailable)")
        
        # Проверка Oxapay
        if not self.oxapay_api_key:
            warnings.append("⚠️ OXAPAY_API_KEY not configured")
        
        # Проверка CryptoBot
        if not self.cryptobot_token:
            warnings.append("⚠️ CRYPTOBOT_TOKEN not configured")
        
        # Вывести предупреждения
        for warning in warnings:
            logger.warning(warning)
    
    def set_environment(self, environment: APIEnvironment):
        """
        Установить текущее окружение для API
        
        Args:
            environment: 'test' или 'production'
        """
        if environment not in ['test', 'production']:
            raise ValueError(f"Invalid environment: {environment}")
        
        old_env = self._current_environment
        self._current_environment = environment
        
        # Очистить кеш при смене окружения
        self._active_keys_cache.clear()
        
        logger.info(f"🔄 API Environment changed: {old_env} -> {environment}")
    
    def get_current_environment(self) -> APIEnvironment:
        """Получить текущее окружение"""
        return self._current_environment
    
    def get_shipstation_key(self, environment: Optional[APIEnvironment] = None) -> str:
        """
        Получить ShipStation API ключ
        
        Args:
            environment: Окружение (если None, используется текущее)
            
        Returns:
            API ключ для указанного окружения
        """
        env = environment or self._current_environment
        
        # Проверить кеш
        cache_key = f"shipstation_{env}"
        if cache_key in self._active_keys_cache:
            return self._active_keys_cache[cache_key]
        
        # Выбрать ключ
        if env == 'test':
            key = self.shipstation_test_key or self.shipstation_default_key
        else:  # production
            key = self.shipstation_prod_key or self.shipstation_default_key
        
        if not key:
            logger.error(f"❌ ShipStation API key not available for {env} environment")
            raise ValueError(f"ShipStation API key not configured for {env}")
        
        # Кешировать
        self._active_keys_cache[cache_key] = key
        
        # Логировать (частично скрыть ключ)
        key_display = self._mask_key(key)
        logger.debug(f"🔑 ShipStation key ({env}): {key_display}")
        
        return key
    
    def get_oxapay_key(self) -> str:
        """
        Получить Oxapay API ключ
        
        Returns:
            API ключ Oxapay
        """
        if not self.oxapay_api_key:
            logger.error("❌ Oxapay API key not configured")
            raise ValueError("Oxapay API key not configured")
        
        return self.oxapay_api_key
    
    def get_cryptobot_token(self) -> str:
        """
        Получить CryptoBot токен
        
        Returns:
            CryptoBot токен
        """
        if not self.cryptobot_token:
            logger.error("❌ CryptoBot token not configured")
            raise ValueError("CryptoBot token not configured")
        
        return self.cryptobot_token
    
    def is_shipstation_configured(self, environment: Optional[APIEnvironment] = None) -> bool:
        """
        Проверить доступность ShipStation ключа
        
        Args:
            environment: Окружение для проверки
            
        Returns:
            True если ключ доступен
        """
        try:
            self.get_shipstation_key(environment)
            return True
        except ValueError:
            return False
    
    def is_oxapay_configured(self) -> bool:
        """Проверить доступность Oxapay ключа"""
        return bool(self.oxapay_api_key)
    
    def is_cryptobot_configured(self) -> bool:
        """Проверить доступность CryptoBot токена"""
        return bool(self.cryptobot_token)
    
    def get_all_keys_status(self) -> Dict:
        """
        Получить статус всех API ключей
        
        Returns:
            Словарь со статусом конфигурации
        """
        return {
            'environment': self._current_environment,
            'shipstation': {
                'test_configured': bool(self.shipstation_test_key),
                'prod_configured': bool(self.shipstation_prod_key),
                'default_configured': bool(self.shipstation_default_key),
                'current_available': self.is_shipstation_configured()
            },
            'oxapay': {
                'configured': self.is_oxapay_configured()
            },
            'cryptobot': {
                'configured': self.is_cryptobot_configured()
            }
        }
    
    @staticmethod
    def _mask_key(key: str, visible_chars: int = 8) -> str:
        """
        Замаскировать API ключ для безопасного логирования
        
        Args:
            key: Ключ для маскирования
            visible_chars: Количество видимых символов в начале и конце
            
        Returns:
            Замаскированный ключ
        """
        if len(key) <= visible_chars * 2:
            return '*' * len(key)
        
        start = key[:visible_chars]
        end = key[-visible_chars:]
        middle = '*' * (len(key) - visible_chars * 2)
        
        return f"{start}{middle}{end}"
    
    def get_shipstation_headers(self, environment: Optional[APIEnvironment] = None) -> Dict[str, str]:
        """
        Получить готовые headers для ShipStation API
        
        Args:
            environment: Окружение (если None, используется текущее)
            
        Returns:
            Словарь с headers
        """
        return {
            'API-Key': self.get_shipstation_key(environment),
            'Content-Type': 'application/json'
        }
    
    def get_oxapay_headers(self) -> Dict[str, str]:
        """
        Получить готовые headers для Oxapay API
        
        Returns:
            Словарь с headers
        """
        return {
            'Content-Type': 'application/json'
        }


# Глобальный экземпляр менеджера
_api_config_manager: Optional[APIConfigManager] = None


def get_api_config() -> APIConfigManager:
    """
    Получить глобальный экземпляр API Config Manager
    
    Returns:
        Экземпляр APIConfigManager
    """
    global _api_config_manager
    
    if _api_config_manager is None:
        _api_config_manager = APIConfigManager()
    
    return _api_config_manager


def init_api_config(environment: APIEnvironment = "production") -> APIConfigManager:
    """
    Инициализировать API Config Manager с указанным окружением
    
    Args:
        environment: Начальное окружение
        
    Returns:
        Экземпляр APIConfigManager
    """
    global _api_config_manager
    
    _api_config_manager = APIConfigManager()
    _api_config_manager.set_environment(environment)
    
    return _api_config_manager


# Convenience functions для быстрого доступа
def get_shipstation_key(environment: Optional[APIEnvironment] = None) -> str:
    """Получить ShipStation API ключ"""
    return get_api_config().get_shipstation_key(environment)


def get_oxapay_key() -> str:
    """Получить Oxapay API ключ"""
    return get_api_config().get_oxapay_key()


def get_cryptobot_token() -> str:
    """Получить CryptoBot токен"""
    return get_api_config().get_cryptobot_token()


def get_shipstation_headers(environment: Optional[APIEnvironment] = None) -> Dict[str, str]:
    """Получить готовые headers для ShipStation API"""
    return get_api_config().get_shipstation_headers(environment)


def set_api_environment(environment: APIEnvironment):
    """Установить окружение для всех API"""
    get_api_config().set_environment(environment)


# Примеры использования
"""
ИСПОЛЬЗОВАНИЕ:
=============

1. Базовое использование:
   ```python
   from utils.api_config import get_shipstation_key, get_oxapay_key
   
   # Получить ключ для текущего окружения
   key = get_shipstation_key()
   
   # Получить ключ для конкретного окружения
   test_key = get_shipstation_key('test')
   prod_key = get_shipstation_key('production')
   ```

2. Использование headers:
   ```python
   from utils.api_config import get_shipstation_headers
   import httpx
   
   headers = get_shipstation_headers()
   response = await client.post(url, headers=headers, json=data)
   ```

3. Переключение окружения:
   ```python
   from utils.api_config import set_api_environment
   
   # Переключить на test
   set_api_environment('test')
   
   # Теперь все вызовы get_shipstation_key() вернут test ключ
   ```

4. Проверка конфигурации:
   ```python
   from utils.api_config import get_api_config
   
   config = get_api_config()
   if config.is_shipstation_configured('test'):
       # Test ключ доступен
       pass
   
   # Получить полный статус
   status = config.get_all_keys_status()
   ```

ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (.env):
============================

# ShipStation
SHIPSTATION_API_KEY_TEST="test_key_here"
SHIPSTATION_API_KEY_PROD="prod_key_here"
SHIPSTATION_API_KEY="default_key"  # Fallback

# Oxapay
OXAPAY_API_KEY="your_key"

# CryptoBot
CRYPTOBOT_TOKEN="your_token"
"""
