"""
Order Service
Сервис для управления заказами - бизнес-логика работы с заказами
"""
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)


class OrderService:
    """
    Сервис для управления заказами
    Инкапсулирует всю бизнес-логику работы с заказами
    """
    
    def __init__(self, order_repo, user_repo, payment_repo):
        """
        Инициализация сервиса
        
        Args:
            order_repo: OrderRepository
            user_repo: UserRepository
            payment_repo: PaymentRepository
        """
        self.order_repo = order_repo
        self.user_repo = user_repo
        self.payment_repo = payment_repo
    
    async def create_order(
        self,
        telegram_id: int,
        order_data: Dict[str, Any],
        selected_rate: Dict[str, Any],
        discount_percent: float = 0.0,
        discount_amount: float = 0.0
    ) -> Dict[str, Any]:
        """
        Создать новый заказ
        
        Args:
            telegram_id: Telegram ID пользователя
            order_data: Данные заказа (адреса, посылка)
            selected_rate: Выбранный тариф доставки
            discount_percent: Процент скидки
            discount_amount: Сумма скидки
            
        Returns:
            Созданный заказ
        """
        try:
            # Проверить существование пользователя
            user = await self.user_repo.find_by_telegram_id(telegram_id)
            if not user:
                raise ValueError(f"User {telegram_id} not found")
            
            # Создать ID заказа
            order_id = str(uuid4())
            
            # Подготовить данные заказа
            order_dict = {
                'id': order_id,
                'telegram_id': telegram_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'pending',
                'payment_status': 'pending',
                'shipping_status': 'pending',
                
                # Данные доставки
                'selected_carrier': selected_rate['carrier'],
                'selected_service': selected_rate['service'],
                'selected_service_code': selected_rate.get('service_code', ''),
                'rate_id': selected_rate['rate_id'],
                
                # Финансы
                'amount': selected_rate['amount'],
                'original_amount': selected_rate.get('original_amount', selected_rate['amount']),
                'markup': selected_rate.get('amount', 0) - selected_rate.get('original_amount', 0),
                'discount_percent': discount_percent,
                'discount_amount': discount_amount,
                
                # Адреса
                'address_from': order_data.get('address_from', {}),
                'address_to': order_data.get('address_to', {}),
                
                # Посылка
                'parcel': order_data.get('parcel', {}),
            }
            
            # Сохранить в БД
            await self.order_repo.collection.insert_one(order_dict)
            
            logger.info(f"✅ Order {order_id} created for user {telegram_id}")
            return order_dict
            
        except Exception as e:
            logger.error(f"❌ Error creating order: {e}")
            raise
    
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить заказ по ID
        
        Args:
            order_id: UUID заказа
            
        Returns:
            Заказ или None
        """
        return await self.order_repo.find_by_id(order_id)
    
    async def update_order_status(
        self,
        order_id: str,
        status: str,
        payment_status: Optional[str] = None,
        shipping_status: Optional[str] = None
    ) -> bool:
        """
        Обновить статус заказа
        
        Args:
            order_id: UUID заказа
            status: Новый статус
            payment_status: Статус оплаты (опционально)
            shipping_status: Статус доставки (опционально)
            
        Returns:
            True если обновлено
        """
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            if payment_status:
                update_data['payment_status'] = payment_status
            
            if shipping_status:
                update_data['shipping_status'] = shipping_status
            
            result = await self.order_repo.update_by_id(order_id, update_data)
            
            if result:
                logger.info(f"✅ Order {order_id} status updated: {status}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error updating order status: {e}")
            return False
    
    async def process_payment(
        self,
        order_id: str,
        telegram_id: int,
        payment_method: str = 'balance'
    ) -> Dict[str, Any]:
        """
        Обработать оплату заказа
        
        Args:
            order_id: UUID заказа
            telegram_id: Telegram ID пользователя
            payment_method: Метод оплаты (balance, crypto)
            
        Returns:
            Результат обработки платежа
        """
        try:
            # Получить заказ
            order = await self.order_repo.find_by_id(order_id)
            if not order:
                return {
                    'success': False,
                    'error': 'Order not found'
                }
            
            amount = order['amount']
            
            if payment_method == 'balance':
                # Оплата с баланса
                user_balance = await self.user_repo.get_balance(telegram_id)
                
                if user_balance < amount:
                    return {
                        'success': False,
                        'error': 'Insufficient balance',
                        'required': amount,
                        'available': user_balance
                    }
                
                # Списать с баланса
                success = await self.user_repo.update_balance(
                    telegram_id,
                    amount,
                    operation='subtract'
                )
                
                if success:
                    # Обновить статус заказа
                    await self.update_order_status(
                        order_id,
                        status='paid',
                        payment_status='paid'
                    )
                    
                    logger.info(f"✅ Order {order_id} paid from balance")
                    return {
                        'success': True,
                        'payment_method': 'balance',
                        'amount': amount
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to deduct balance'
                    }
            
            else:
                # Для crypto платежей - возвращаем необходимость создания инвойса
                return {
                    'success': False,
                    'error': 'Crypto payment not implemented in service yet',
                    'requires_invoice': True
                }
                
        except Exception as e:
            logger.error(f"❌ Error processing payment: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def cancel_order(
        self,
        order_id: str,
        telegram_id: int,
        reason: str = "User cancelled"
    ) -> Dict[str, Any]:
        """
        Отменить заказ
        
        Args:
            order_id: UUID заказа
            telegram_id: Telegram ID пользователя
            reason: Причина отмены
            
        Returns:
            Результат отмены
        """
        try:
            # Получить заказ
            order = await self.order_repo.find_by_id(order_id)
            if not order:
                return {
                    'success': False,
                    'error': 'Order not found'
                }
            
            # Проверить владельца
            if order['telegram_id'] != telegram_id:
                return {
                    'success': False,
                    'error': 'Not authorized'
                }
            
            # Если заказ оплачен, вернуть деньги
            refund_amount = 0
            if order.get('payment_status') == 'paid':
                amount = order['amount']
                await self.user_repo.update_balance(
                    telegram_id,
                    amount,
                    operation='add'
                )
                refund_amount = amount
                logger.info(f"💰 Refunded ${amount} to user {telegram_id}")
            
            # Обновить статус
            await self.update_order_status(
                order_id,
                status='cancelled',
                payment_status='refunded' if refund_amount > 0 else 'cancelled',
                shipping_status='cancelled'
            )
            
            # Добавить информацию об отмене
            await self.order_repo.update_by_id(order_id, {
                'cancellation_reason': reason,
                'cancelled_at': datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"✅ Order {order_id} cancelled")
            return {
                'success': True,
                'refunded': refund_amount > 0,
                'refund_amount': refund_amount
            }
            
        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_user_orders(
        self,
        telegram_id: int,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить заказы пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            limit: Максимальное количество
            status: Фильтр по статусу (опционально)
            
        Returns:
            Список заказов
        """
        try:
            filter_dict = {'telegram_id': telegram_id}
            if status:
                filter_dict['status'] = status
            
            orders = await self.order_repo.find_with_filter(
                filter_dict,
                limit=limit
            )
            
            return orders
            
        except Exception as e:
            logger.error(f"❌ Error getting user orders: {e}")
            return []
    
    async def add_tracking_info(
        self,
        order_id: str,
        tracking_number: str,
        carrier: str,
        label_id: Optional[str] = None
    ) -> bool:
        """
        Добавить tracking информацию к заказу
        
        Args:
            order_id: UUID заказа
            tracking_number: Tracking номер
            carrier: Перевозчик
            label_id: ID ярлыка (опционально)
            
        Returns:
            True если добавлено
        """
        try:
            update_data = {
                'tracking_number': tracking_number,
                'carrier': carrier,
                'shipping_status': 'label_created',
                'label_created_at': datetime.now(timezone.utc).isoformat()
            }
            
            if label_id:
                update_data['label_id'] = label_id
            
            result = await self.order_repo.update_by_id(order_id, update_data)
            
            if result:
                logger.info(f"✅ Tracking info added to order {order_id}: {tracking_number}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error adding tracking info: {e}")
            return False


# ============================================================
# Factory function для удобного создания сервиса
# ============================================================

def create_order_service(repositories):
    """
    Создать OrderService с repository dependencies
    
    Args:
        repositories: RepositoryManager
        
    Returns:
        OrderService instance
    """
    return OrderService(
        order_repo=repositories.orders,
        user_repo=repositories.users,
        payment_repo=repositories.payments
    )
