"""
User Service
Сервис для управления пользователями - бизнес-логика работы с пользователями
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class UserService:
    """
    Сервис для управления пользователями
    Инкапсулирует бизнес-логику работы с пользователями
    """
    
    def __init__(self, user_repo, notification_service=None):
        """
        Инициализация сервиса
        
        Args:
            user_repo: UserRepository
            notification_service: NotificationService (опционально)
        """
        self.user_repo = user_repo
        self.notification_service = notification_service
    
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получить или создать пользователя
        
        Args:
            telegram_id: Telegram ID
            username: Username
            first_name: Имя
            
        Returns:
            User document
        """
        user = await self.user_repo.get_or_create_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
        return user
    
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить пользователя
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            User document или None
        """
        return await self.user_repo.find_by_telegram_id(telegram_id)
    
    async def is_user_blocked(self, telegram_id: int) -> bool:
        """
        Проверить, заблокирован ли пользователь
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            True если заблокирован
        """
        user = await self.user_repo.find_by_telegram_id(telegram_id)
        return user.get('blocked', False) if user else False
    
    async def block_user(
        self,
        telegram_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Заблокировать пользователя
        
        Args:
            telegram_id: Telegram ID
            reason: Причина блокировки
            
        Returns:
            True если заблокирован
        """
        try:
            result = await self.user_repo.block_user(telegram_id)
            
            if result and reason:
                # Добавить причину блокировки
                await self.user_repo.collection.update_one(
                    {'telegram_id': telegram_id},
                    {'$set': {
                        'block_reason': reason,
                        'blocked_at': datetime.now(timezone.utc).isoformat()
                    }}
                )
            
            if result:
                logger.info(f"🚫 User {telegram_id} blocked. Reason: {reason}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error blocking user: {e}")
            return False
    
    async def unblock_user(self, telegram_id: int) -> bool:
        """
        Разблокировать пользователя
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            True если разблокирован
        """
        try:
            result = await self.user_repo.unblock_user(telegram_id)
            
            if result:
                logger.info(f"✅ User {telegram_id} unblocked")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error unblocking user: {e}")
            return False
    
    async def get_balance(self, telegram_id: int) -> float:
        """
        Получить баланс пользователя
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            Баланс
        """
        return await self.user_repo.get_balance(telegram_id)
    
    async def add_balance(
        self,
        telegram_id: int,
        amount: float,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Пополнить баланс
        
        Args:
            telegram_id: Telegram ID
            amount: Сумма пополнения
            description: Описание операции
            
        Returns:
            Результат операции
        """
        try:
            if amount <= 0:
                return {
                    'success': False,
                    'error': 'Amount must be positive'
                }
            
            # Получить текущий баланс
            old_balance = await self.user_repo.get_balance(telegram_id)
            
            # Пополнить
            result = await self.user_repo.update_balance(
                telegram_id,
                amount,
                operation='add'
            )
            
            if result:
                new_balance = old_balance + amount
                
                logger.info(
                    f"💰 User {telegram_id} balance updated: "
                    f"${old_balance:.2f} → ${new_balance:.2f} (+${amount:.2f})"
                )
                
                # Отправить уведомление (если сервис доступен)
                if self.notification_service:
                    try:
                        await self.notification_service.send_balance_update(
                            telegram_id=telegram_id,
                            old_balance=old_balance,
                            new_balance=new_balance,
                            amount=amount,
                            operation='add'
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send balance notification: {e}")
                
                return {
                    'success': True,
                    'old_balance': old_balance,
                    'new_balance': new_balance,
                    'amount': amount
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to update balance'
                }
                
        except Exception as e:
            logger.error(f"❌ Error adding balance: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def deduct_balance(
        self,
        telegram_id: int,
        amount: float,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Списать с баланса
        
        Args:
            telegram_id: Telegram ID
            amount: Сумма списания
            description: Описание операции
            
        Returns:
            Результат операции
        """
        try:
            if amount <= 0:
                return {
                    'success': False,
                    'error': 'Amount must be positive'
                }
            
            # Проверить баланс
            current_balance = await self.user_repo.get_balance(telegram_id)
            
            if current_balance < amount:
                return {
                    'success': False,
                    'error': 'Insufficient balance',
                    'required': amount,
                    'available': current_balance
                }
            
            # Списать
            result = await self.user_repo.update_balance(
                telegram_id,
                amount,
                operation='subtract'
            )
            
            if result:
                new_balance = current_balance - amount
                
                logger.info(
                    f"💸 User {telegram_id} balance updated: "
                    f"${current_balance:.2f} → ${new_balance:.2f} (-${amount:.2f})"
                )
                
                # Отправить уведомление
                if self.notification_service:
                    try:
                        await self.notification_service.send_balance_update(
                            telegram_id=telegram_id,
                            old_balance=current_balance,
                            new_balance=new_balance,
                            amount=amount,
                            operation='subtract'
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send balance notification: {e}")
                
                return {
                    'success': True,
                    'old_balance': current_balance,
                    'new_balance': new_balance,
                    'amount': amount
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to update balance'
                }
                
        except Exception as e:
            logger.error(f"❌ Error deducting balance: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def set_discount(
        self,
        telegram_id: int,
        discount_percent: float
    ) -> bool:
        """
        Установить скидку пользователю
        
        Args:
            telegram_id: Telegram ID
            discount_percent: Процент скидки (0-100)
            
        Returns:
            True если установлено
        """
        try:
            if discount_percent < 0 or discount_percent > 100:
                raise ValueError("Discount must be between 0 and 100")
            
            result = await self.user_repo.update_user_field(
                telegram_id,
                'discount',
                discount_percent
            )
            
            if result:
                logger.info(f"💎 Discount {discount_percent}% set for user {telegram_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error setting discount: {e}")
            return False
    
    async def get_user_stats(self, telegram_id: int) -> Dict[str, Any]:
        """
        Получить статистику пользователя
        
        Args:
            telegram_id: Telegram ID
            
        Returns:
            Статистика пользователя
        """
        try:
            user = await self.user_repo.find_by_telegram_id(telegram_id)
            
            if not user:
                return {
                    'exists': False
                }
            
            return {
                'exists': True,
                'telegram_id': telegram_id,
                'username': user.get('username'),
                'first_name': user.get('first_name'),
                'balance': user.get('balance', 0.0),
                'discount': user.get('discount', 0.0),
                'blocked': user.get('blocked', False),
                'created_at': user.get('created_at'),
                'is_admin': user.get('is_admin', False)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting user stats: {e}")
            return {'exists': False, 'error': str(e)}


# ============================================================
# Factory function
# ============================================================

def create_user_service(user_repo, notification_service=None):
    """
    Создать UserService
    
    Args:
        user_repo: UserRepository
        notification_service: NotificationService (опционально)
        
    Returns:
        UserService instance
    """
    return UserService(user_repo, notification_service)
