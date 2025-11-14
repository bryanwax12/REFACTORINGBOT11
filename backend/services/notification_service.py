"""
Notification Service
Централизованный сервис для всех уведомлений (Telegram, Email, SMS и т.д.)
"""
from typing import Optional, Dict, List, Union
from telegram import Bot
from telegram.error import TelegramError
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class NotificationTemplate:
    """Шаблоны сообщений для уведомлений"""
    
    # User notifications
    BALANCE_ADDED = """
💰 *Баланс пополнен*

Сумма: `${amount}`
Новый баланс: `${new_balance}`

Спасибо за пополнение!
"""
    
    ORDER_CREATED = """
📦 *Новый заказ создан*

Order ID: `{order_id}`
Стоимость: `${cost}`

Статус: В обработке
Ожидайте обновлений!
"""
    
    ORDER_PAID = """
✅ *Заказ оплачен*

Order ID: `{order_id}`
Оплачено: `${amount}`

Ваш заказ будет обработан в ближайшее время.
"""
    
    ORDER_SHIPPED = """
🚚 *Заказ отправлен*

Order ID: `{order_id}`
Трекинг: `{tracking_number}`
Перевозчик: {carrier}

Отследить: {tracking_url}
"""
    
    ORDER_COMPLETED = """
✨ *Заказ завершен*

Order ID: `{order_id}`

Спасибо за использование нашего сервиса!
Будем рады видеть вас снова.
"""
    
    PAYMENT_RECEIVED = """
💳 *Платеж получен*

Сумма: `${amount}`
Invoice: `{invoice_id}`

Баланс обновлен автоматически.
"""
    
    # Admin notifications
    ADMIN_NEW_ORDER = """
🔔 *Новый заказ*

User: {user_name} (ID: {user_id})
Order ID: `{order_id}`
Стоимость: `${cost}`

Создан: {created_at}
"""
    
    ADMIN_PAYMENT_RECEIVED = """
💰 *Новый платеж*

User: {user_name} (ID: {user_id})
Сумма: `${amount}`
Provider: {provider}

Invoice: `{invoice_id}`
"""
    
    ADMIN_ERROR = """
⚠️ *Системная ошибка*

Компонент: {component}
Ошибка: `{error}`

Время: {timestamp}
"""
    
    ADMIN_LOW_BALANCE = """
⚠️ *Низкий баланс пользователя*

User: {user_name} (ID: {user_id})
Баланс: `${balance}`

Пользователь пытался создать заказ на `${order_cost}`
"""


class NotificationService:
    """
    Централизованный сервис уведомлений
    
    Управляет всеми типами уведомлений:
    - Telegram сообщения
    - Email (в будущем)
    - SMS (в будущем)
    - Push notifications (в будущем)
    """
    
    def __init__(self, bot: Optional[Bot] = None, admin_id: Optional[int] = None):
        """
        Инициализация сервиса
        
        Args:
            bot: Telegram Bot instance
            admin_id: Telegram ID админа для уведомлений
        """
        self.bot = bot
        self.admin_id = admin_id
        self.sent_count = 0
        self.error_count = 0
        
        logger.info("📬 Notification Service initialized")
    
    def set_bot(self, bot: Bot):
        """Установить Telegram bot"""
        self.bot = bot
    
    def set_admin_id(self, admin_id: int):
        """Установить admin ID"""
        self.admin_id = admin_id
    
    async def _send_telegram(
        self,
        user_id: int,
        message: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True
    ) -> bool:
        """
        Отправить Telegram сообщение
        
        Args:
            user_id: Telegram ID получателя
            message: Текст сообщения
            parse_mode: Режим парсинга (Markdown или HTML)
            disable_web_page_preview: Отключить превью ссылок
            
        Returns:
            True если отправлено успешно
        """
        if not self.bot:
            logger.error("❌ Telegram bot not configured")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
            
            self.sent_count += 1
            logger.info(f"✅ Notification sent to {user_id}")
            return True
            
        except TelegramError as e:
            self.error_count += 1
            logger.error(f"❌ Failed to send notification to {user_id}: {e}")
            return False
        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ Unexpected error sending notification: {e}")
            return False
    
    # ============================================================
    # USER NOTIFICATIONS
    # ============================================================
    
    async def notify_balance_added(
        self,
        user_id: int,
        amount: float,
        new_balance: float
    ) -> bool:
        """
        Уведомить пользователя о пополнении баланса
        
        Args:
            user_id: Telegram ID
            amount: Сумма пополнения
            new_balance: Новый баланс
            
        Returns:
            True если отправлено
        """
        message = NotificationTemplate.BALANCE_ADDED.format(
            amount=f"{amount:.2f}",
            new_balance=f"{new_balance:.2f}"
        )
        
        return await self._send_telegram(user_id, message)
    
    async def notify_order_created(
        self,
        user_id: int,
        order_id: str,
        cost: float
    ) -> bool:
        """
        Уведомить о создании заказа
        
        Args:
            user_id: Telegram ID
            order_id: ID заказа
            cost: Стоимость
            
        Returns:
            True если отправлено
        """
        message = NotificationTemplate.ORDER_CREATED.format(
            order_id=order_id,
            cost=f"{cost:.2f}"
        )
        
        return await self._send_telegram(user_id, message)
    
    async def notify_order_paid(
        self,
        user_id: int,
        order_id: str,
        amount: float
    ) -> bool:
        """
        Уведомить об оплате заказа
        
        Args:
            user_id: Telegram ID
            order_id: ID заказа
            amount: Сумма оплаты
            
        Returns:
            True если отправлено
        """
        message = NotificationTemplate.ORDER_PAID.format(
            order_id=order_id,
            amount=f"{amount:.2f}"
        )
        
        return await self._send_telegram(user_id, message)
    
    async def notify_order_shipped(
        self,
        user_id: int,
        order_id: str,
        tracking_number: str,
        carrier: str = "USPS",
        tracking_url: Optional[str] = None
    ) -> bool:
        """
        Уведомить об отправке заказа
        
        Args:
            user_id: Telegram ID
            order_id: ID заказа
            tracking_number: Номер трекинга
            carrier: Перевозчик
            tracking_url: URL для отслеживания
            
        Returns:
            True если отправлено
        """
        if not tracking_url:
            tracking_url = f"https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}"
        
        message = NotificationTemplate.ORDER_SHIPPED.format(
            order_id=order_id,
            tracking_number=tracking_number,
            carrier=carrier,
            tracking_url=tracking_url
        )
        
        return await self._send_telegram(user_id, message)
    
    async def notify_order_completed(
        self,
        user_id: int,
        order_id: str
    ) -> bool:
        """
        Уведомить о завершении заказа
        
        Args:
            user_id: Telegram ID
            order_id: ID заказа
            
        Returns:
            True если отправлено
        """
        message = NotificationTemplate.ORDER_COMPLETED.format(
            order_id=order_id
        )
        
        return await self._send_telegram(user_id, message)
    
    async def notify_payment_received(
        self,
        user_id: int,
        amount: float,
        invoice_id: str
    ) -> bool:
        """
        Уведомить о получении платежа
        
        Args:
            user_id: Telegram ID
            amount: Сумма платежа
            invoice_id: ID инвойса
            
        Returns:
            True если отправлено
        """
        message = NotificationTemplate.PAYMENT_RECEIVED.format(
            amount=f"{amount:.2f}",
            invoice_id=invoice_id
        )
        
        return await self._send_telegram(user_id, message)
    
    async def notify_custom(
        self,
        user_id: int,
        message: str,
        parse_mode: str = "Markdown"
    ) -> bool:
        """
        Отправить кастомное уведомление
        
        Args:
            user_id: Telegram ID
            message: Текст сообщения
            parse_mode: Режим парсинга
            
        Returns:
            True если отправлено
        """
        return await self._send_telegram(user_id, message, parse_mode=parse_mode)
    
    # ============================================================
    # ADMIN NOTIFICATIONS
    # ============================================================
    
    async def notify_admin_new_order(
        self,
        user_id: int,
        user_name: str,
        order_id: str,
        cost: float
    ) -> bool:
        """
        Уведомить админа о новом заказе
        
        Args:
            user_id: Telegram ID пользователя
            user_name: Имя пользователя
            order_id: ID заказа
            cost: Стоимость
            
        Returns:
            True если отправлено
        """
        if not self.admin_id:
            logger.warning("⚠️ Admin ID not configured")
            return False
        
        message = NotificationTemplate.ADMIN_NEW_ORDER.format(
            user_name=user_name,
            user_id=user_id,
            order_id=order_id,
            cost=f"{cost:.2f}",
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        
        return await self._send_telegram(self.admin_id, message)
    
    async def notify_admin_payment(
        self,
        user_id: int,
        user_name: str,
        amount: float,
        provider: str,
        invoice_id: str
    ) -> bool:
        """
        Уведомить админа о новом платеже
        
        Args:
            user_id: Telegram ID пользователя
            user_name: Имя пользователя
            amount: Сумма
            provider: Платежный провайдер
            invoice_id: ID инвойса
            
        Returns:
            True если отправлено
        """
        if not self.admin_id:
            return False
        
        message = NotificationTemplate.ADMIN_PAYMENT_RECEIVED.format(
            user_name=user_name,
            user_id=user_id,
            amount=f"{amount:.2f}",
            provider=provider,
            invoice_id=invoice_id
        )
        
        return await self._send_telegram(self.admin_id, message)
    
    async def notify_admin_error(
        self,
        component: str,
        error: str
    ) -> bool:
        """
        Уведомить админа об ошибке
        
        Args:
            component: Компонент где произошла ошибка
            error: Описание ошибки
            
        Returns:
            True если отправлено
        """
        if not self.admin_id:
            return False
        
        message = NotificationTemplate.ADMIN_ERROR.format(
            component=component,
            error=error[:200],  # Ограничить длину
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        
        return await self._send_telegram(self.admin_id, message)
    
    async def notify_admin_low_balance(
        self,
        user_id: int,
        user_name: str,
        balance: float,
        order_cost: float
    ) -> bool:
        """
        Уведомить админа о попытке создать заказ при низком балансе
        
        Args:
            user_id: Telegram ID пользователя
            user_name: Имя пользователя
            balance: Текущий баланс
            order_cost: Стоимость заказа
            
        Returns:
            True если отправлено
        """
        if not self.admin_id:
            return False
        
        message = NotificationTemplate.ADMIN_LOW_BALANCE.format(
            user_name=user_name,
            user_id=user_id,
            balance=f"{balance:.2f}",
            order_cost=f"{order_cost:.2f}"
        )
        
        return await self._send_telegram(self.admin_id, message)
    
    async def notify_admin_custom(
        self,
        message: str,
        parse_mode: str = "Markdown"
    ) -> bool:
        """
        Отправить кастомное уведомление админу
        
        Args:
            message: Текст сообщения
            parse_mode: Режим парсинга
            
        Returns:
            True если отправлено
        """
        if not self.admin_id:
            return False
        
        return await self._send_telegram(self.admin_id, message, parse_mode=parse_mode)
    
    # ============================================================
    # BROADCAST NOTIFICATIONS
    # ============================================================
    
    async def broadcast_to_users(
        self,
        user_ids: List[int],
        message: str,
        parse_mode: str = "Markdown"
    ) -> Dict[str, int]:
        """
        Отправить сообщение нескольким пользователям
        
        Args:
            user_ids: Список Telegram ID
            message: Текст сообщения
            parse_mode: Режим парсинга
            
        Returns:
            Статистика отправки {'sent': N, 'failed': M}
        """
        stats = {'sent': 0, 'failed': 0}
        
        for user_id in user_ids:
            success = await self._send_telegram(user_id, message, parse_mode=parse_mode)
            
            if success:
                stats['sent'] += 1
            else:
                stats['failed'] += 1
        
        logger.info(f"📊 Broadcast complete: {stats}")
        
        return stats
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> Dict:
        """
        Получить статистику сервиса
        
        Returns:
            Статистика отправок
        """
        return {
            'total_sent': self.sent_count,
            'total_errors': self.error_count,
            'success_rate': f"{(self.sent_count / (self.sent_count + self.error_count) * 100):.1f}%" if (self.sent_count + self.error_count) > 0 else "0%",
            'bot_configured': self.bot is not None,
            'admin_configured': self.admin_id is not None
        }
    
    def reset_stats(self):
        """Сбросить статистику"""
        self.sent_count = 0
        self.error_count = 0
        logger.info("📊 Statistics reset")


# ============================================================
# GLOBAL INSTANCE
# ============================================================

_notification_service: Optional[NotificationService] = None


def init_notification_service(bot: Optional[Bot] = None, admin_id: Optional[int] = None) -> NotificationService:
    """
    Инициализировать Notification Service
    
    Args:
        bot: Telegram Bot instance
        admin_id: Admin Telegram ID
        
    Returns:
        NotificationService instance
    """
    global _notification_service
    
    _notification_service = NotificationService(bot=bot, admin_id=admin_id)
    
    return _notification_service


def get_notification_service() -> NotificationService:
    """
    Получить глобальный экземпляр Notification Service
    
    Returns:
        NotificationService instance
        
    Raises:
        RuntimeError: Если сервис не инициализирован
    """
    if _notification_service is None:
        raise RuntimeError("Notification service not initialized. Call init_notification_service() first.")
    
    return _notification_service


"""
ИСПОЛЬЗОВАНИЕ:
=============

1. Инициализация в server.py:
   ```python
   from services.notification_service import init_notification_service
   
   @app.on_event("startup")
   async def startup():
       # Инициализировать сервис
       init_notification_service(
           bot=bot_instance,
           admin_id=int(os.environ.get('ADMIN_TELEGRAM_ID'))
       )
   ```

2. В handlers:
   ```python
   from services.notification_service import get_notification_service
   
   async def handle_payment(user_id, amount):
       notifier = get_notification_service()
       
       # Уведомить пользователя
       await notifier.notify_payment_received(user_id, amount, "INV123")
       
       # Уведомить админа
       await notifier.notify_admin_payment(
           user_id, "John", amount, "Oxapay", "INV123"
       )
   ```

3. Broadcast:
   ```python
   notifier = get_notification_service()
   
   user_ids = [123, 456, 789]
   stats = await notifier.broadcast_to_users(
       user_ids,
       "🎉 Новая функция доступна!"
   )
   print(f"Sent to {stats['sent']} users")
   ```

ПРЕИМУЩЕСТВА:
=============

- ✅ Централизованное управление всеми уведомлениями
- ✅ Единый формат сообщений (шаблоны)
- ✅ Легко добавлять новые типы уведомлений
- ✅ Статистика отправок
- ✅ Error handling из коробки
- ✅ Broadcast функциональность
- ✅ Легко добавить Email/SMS в будущем
"""
