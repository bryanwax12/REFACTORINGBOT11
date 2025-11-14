"""
Tests for Payment Gateway
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from services.payment_gateway import (
    PaymentInvoice,
    OxapayGateway,
    CryptoBotGateway,
    PaymentGatewayFactory
)


class TestPaymentInvoice:
    """Тесты для PaymentInvoice"""
    
    def test_invoice_creation(self):
        """Тест создания инвойса"""
        invoice = PaymentInvoice(
            invoice_id='123',
            payment_url='https://pay.example.com/123',
            amount=50.0,
            currency='USDT',
            status='pending',
            provider='oxapay',
            user_id=12345
        )
        
        assert invoice.invoice_id == '123'
        assert invoice.amount == 50.0
        assert invoice.status == 'pending'
        assert invoice.provider == 'oxapay'
    
    def test_invoice_to_dict(self):
        """Тест конвертации в словарь"""
        invoice = PaymentInvoice(
            invoice_id='123',
            payment_url='https://pay.example.com/123',
            amount=50.0,
            currency='USDT',
            status='pending',
            provider='oxapay',
            user_id=12345
        )
        
        data = invoice.to_dict()
        
        assert data['invoice_id'] == '123'
        assert data['amount'] == 50.0
        assert data['provider'] == 'oxapay'
        assert 'created_at' in data
    
    def test_is_paid(self):
        """Тест проверки оплаты"""
        invoice_paid = PaymentInvoice(
            invoice_id='123',
            payment_url='https://pay.example.com/123',
            amount=50.0,
            currency='USDT',
            status='paid',
            provider='oxapay',
            user_id=12345
        )
        
        invoice_pending = PaymentInvoice(
            invoice_id='124',
            payment_url='https://pay.example.com/124',
            amount=50.0,
            currency='USDT',
            status='pending',
            provider='oxapay',
            user_id=12345
        )
        
        assert invoice_paid.is_paid() == True
        assert invoice_pending.is_paid() == False


class TestOxapayGateway:
    """Тесты для OxapayGateway"""
    
    @pytest_asyncio.fixture
    async def gateway(self):
        """Фикстура для gateway"""
        gateway = OxapayGateway(api_key='test_key_123')
        yield gateway
        await gateway.close()
    
    @pytest.mark.asyncio
    async def test_create_invoice_success(self, gateway):
        """Тест успешного создания инвойса"""
        
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': 100,
            'trackId': 192105324,
            'payLink': 'https://pay.oxapay.com/123'
        }
        
        with patch.object(gateway.client, 'post', return_value=mock_response) as mock_post:
            mock_post.return_value = mock_response
            
            invoice = await gateway.create_invoice(
                amount=50.0,
                currency='USDT',
                user_id=12345
            )
            
            assert invoice.invoice_id == '192105324'
            assert invoice.amount == 50.0
            assert invoice.currency == 'USDT'
            assert invoice.status == 'pending'
            assert invoice.provider == 'oxapay'
    
    @pytest.mark.asyncio
    async def test_create_invoice_error(self, gateway):
        """Тест ошибки создания инвойса"""
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result': 400,
            'message': 'Invalid amount'
        }
        
        with patch.object(gateway.client, 'post', return_value=mock_response):
            with pytest.raises(ValueError, match="Oxapay error"):
                await gateway.create_invoice(amount=-10.0, user_id=12345)
    
    @pytest.mark.asyncio
    async def test_verify_payment(self, gateway):
        """Тест верификации платежа"""
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'status': 'Paid',
            'amount': 50.0,
            'currency': 'USDT',
            'payLink': 'https://pay.oxapay.com/123'
        }
        
        with patch.object(gateway.client, 'post', return_value=mock_response):
            invoice = await gateway.verify_payment('192105324')
            
            assert invoice.status == 'paid'
            assert invoice.amount == 50.0


class TestCryptoBotGateway:
    """Тесты для CryptoBotGateway"""
    
    @pytest_asyncio.fixture
    async def gateway(self):
        """Фикстура для gateway"""
        gateway = CryptoBotGateway(api_token='test_token_123')
        yield gateway
        await gateway.close()
    
    @pytest.mark.asyncio
    async def test_create_invoice_success(self, gateway):
        """Тест создания инвойса через CryptoBot"""
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'ok': True,
            'result': {
                'invoice_id': 123456,
                'pay_url': 'https://t.me/CryptoBot?start=pay_123'
            }
        }
        
        with patch.object(gateway.client, 'post', return_value=mock_response):
            invoice = await gateway.create_invoice(
                amount=50.0,
                currency='USDT',
                user_id=12345
            )
            
            assert invoice.invoice_id == '123456'
            assert invoice.provider == 'cryptobot'
            assert invoice.status == 'pending'


class TestPaymentGatewayFactory:
    """Тесты для PaymentGatewayFactory"""
    
    def test_create_oxapay_gateway(self):
        """Тест создания Oxapay gateway"""
        gateway = PaymentGatewayFactory.create_gateway('oxapay', api_key='test_key')
        
        assert isinstance(gateway, OxapayGateway)
        assert gateway.provider_name == 'oxapay'
    
    def test_create_cryptobot_gateway(self):
        """Тест создания CryptoBot gateway"""
        gateway = PaymentGatewayFactory.create_gateway('cryptobot', api_key='test_token')
        
        assert isinstance(gateway, CryptoBotGateway)
        assert gateway.provider_name == 'cryptobot'
    
    def test_invalid_provider(self):
        """Тест создания с неверным провайдером"""
        with pytest.raises(ValueError, match="Unknown payment provider"):
            PaymentGatewayFactory.create_gateway('invalid_provider')
