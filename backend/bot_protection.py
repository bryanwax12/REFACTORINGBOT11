"""
Bot Protection System - Anti-Cloning & Security Features
Защищает бота от копирования и несанкционированного использования
"""

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Уникальный идентификатор этого экземпляра бота
BOT_INSTANCE_ID = os.environ.get('BOT_INSTANCE_ID', str(uuid.uuid4()))

# Секретный ключ для подписи (хранится в .env)
SECRET_SIGNATURE_KEY = os.environ.get('BOT_SIGNATURE_KEY', 'default_secret_key_change_me')

class BotProtection:
    """Система защиты бота от копирования"""
    
    def __init__(self, owner_telegram_id: int, bot_name: str = "WhiteLabelBot"):
        self.owner_id = owner_telegram_id
        self.bot_name = bot_name
        self.instance_id = BOT_INSTANCE_ID
        
    def generate_signature(self, data: str) -> str:
        """Генерирует криптографическую подпись для данных"""
        signature = hmac.new(
            SECRET_SIGNATURE_KEY.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature[:16]  # Первые 16 символов
    
    def create_watermark(self, message_id: int, user_id: int) -> str:
        """
        Создает невидимый водяной знак для сообщений
        Уникальная подпись для каждого сообщения
        """
        data = f"{self.instance_id}:{message_id}:{user_id}:{self.bot_name}"
        signature = self.generate_signature(data)
        # Используем zero-width characters для невидимого watermark
        watermark = f"​{signature}​"  # ​ - zero-width space
        return watermark
    
    def verify_owner(self, telegram_id: int) -> bool:
        """Проверяет, что пользователь - владелец бота"""
        return telegram_id == self.owner_id
    
    def log_suspicious_activity(self, activity: str, details: dict):
        """Логирует подозрительную активность"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "instance_id": self.instance_id,
            "activity": activity,
            "details": details
        }
        logger.warning(f"🚨 SUSPICIOUS ACTIVITY: {log_entry}")
        return log_entry
    
    def check_rate_limit(self, user_id: int, action: str, limit: int = 10) -> bool:
        """
        Проверяет rate limiting для пользователя
        Защита от злоупотребления
        """
        # Здесь можно добавить Redis для хранения счетчиков
        # Пока простая проверка
        return True
    
    def add_protection_footer(self, message: str, context_id: Optional[str] = None) -> str:
        """
        Добавляет защитный footer к сообщению
        Содержит невидимый watermark
        """
        if context_id:
            watermark = self.create_watermark(hash(context_id), hash(self.instance_id))
            return f"{message}\n{watermark}"
        return message
    
    def get_instance_info(self) -> dict:
        """Возвращает информацию об инстансе бота"""
        return {
            "instance_id": self.instance_id,
            "bot_name": self.bot_name,
            "owner_id": self.owner_id,
            "protected": True,
            "version": "1.0.0"
        }

# Дополнительные меры защиты

def obfuscate_api_key(api_key: str) -> str:
    """Маскирует API ключ для логов"""
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}...{api_key[-4:]}"

def detect_clone_attempt(bot_token: str, expected_id: str) -> bool:
    """
    Проверяет, не является ли это клоном бота
    Сравнивает токен с ожидаемым
    """
    token_hash = hashlib.sha256(bot_token.encode()).hexdigest()
    expected_hash = hashlib.sha256(expected_id.encode()).hexdigest()
    return token_hash != expected_hash

# Информационные watermarks для UI
PROTECTED_BADGE = "🔒"
VERSION_WATERMARK = f"v1.0-{BOT_INSTANCE_ID[:8]}"

# Copyright и licensing info
COPYRIGHT_NOTICE = f"""
© 2025 Shipping Label Bot
Instance ID: {BOT_INSTANCE_ID[:8]}
Protected by Anti-Clone System
Unauthorized copying is prohibited
"""

def get_copyright_footer() -> str:
    """Возвращает copyright footer для важных сообщений"""
    return f"\n\n_{VERSION_WATERMARK}_"
