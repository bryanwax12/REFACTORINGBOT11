"""
Payment Gateway - Unified Interface for All Payment Providers
Единый интерфейс для всех платежных систем (Oxapay, CryptoBot, и т.д.)
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Literal
from datetime import datetime, timezone
import logging
import httpx
from utils.retry_utils import retry_on_api_error

logger = logging.getLogger(__name__)

PaymentStatus = Literal["pending", "paid", "expired", "failed", "cancelled"]
PaymentProvider = Literal["oxapay", "cryptobot"]


class PaymentInvoice:
    """Унифицированная структура платежного инвойса"""
    
    def __init__(
        self,
        invoice_id: str,
        payment_url: str,
        amount: float,
        currency: str,
        status: PaymentStatus,
        provider: PaymentProvider,
        user_id: int,
        order_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        paid_at: Optional[datetime] = None,
        raw_data: Optional[Dict] = None
    ):
        self.invoice_id = invoice_id
        self.payment_url = payment_url
        self.amount = amount
        self.currency = currency
        self.status = status
        self.provider = provider
        self.user_id = user_id
        self.order_id = order_id
        self.expires_at = expires_at
        self.paid_at = paid_at
        self.raw_data = raw_data or {}
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict:
        """Конвертировать в словарь для БД"""
        return {
            'invoice_id': self.invoice_id,
            'payment_url': self.payment_url,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'provider': self.provider,
            'user_id': self.user_id,
            'order_id': self.order_id,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat(),
            'raw_data': self.raw_data
        }
    
    def is_paid(self) -> bool:
        """Проверка что инвойс оплачен"""
        return self.status == 'paid'
    
    def is_expired(self) -> bool:
        """Проверка что инвойс истёк"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class PaymentGateway(ABC):
    """
    Абстрактный базовый класс для всех платежных провайдеров
    
    Определяет единый интерфейс для:
    - Создания инвойсов
    - Проверки статуса платежа
    - Обработки webhook
    """
    
    def __init__(self, api_key: str, provider_name: PaymentProvider):
        self.api_key = api_key
        self.provider_name = provider_name
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    @abstractmethod
    async def create_invoice(
        self,
        amount: float,
        currency: str,
        user_id: int,
        order_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> PaymentInvoice:
        """
        Создать платежный инвойс
        
        Args:
            amount: Сумма платежа
            currency: Валюта (USD, USDT и т.д.)
            user_id: ID пользователя
            order_id: ID заказа (опционально)
            description: Описание платежа
            
        Returns:
            PaymentInvoice объект
        """
        pass
    
    @abstractmethod
    async def verify_payment(self, invoice_id: str) -> PaymentInvoice:
        """
        Проверить статус платежа
        
        Args:
            invoice_id: ID инвойса
            
        Returns:
            Обновленный PaymentInvoice объект
        """
        pass
    
    @abstractmethod
    async def verify_webhook(
        self,
        payload: Dict,
        signature: Optional[str] = None
    ) -> bool:
        """
        Верифицировать webhook от провайдера
        
        Args:
            payload: Данные webhook
            signature: Подпись (если используется)
            
        Returns:
            True если webhook валиден
        """
        pass
    
    @abstractmethod
    async def process_webhook(self, payload: Dict) -> Optional[PaymentInvoice]:
        """
        Обработать webhook и извлечь информацию о платеже
        
        Args:
            payload: Данные webhook
            
        Returns:
            PaymentInvoice если платеж обработан успешно
        """
        pass
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.aclose()


class OxapayGateway(PaymentGateway):
    """
    Платежный шлюз для Oxapay
    
    Документация: https://docs.oxapay.com/
    """
    
    BASE_URL = "https://api.oxapay.com"
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "oxapay")
        logger.info("🟢 Oxapay Gateway initialized")
    
    @with_retry(max_attempts=3, delay=1.0)
    async def create_invoice(
        self,
        amount: float,
        currency: str = "USDT",
        user_id: int = 0,
        order_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> PaymentInvoice:
        """Создать инвойс через Oxapay API"""
        
        # Подготовить данные
        payload = {
            "merchant": self.api_key,
            "amount": amount,
            "currency": currency,
            "orderId": order_id or f"user_{user_id}_{int(datetime.now().timestamp())}",
            "description": description or f"Payment for user {user_id}",
            "callbackUrl": None,  # Webhook URL устанавливается в админке Oxapay
            "returnUrl": None
        }
        
        logger.info(f"💳 Creating Oxapay invoice: {amount} {currency} for user {user_id}")
        
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/merchants/request",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            # Проверить результат
            if data.get('result') != 100:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"❌ Oxapay API error: {error_msg}")
                raise ValueError(f"Oxapay error: {error_msg}")
            
            # Создать PaymentInvoice
            invoice = PaymentInvoice(
                invoice_id=str(data['trackId']),
                payment_url=data['payLink'],
                amount=amount,
                currency=currency,
                status='pending',
                provider='oxapay',
                user_id=user_id,
                order_id=order_id,
                raw_data=data
            )
            
            logger.info(f"✅ Oxapay invoice created: {invoice.invoice_id}")
            return invoice
            
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error creating Oxapay invoice: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error creating Oxapay invoice: {e}")
            raise
    
    @with_retry(max_attempts=3, delay=1.0)
    async def verify_payment(self, invoice_id: str) -> PaymentInvoice:
        """Проверить статус платежа в Oxapay"""
        
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/merchants/inquiry",
                json={
                    "merchant": self.api_key,
                    "trackId": int(invoice_id)
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Маппинг статусов Oxapay на наши
            status_map = {
                'Waiting': 'pending',
                'Confirming': 'pending',
                'Paid': 'paid',
                'Expired': 'expired',
                'Failed': 'failed'
            }
            
            status = status_map.get(data.get('status'), 'pending')
            
            invoice = PaymentInvoice(
                invoice_id=invoice_id,
                payment_url=data.get('payLink', ''),
                amount=float(data.get('amount', 0)),
                currency=data.get('currency', 'USDT'),
                status=status,
                provider='oxapay',
                user_id=0,  # Не доступен из API
                raw_data=data
            )
            
            if status == 'paid' and data.get('date'):
                # Попытаться распарсить дату оплаты
                try:
                    invoice.paid_at = datetime.fromisoformat(data['date'])
                except:
                    invoice.paid_at = datetime.now(timezone.utc)
            
            return invoice
            
        except Exception as e:
            logger.error(f"❌ Error verifying Oxapay payment: {e}")
            raise
    
    async def verify_webhook(
        self,
        payload: Dict,
        signature: Optional[str] = None
    ) -> bool:
        """
        Верифицировать Oxapay webhook
        
        Note: Oxapay не использует подписи, верификация через API
        """
        # Oxapay не предоставляет подписи webhook
        # Верификация происходит через повторный запрос к API
        return True
    
    async def process_webhook(self, payload: Dict) -> Optional[PaymentInvoice]:
        """Обработать Oxapay webhook"""
        
        try:
            track_id = payload.get('trackId')
            if not track_id:
                logger.warning("⚠️ Oxapay webhook without trackId")
                return None
            
            # Верифицировать через API
            invoice = await self.verify_payment(str(track_id))
            
            logger.info(f"✅ Oxapay webhook processed: {track_id}, status: {invoice.status}")
            return invoice
            
        except Exception as e:
            logger.error(f"❌ Error processing Oxapay webhook: {e}")
            return None


class CryptoBotGateway(PaymentGateway):
    """
    Платежный шлюз для CryptoBot (@CryptoBot)
    
    Документация: https://help.crypt.bot/crypto-pay-api
    """
    
    BASE_URL = "https://pay.crypt.bot/api"
    
    def __init__(self, api_token: str):
        super().__init__(api_token, "cryptobot")
        self.api_token = api_token
        logger.info("🤖 CryptoBot Gateway initialized")
    
    @with_retry(max_attempts=3, delay=1.0)
    async def create_invoice(
        self,
        amount: float,
        currency: str = "USDT",
        user_id: int = 0,
        order_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> PaymentInvoice:
        """Создать инвойс через CryptoBot API"""
        
        # CryptoBot headers
        headers = {
            "Crypto-Pay-API-Token": self.api_token,
            "Content-Type": "application/json"
        }
        
        # Payload
        payload = {
            "amount": str(amount),
            "currency_type": "fiat",  # или "crypto"
            "fiat": currency if currency in ["USD", "EUR", "RUB"] else "USD",
            "description": description or f"Payment for user {user_id}",
            "paid_btn_name": "callback",
            "paid_btn_url": None
        }
        
        if order_id:
            payload["payload"] = order_id
        
        logger.info(f"🤖 Creating CryptoBot invoice: {amount} {currency} for user {user_id}")
        
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/createInvoice",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get('ok'):
                error = data.get('error', {})
                logger.error(f"❌ CryptoBot API error: {error}")
                raise ValueError(f"CryptoBot error: {error}")
            
            result = data['result']
            
            # Создать PaymentInvoice
            invoice = PaymentInvoice(
                invoice_id=str(result['invoice_id']),
                payment_url=result['pay_url'],
                amount=amount,
                currency=currency,
                status='pending',
                provider='cryptobot',
                user_id=user_id,
                order_id=order_id,
                raw_data=result
            )
            
            logger.info(f"✅ CryptoBot invoice created: {invoice.invoice_id}")
            return invoice
            
        except Exception as e:
            logger.error(f"❌ Error creating CryptoBot invoice: {e}")
            raise
    
    async def verify_payment(self, invoice_id: str) -> PaymentInvoice:
        """Проверить статус в CryptoBot"""
        
        headers = {
            "Crypto-Pay-API-Token": self.api_token
        }
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/getInvoices",
                headers=headers,
                params={"invoice_ids": invoice_id}
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get('ok') or not data.get('result', {}).get('items'):
                raise ValueError("Invoice not found")
            
            item = data['result']['items'][0]
            
            # Маппинг статусов
            status_map = {
                'active': 'pending',
                'paid': 'paid',
                'expired': 'expired'
            }
            
            status = status_map.get(item.get('status'), 'pending')
            
            invoice = PaymentInvoice(
                invoice_id=str(item['invoice_id']),
                payment_url=item.get('pay_url', ''),
                amount=float(item.get('amount', 0)),
                currency=item.get('asset', 'USDT'),
                status=status,
                provider='cryptobot',
                user_id=0,
                raw_data=item
            )
            
            if status == 'paid' and item.get('paid_at'):
                invoice.paid_at = datetime.fromtimestamp(item['paid_at'], tz=timezone.utc)
            
            return invoice
            
        except Exception as e:
            logger.error(f"❌ Error verifying CryptoBot payment: {e}")
            raise
    
    async def verify_webhook(
        self,
        payload: Dict,
        signature: Optional[str] = None
    ) -> bool:
        """Верифицировать CryptoBot webhook"""
        # CryptoBot использует HMAC подпись
        # TODO: Реализовать верификацию подписи
        return True
    
    async def process_webhook(self, payload: Dict) -> Optional[PaymentInvoice]:
        """Обработать CryptoBot webhook"""
        
        try:
            update_type = payload.get('update_type')
            
            if update_type == 'invoice_paid':
                invoice_data = payload.get('payload', {})
                invoice_id = str(invoice_data.get('invoice_id'))
                
                # Верифицировать через API
                invoice = await self.verify_payment(invoice_id)
                
                logger.info(f"✅ CryptoBot webhook processed: {invoice_id}")
                return invoice
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error processing CryptoBot webhook: {e}")
            return None


# ============================================================
# FACTORY для создания gateway
# ============================================================

class PaymentGatewayFactory:
    """Фабрика для создания платежных шлюзов"""
    
    @staticmethod
    def create_gateway(
        provider: PaymentProvider,
        api_key: Optional[str] = None
    ) -> PaymentGateway:
        """
        Создать gateway для указанного провайдера
        
        Args:
            provider: Имя провайдера ('oxapay' или 'cryptobot')
            api_key: API ключ (если None, берется из env)
            
        Returns:
            Экземпляр PaymentGateway
        """
        if provider == 'oxapay':
            if not api_key:
                from utils.api_config import get_oxapay_key
                api_key = get_oxapay_key()
            return OxapayGateway(api_key)
        
        elif provider == 'cryptobot':
            if not api_key:
                from utils.api_config import get_cryptobot_token
                api_key = get_cryptobot_token()
            return CryptoBotGateway(api_key)
        
        else:
            raise ValueError(f"Unknown payment provider: {provider}")
    
    @staticmethod
    def get_available_providers() -> list[PaymentProvider]:
        """Получить список доступных провайдеров"""
        from utils.api_config import get_api_config
        
        config = get_api_config()
        providers = []
        
        if config.is_oxapay_configured():
            providers.append('oxapay')
        
        if config.is_cryptobot_configured():
            providers.append('cryptobot')
        
        return providers


# ============================================================
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
# ============================================================

"""
ИСПОЛЬЗОВАНИЕ:
=============

1. Создание инвойса:
   ```python
   from services.payment_gateway import PaymentGatewayFactory
   
   # Создать gateway
   gateway = PaymentGatewayFactory.create_gateway('oxapay')
   
   # Создать инвойс
   invoice = await gateway.create_invoice(
       amount=50.0,
       currency='USDT',
       user_id=12345,
       order_id='order_123'
   )
   
   # Получить платежную ссылку
   payment_url = invoice.payment_url
   ```

2. Проверка статуса:
   ```python
   invoice = await gateway.verify_payment(invoice_id='123456')
   
   if invoice.is_paid():
       # Платеж получен
       pass
   ```

3. Обработка webhook:
   ```python
   # В webhook handler
   gateway = PaymentGatewayFactory.create_gateway('oxapay')
   invoice = await gateway.process_webhook(request_data)
   
   if invoice and invoice.is_paid():
       # Обработать оплату
       pass
   ```

4. Context manager:
   ```python
   async with PaymentGatewayFactory.create_gateway('oxapay') as gateway:
       invoice = await gateway.create_invoice(...)
       # Client автоматически закроется
   ```
"""
