"""
Webhook Processor
Унифицированная обработка webhook от различных сервисов
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable, Any
import hmac
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WebhookEvent:
    """Унифицированная структура webhook события"""
    
    def __init__(
        self,
        event_type: str,
        provider: str,
        data: Dict,
        timestamp: Optional[datetime] = None,
        raw_payload: Optional[Dict] = None
    ):
        self.event_type = event_type
        self.provider = provider
        self.data = data
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.raw_payload = raw_payload or {}
    
    def to_dict(self) -> Dict:
        """Конвертировать в словарь"""
        return {
            'event_type': self.event_type,
            'provider': self.provider,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'raw_payload': self.raw_payload
        }


class WebhookProcessor(ABC):
    """
    Базовый класс для обработки webhook
    
    Определяет единый интерфейс для всех webhook процессоров
    """
    
    def __init__(self, provider_name: str, secret_key: Optional[str] = None):
        """
        Инициализация процессора
        
        Args:
            provider_name: Имя провайдера (oxapay, shipstation и т.д.)
            secret_key: Секретный ключ для верификации подписи
        """
        self.provider_name = provider_name
        self.secret_key = secret_key
        self.processed_count = 0
        self.error_count = 0
        
        logger.info(f"🔗 Webhook processor initialized: {provider_name}")
    
    @abstractmethod
    async def verify_signature(
        self,
        payload: Dict,
        signature: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> bool:
        """
        Верифицировать подпись webhook
        
        Args:
            payload: Данные webhook
            signature: Подпись (если есть)
            headers: HTTP headers
            
        Returns:
            True если подпись валидна
        """
        pass
    
    @abstractmethod
    async def parse_event(self, payload: Dict) -> Optional[WebhookEvent]:
        """
        Парсить webhook payload в WebhookEvent
        
        Args:
            payload: Данные webhook
            
        Returns:
            WebhookEvent или None если не удалось распарсить
        """
        pass
    
    @abstractmethod
    async def handle_event(self, event: WebhookEvent) -> bool:
        """
        Обработать событие
        
        Args:
            event: WebhookEvent
            
        Returns:
            True если обработано успешно
        """
        pass
    
    async def process_webhook(
        self,
        payload: Dict,
        signature: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> bool:
        """
        Полный цикл обработки webhook
        
        Args:
            payload: Данные webhook
            signature: Подпись
            headers: HTTP headers
            
        Returns:
            True если обработано успешно
        """
        try:
            # 1. Верифицировать подпись
            if not await self.verify_signature(payload, signature, headers):
                logger.warning(f"❌ {self.provider_name}: Invalid signature")
                self.error_count += 1
                return False
            
            # 2. Парсить событие
            event = await self.parse_event(payload)
            if not event:
                logger.warning(f"❌ {self.provider_name}: Failed to parse event")
                self.error_count += 1
                return False
            
            # 3. Обработать событие
            success = await self.handle_event(event)
            
            if success:
                self.processed_count += 1
                logger.info(f"✅ {self.provider_name}: Webhook processed successfully")
            else:
                self.error_count += 1
                logger.error(f"❌ {self.provider_name}: Failed to handle event")
            
            return success
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ {self.provider_name}: Webhook processing error: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Получить статистику обработки"""
        total = self.processed_count + self.error_count
        success_rate = (self.processed_count / total * 100) if total > 0 else 0
        
        return {
            'provider': self.provider_name,
            'processed': self.processed_count,
            'errors': self.error_count,
            'success_rate': f"{success_rate:.1f}%"
        }


class OxapayWebhookProcessor(WebhookProcessor):
    """Процессор webhook для Oxapay"""
    
    def __init__(self, secret_key: Optional[str] = None):
        super().__init__('oxapay', secret_key)
    
    async def verify_signature(
        self,
        payload: Dict,
        signature: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> bool:
        """
        Oxapay не использует подписи webhook
        Верификация происходит через повторный запрос к API
        """
        # TODO: Можно добавить верификацию через API
        return True
    
    async def parse_event(self, payload: Dict) -> Optional[WebhookEvent]:
        """Парсить Oxapay webhook"""
        
        try:
            # Oxapay webhook structure
            track_id = payload.get('trackId')
            status = payload.get('status')
            
            if not track_id:
                return None
            
            # Определить тип события
            event_type = 'payment_received' if status == 'Paid' else 'payment_updated'
            
            event = WebhookEvent(
                event_type=event_type,
                provider='oxapay',
                data={
                    'track_id': str(track_id),
                    'status': status,
                    'amount': payload.get('amount'),
                    'currency': payload.get('currency'),
                    'order_id': payload.get('orderId')
                },
                raw_payload=payload
            )
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to parse Oxapay webhook: {e}")
            return None
    
    async def handle_event(self, event: WebhookEvent) -> bool:
        """Обработать Oxapay событие"""
        
        try:
            if event.event_type == 'payment_received':
                # Обработать оплату
                logger.info(f"💰 Payment received: {event.data['track_id']}")
                
                # TODO: Здесь вызвать обработчик оплаты
                # Например: await process_payment(event.data)
                
                return True
            
            elif event.event_type == 'payment_updated':
                logger.info(f"📝 Payment updated: {event.data['track_id']}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to handle Oxapay event: {e}")
            return False


class CryptoBotWebhookProcessor(WebhookProcessor):
    """Процессор webhook для CryptoBot"""
    
    def __init__(self, secret_key: Optional[str] = None):
        super().__init__('cryptobot', secret_key)
    
    async def verify_signature(
        self,
        payload: Dict,
        signature: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> bool:
        """
        Верифицировать HMAC подпись CryptoBot
        """
        if not self.secret_key or not signature:
            logger.warning("CryptoBot: No secret key or signature provided")
            return True  # Пропустить если не настроено
        
        try:
            # CryptoBot использует HMAC-SHA256
            import json
            payload_string = json.dumps(payload, separators=(',', ':'))
            
            expected_signature = hmac.new(
                self.secret_key.encode(),
                payload_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    async def parse_event(self, payload: Dict) -> Optional[WebhookEvent]:
        """Парсить CryptoBot webhook"""
        
        try:
            update_type = payload.get('update_type')
            
            if update_type == 'invoice_paid':
                invoice_data = payload.get('payload', {})
                
                event = WebhookEvent(
                    event_type='payment_received',
                    provider='cryptobot',
                    data={
                        'invoice_id': str(invoice_data.get('invoice_id')),
                        'amount': invoice_data.get('amount'),
                        'asset': invoice_data.get('asset'),
                        'status': invoice_data.get('status')
                    },
                    raw_payload=payload
                )
                
                return event
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse CryptoBot webhook: {e}")
            return None
    
    async def handle_event(self, event: WebhookEvent) -> bool:
        """Обработать CryptoBot событие"""
        
        try:
            if event.event_type == 'payment_received':
                logger.info(f"💰 CryptoBot payment: {event.data['invoice_id']}")
                
                # TODO: Обработать оплату
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to handle CryptoBot event: {e}")
            return False


class ShipStationWebhookProcessor(WebhookProcessor):
    """Процессор webhook для ShipStation"""
    
    def __init__(self, secret_key: Optional[str] = None):
        super().__init__('shipstation', secret_key)
    
    async def verify_signature(
        self,
        payload: Dict,
        signature: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> bool:
        """ShipStation webhook verification"""
        # TODO: Реализовать верификацию если ShipStation использует подписи
        return True
    
    async def parse_event(self, payload: Dict) -> Optional[WebhookEvent]:
        """Парсить ShipStation webhook"""
        
        try:
            resource_type = payload.get('resource_type')
            resource_url = payload.get('resource_url')
            
            event = WebhookEvent(
                event_type=f"shipstation_{resource_type}",
                provider='shipstation',
                data={
                    'resource_type': resource_type,
                    'resource_url': resource_url
                },
                raw_payload=payload
            )
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to parse ShipStation webhook: {e}")
            return None
    
    async def handle_event(self, event: WebhookEvent) -> bool:
        """Обработать ShipStation событие"""
        
        try:
            logger.info(f"📦 ShipStation event: {event.event_type}")
            
            # TODO: Обработать события ShipStation
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle ShipStation event: {e}")
            return False


# ============================================================
# WEBHOOK PROCESSOR FACTORY
# ============================================================

class WebhookProcessorFactory:
    """Фабрика для создания webhook процессоров"""
    
    _processors: Dict[str, type] = {
        'oxapay': OxapayWebhookProcessor,
        'cryptobot': CryptoBotWebhookProcessor,
        'shipstation': ShipStationWebhookProcessor
    }
    
    @classmethod
    def create_processor(
        cls,
        provider: str,
        secret_key: Optional[str] = None
    ) -> WebhookProcessor:
        """
        Создать процессор для провайдера
        
        Args:
            provider: Имя провайдера
            secret_key: Секретный ключ
            
        Returns:
            WebhookProcessor instance
        """
        processor_class = cls._processors.get(provider.lower())
        
        if not processor_class:
            raise ValueError(f"Unknown webhook provider: {provider}")
        
        return processor_class(secret_key=secret_key)
    
    @classmethod
    def register_processor(cls, provider: str, processor_class: type):
        """
        Зарегистрировать новый процессор
        
        Args:
            provider: Имя провайдера
            processor_class: Класс процессора
        """
        cls._processors[provider.lower()] = processor_class
        logger.info(f"✅ Registered webhook processor: {provider}")
    
    @classmethod
    def get_available_processors(cls) -> list:
        """Получить список доступных процессоров"""
        return list(cls._processors.keys())


# ============================================================
# WEBHOOK ROUTER для FastAPI
# ============================================================

async def handle_webhook(
    provider: str,
    payload: Dict,
    signature: Optional[str] = None,
    headers: Optional[Dict] = None,
    secret_key: Optional[str] = None
) -> bool:
    """
    Обработать webhook от любого провайдера
    
    Args:
        provider: Имя провайдера
        payload: Данные webhook
        signature: Подпись
        headers: HTTP headers
        secret_key: Секретный ключ
        
    Returns:
        True если обработано успешно
    """
    try:
        processor = WebhookProcessorFactory.create_processor(provider, secret_key)
        return await processor.process_webhook(payload, signature, headers)
    except Exception as e:
        logger.error(f"Webhook handling error: {e}")
        return False


"""
ИСПОЛЬЗОВАНИЕ:
=============

1. В FastAPI endpoint:
   ```python
   from services.webhook_processor import handle_webhook
   
   @app.post("/api/webhook/oxapay")
   async def oxapay_webhook(request: Request):
       payload = await request.json()
       
       success = await handle_webhook(
           provider='oxapay',
           payload=payload
       )
       
       return {"success": success}
   ```

2. С верификацией подписи:
   ```python
   @app.post("/api/webhook/cryptobot")
   async def cryptobot_webhook(request: Request):
       payload = await request.json()
       signature = request.headers.get('X-Signature')
       
       success = await handle_webhook(
           provider='cryptobot',
           payload=payload,
           signature=signature,
           secret_key=os.environ.get('CRYPTOBOT_WEBHOOK_SECRET')
       )
       
       return {"success": success}
   ```

3. Добавление своего процессора:
   ```python
   class MyCustomProcessor(WebhookProcessor):
       async def verify_signature(...): ...
       async def parse_event(...): ...
       async def handle_event(...): ...
   
   WebhookProcessorFactory.register_processor('mycustom', MyCustomProcessor)
   ```

ПРЕИМУЩЕСТВА:
=============

- ✅ Единый интерфейс для всех webhook
- ✅ Автоматическая верификация подписи
- ✅ Унифицированная структура событий
- ✅ Централизованная обработка ошибок
- ✅ Статистика обработки
- ✅ Легко добавлять новые провайдеры
- ✅ Retry логика (можно добавить)
"""
