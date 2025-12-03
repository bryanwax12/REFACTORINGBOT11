"""
Bot Configuration Manager
Управление конфигурацией для test и production ботов
"""
import os
import logging
from typing import Dict, Literal

logger = logging.getLogger(__name__)

# Типы окружений и режимов
BotEnvironment = Literal["test", "production"]
BotMode = Literal["polling", "webhook"]


class BotConfig:
    """
    Конфигурация бота для разных окружений
    
    Поддерживает два окружения:
    - test: Тестовый бот с polling
    - production: Продакшн бот с webhook
    """
    
    def __init__(self):
        """Инициализация конфигурации из переменных окружения"""
        # Основные настройки
        self.environment: BotEnvironment = os.environ.get('BOT_ENVIRONMENT', 'test').lower()
        self.mode: BotMode = os.environ.get('BOT_MODE', 'polling').lower()
        
        # Test bot
        self.test_bot_token = os.environ.get('TEST_BOT_TOKEN', '')
        self.test_bot_username = os.environ.get('TEST_BOT_USERNAME', 'whitelabel_shipping_bot_test_bot')
        
        # Production bot
        self.prod_bot_token = os.environ.get('PROD_BOT_TOKEN', '')
        self.prod_bot_username = os.environ.get('PROD_BOT_USERNAME', 'whitelabel_shipping_bot')
        
        # Webhook настройки
        self.webhook_base_url = os.environ.get('WEBHOOK_BASE_URL', '')
        self.webhook_path = os.environ.get('WEBHOOK_PATH', '/api/telegram/webhook')
        
        # Legacy поддержка (для обратной совместимости)
        os.environ.get('TELEGRAM_BOT_TOKEN', '')
        
        # Validate configuration
        self._validate_config()
        
        logger.info("🤖 Bot Configuration Loaded:")
        logger.info(f"   Environment: {self.environment.upper()}")
        logger.info(f"   Mode: {self.mode.upper()}")
        logger.info(f"   Active Bot: @{self.get_active_bot_username()}")
        
    def _validate_config(self):
        """Валидация конфигурации"""
        # Проверка что environment корректен
        if self.environment not in ['test', 'production']:
            logger.warning(f"Invalid BOT_ENVIRONMENT: {self.environment}. Using 'test'")
            self.environment = 'test'
        
        # Проверка что mode корректен
        if self.mode not in ['polling', 'webhook']:
            logger.warning(f"Invalid BOT_MODE: {self.mode}. Using 'polling'")
            self.mode = 'polling'
        
        # Проверка наличия токенов
        if not self.test_bot_token and not self.prod_bot_token:
            logger.error("❌ No bot tokens configured! Please set TEST_BOT_TOKEN or PROD_BOT_TOKEN")
        
        # Проверка webhook URL для production + webhook
        if self.environment == 'production' and self.mode == 'webhook':
            if not self.webhook_base_url:
                logger.warning("⚠️ WEBHOOK_BASE_URL not set for production webhook mode")
    
    def get_active_bot_token(self) -> str:
        """
        Получить токен активного бота
        
        Returns:
            Токен бота в зависимости от окружения
        """
        if self.environment == 'production':
            return self.prod_bot_token
        else:
            return self.test_bot_token
    
    def get_active_bot_username(self) -> str:
        """
        Получить username активного бота
        
        Returns:
            Username бота в зависимости от окружения
        """
        if self.environment == 'production':
            return self.prod_bot_username
        else:
            return self.test_bot_username
    
    def should_use_webhook(self) -> bool:
        """
        Определить нужно ли использовать webhook
        
        CRITICAL: In Kubernetes/production with multiple replicas, 
        MUST use webhook to avoid Telegram Conflict errors!
        
        Returns:
            True если нужен webhook, False для polling
        """
        # If explicitly set to webhook mode
        if self.mode == 'webhook':
            return True
        
        # KUBERNETES FIX: If webhook URL is configured, prefer webhook over polling
        # This prevents Conflict errors when multiple pods run simultaneously
        if self.webhook_base_url and self.webhook_path:
            logger.info("🔧 Webhook URL configured - using webhook mode to avoid Kubernetes conflicts")
            return True
        
        # Default to polling for local development
        return False
    
    def get_webhook_url(self) -> str:
        """
        Получить полный URL для webhook
        
        Returns:
            Полный URL webhook или пустую строку
        """
        if not self.should_use_webhook():
            return ''
        
        if not self.webhook_base_url:
            return ''
        
        # Убрать trailing slash из base_url
        base = self.webhook_base_url.rstrip('/')
        # Добавить leading slash к path если нужно
        path = self.webhook_path if self.webhook_path.startswith('/') else f'/{self.webhook_path}'
        
        return f"{base}{path}"
    
    def is_production(self) -> bool:
        """Проверка что это production окружение"""
        return self.environment == 'production'
    
    def is_test(self) -> bool:
        """Проверка что это test окружение"""
        return self.environment == 'test'
    
    def get_config_summary(self) -> Dict:
        """
        Получить сводку конфигурации
        
        Returns:
            Словарь с основной информацией о конфигурации
        """
        return {
            'environment': self.environment,
            'mode': self.mode,
            'bot_username': self.get_active_bot_username(),
            'webhook_enabled': self.should_use_webhook(),
            'webhook_url': self.get_webhook_url() if self.should_use_webhook() else None,
            'is_production': self.is_production()
        }
    
    def switch_environment(self, new_env: BotEnvironment):
        """
        Переключить окружение (для административных целей)
        
        Args:
            new_env: Новое окружение ('test' или 'production')
            
        Note:
            Требует перезапуск бота для применения изменений
        """
        if new_env not in ['test', 'production']:
            raise ValueError(f"Invalid environment: {new_env}")
        
        old_env = self.environment
        self.environment = new_env
        
        logger.warning(f"⚠️ Environment switched: {old_env} -> {new_env}")
        logger.warning("🔄 Bot restart required to apply changes")
    
    def switch_mode(self, new_mode: BotMode):
        """
        Переключить режим работы (для административных целей)
        
        Args:
            new_mode: Новый режим ('polling' или 'webhook')
            
        Note:
            Требует перезапуск бота для применения изменений
        """
        if new_mode not in ['polling', 'webhook']:
            raise ValueError(f"Invalid mode: {new_mode}")
        
        old_mode = self.mode
        self.mode = new_mode
        
        logger.warning(f"⚠️ Mode switched: {old_mode} -> {new_mode}")
        logger.warning("🔄 Bot restart required to apply changes")


# Глобальный экземпляр конфигурации
bot_config = BotConfig()


def get_bot_config() -> BotConfig:
    """
    Получить глобальный экземпляр конфигурации бота
    
    Returns:
        Экземпляр BotConfig
    """
    return bot_config


# Convenience functions для быстрого доступа
def get_bot_token() -> str:
    """Получить токен активного бота"""
    return bot_config.get_active_bot_token()


def get_bot_username() -> str:
    """Получить username активного бота"""
    return bot_config.get_active_bot_username()


def is_webhook_mode() -> bool:
    """Проверка что используется webhook режим"""
    return bot_config.should_use_webhook()


def is_polling_mode() -> bool:
    """Проверка что используется polling режим"""
    return not bot_config.should_use_webhook()


def is_production_environment() -> bool:
    """Проверка что это production окружение"""
    return bot_config.is_production()


def is_test_environment() -> bool:
    """Проверка что это test окружение"""
    return bot_config.is_test()


# Примеры использования в документации
"""
ИСПОЛЬЗОВАНИЕ:
=============

1. Получить конфигурацию:
   ```python
   from utils.bot_config import get_bot_config
   
   config = get_bot_config()
   print(config.get_config_summary())
   ```

2. Получить токен активного бота:
   ```python
   from utils.bot_config import get_bot_token
   
   token = get_bot_token()
   bot = Bot(token=token)
   ```

3. Проверить режим работы:
   ```python
   from utils.bot_config import is_webhook_mode, is_polling_mode
   
   if is_webhook_mode():
       # Настроить webhook
       await application.bot.set_webhook(url=config.get_webhook_url())
   else:
       # Запустить polling
       await application.updater.start_polling()
   ```

4. Проверить окружение:
   ```python
   from utils.bot_config import is_production_environment
   
   if is_production_environment():
       # Production логика
       pass
   else:
       # Test логика
       pass
   ```

ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (.env):
============================

# Окружение
BOT_ENVIRONMENT="test"           # или "production"

# Режим работы
BOT_MODE="polling"               # или "webhook"

# Test bot
TEST_BOT_TOKEN="..."
TEST_BOT_USERNAME="bot_test"

# Production bot
PROD_BOT_TOKEN="..."
PROD_BOT_USERNAME="bot_prod"

# Webhook (для production)
WEBHOOK_BASE_URL="https://example.com"
WEBHOOK_PATH="/api/telegram/webhook"

КОМБИНАЦИИ:
===========

1. Local Development (Разработка):
   BOT_ENVIRONMENT="test"
   BOT_MODE="polling"
   
2. Staging (Тестирование на сервере):
   BOT_ENVIRONMENT="test"
   BOT_MODE="webhook"
   WEBHOOK_BASE_URL="https://staging.example.com"
   
3. Production:
   BOT_ENVIRONMENT="production"
   BOT_MODE="webhook"
   WEBHOOK_BASE_URL="https://example.com"
"""
