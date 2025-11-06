"""
Telegram Bot Safety System - Защита от блокировки
Предотвращает блокировку бота Telegram
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class TelegramSafetySystem:
    """Система безопасности для предотвращения блокировки бота"""
    
    def __init__(self):
        # Rate limiting counters
        self.message_counters: Dict[int, List[float]] = {}  # user_id -> timestamps
        self.global_message_counter: List[float] = []
        
        # Limits (по документации Telegram)
        self.MAX_MESSAGES_PER_SECOND_PER_USER = 1  # 1 сообщение/сек на пользователя
        self.MAX_MESSAGES_PER_SECOND_GLOBAL = 30  # 30 сообщений/сек всего
        self.MAX_MESSAGES_PER_MINUTE_PER_USER = 20  # 20 сообщений/мин на пользователя
        self.MAX_BROADCAST_RATE = 8  # 8 сообщений/сек при broadcast
        
        # Blocked users tracking
        self.blocked_users: set = set()
        
        # Error tracking
        self.error_counts: Dict[str, int] = {}
        self.last_error_reset = time.time()
        
    async def can_send_message(self, user_id: int) -> bool:
        """
        Проверяет, можно ли отправить сообщение пользователю
        Implements rate limiting
        """
        current_time = time.time()
        
        # Cleanup old timestamps (older than 1 minute)
        if user_id in self.message_counters:
            self.message_counters[user_id] = [
                ts for ts in self.message_counters[user_id] 
                if current_time - ts < 60
            ]
        else:
            self.message_counters[user_id] = []
        
        # Check per-user rate limits
        recent_messages = [
            ts for ts in self.message_counters[user_id]
            if current_time - ts < 1  # Last second
        ]
        
        if len(recent_messages) >= self.MAX_MESSAGES_PER_SECOND_PER_USER:
            logger.warning(f"Rate limit exceeded for user {user_id} (per second)")
            return False
        
        if len(self.message_counters[user_id]) >= self.MAX_MESSAGES_PER_MINUTE_PER_USER:
            logger.warning(f"Rate limit exceeded for user {user_id} (per minute)")
            return False
        
        # Check global rate limits
        self.global_message_counter = [
            ts for ts in self.global_message_counter
            if current_time - ts < 1
        ]
        
        if len(self.global_message_counter) >= self.MAX_MESSAGES_PER_SECOND_GLOBAL:
            logger.warning(f"Global rate limit exceeded")
            return False
        
        return True
    
    def record_message_sent(self, user_id: int):
        """Записывает факт отправки сообщения"""
        current_time = time.time()
        
        if user_id not in self.message_counters:
            self.message_counters[user_id] = []
        
        self.message_counters[user_id].append(current_time)
        self.global_message_counter.append(current_time)
    
    async def safe_send_message(self, bot, chat_id: int, text: str, **kwargs):
        """
        Безопасная отправка сообщения с rate limiting
        """
        # Check if user is blocked
        if chat_id in self.blocked_users:
            logger.info(f"Skipping message to blocked user {chat_id}")
            return None
        
        # Check rate limits
        if not await self.can_send_message(chat_id):
            # Wait a bit and retry
            await asyncio.sleep(1)
            if not await self.can_send_message(chat_id):
                logger.warning(f"Rate limit still exceeded for {chat_id}, skipping message")
                return None
        
        try:
            # Record before sending
            self.record_message_sent(chat_id)
            
            # Send message
            result = await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            return result
            
        except Exception as e:
            error_type = type(e).__name__
            
            # Handle specific Telegram errors
            if "blocked" in str(e).lower() or "bot was blocked" in str(e).lower():
                logger.warning(f"User {chat_id} blocked the bot")
                self.blocked_users.add(chat_id)
                # Save to database for tracking
                return None
            
            elif "chat not found" in str(e).lower():
                logger.warning(f"Chat {chat_id} not found")
                self.blocked_users.add(chat_id)
                return None
            
            elif "rate limit" in str(e).lower() or "429" in str(e):
                logger.error(f"Telegram rate limit hit: {e}")
                # Wait longer
                await asyncio.sleep(3)
                return None
            
            else:
                logger.error(f"Error sending message to {chat_id}: {e}")
                self.track_error(error_type)
                return None
    
    def track_error(self, error_type: str):
        """Отслеживает ошибки для мониторинга"""
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # Reset counters every hour
        if time.time() - self.last_error_reset > 3600:
            self.error_counts = {}
            self.last_error_reset = time.time()
    
    async def safe_broadcast(self, bot, user_ids: List[int], text: str, **kwargs):
        """
        Безопасная рассылка с соблюдением лимитов
        Max 8 messages per second for broadcasts
        """
        successful = 0
        failed = 0
        
        for user_id in user_ids:
            result = await self.safe_send_message(bot, user_id, text, **kwargs)
            
            if result:
                successful += 1
            else:
                failed += 1
            
            # Rate limiting for broadcasts (8 msg/sec)
            await asyncio.sleep(1 / self.MAX_BROADCAST_RATE)
        
        logger.info(f"Broadcast complete: {successful} successful, {failed} failed")
        return {"successful": successful, "failed": failed}
    
    def get_statistics(self) -> dict:
        """Возвращает статистику для мониторинга"""
        return {
            "blocked_users_count": len(self.blocked_users),
            "error_counts": self.error_counts,
            "active_conversations": len(self.message_counters),
            "global_messages_last_second": len([
                ts for ts in self.global_message_counter
                if time.time() - ts < 1
            ])
        }


# Best Practices для избежания блокировки

class TelegramBestPractices:
    """
    Лучшие практики для работы с Telegram Bot API
    """
    
    @staticmethod
    def get_guidelines() -> List[str]:
        return [
            "✅ Используйте rate limiting (max 30 msg/sec)",
            "✅ Не отправляйте спам - только по запросу пользователя",
            "✅ Обрабатывайте ошибки 'user blocked bot'",
            "✅ Для рассылок используйте opt-in",
            "✅ Добавляйте кнопку 'Отписаться' в broadcast",
            "✅ Не храните большие файлы на серверах Telegram",
            "✅ Используйте webhook вместо polling для production",
            "✅ Валидируйте контент перед отправкой",
            "✅ Логируйте все ошибки API",
            "✅ Мониторьте здоровье бота (uptime, errors)"
        ]
    
    @staticmethod
    def check_message_safety(text: str) -> tuple[bool, str]:
        """
        Проверяет сообщение на безопасность
        Returns: (is_safe, reason)
        """
        # Check message length (max 4096 for text)
        if len(text) > 4096:
            return False, "Message too long (max 4096 characters)"
        
        # Check for suspicious patterns (spam indicators)
        spam_keywords = ["100% free", "click here now", "limited time"]
        text_lower = text.lower()
        
        for keyword in spam_keywords:
            if keyword in text_lower:
                return False, f"Spam keyword detected: {keyword}"
        
        # Check for too many URLs
        url_count = text.count("http://") + text.count("https://")
        if url_count > 3:
            return False, "Too many URLs (looks like spam)"
        
        return True, "OK"


# Emergency backup strategy

class BackupStrategy:
    """
    Стратегия восстановления при блокировке
    """
    
    @staticmethod
    def create_backup_plan() -> dict:
        return {
            "primary_bot_token": "current token",
            "backup_bot_token": "backup token (if available)",
            "database_backup": "daily backups enabled",
            "user_migration": "export/import user data",
            "notification_plan": "notify users about new bot via email/SMS"
        }
    
    @staticmethod
    def get_recovery_steps() -> List[str]:
        return [
            "1. Проверьте причину блокировки в Telegram Support",
            "2. Исправьте нарушение (если было)",
            "3. Подайте апелляцию через @BotSupport",
            "4. При необходимости создайте новый бот",
            "5. Восстановите данные из backup",
            "6. Уведомите пользователей о новом боте",
            "7. Реализуйте дополнительные меры защиты"
        ]
