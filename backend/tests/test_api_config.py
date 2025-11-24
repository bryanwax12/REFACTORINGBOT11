"""
Tests for API Configuration Manager
"""
import pytest
import os
from unittest.mock import patch
from utils.api_config import APIConfigManager


class TestAPIConfigManager:
    """Тесты для APIConfigManager"""
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key_123',
        'SHIPSTATION_API_KEY_PROD': 'prod_key_456',
        'OXAPAY_API_KEY': 'oxapay_789',
        'CRYPTOBOT_TOKEN': 'cryptobot_abc'
    })
    def test_initialization(self):
        """Тест инициализации менеджера"""
        manager = APIConfigManager()
        
        assert manager.shipstation_test_key == 'test_key_123'
        assert manager.shipstation_prod_key == 'prod_key_456'
        assert manager.oxapay_api_key == 'oxapay_789'
        assert manager.cryptobot_token == 'cryptobot_abc'
        assert manager._current_environment == 'production'
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key_123',
        'SHIPSTATION_API_KEY_PROD': 'prod_key_456'
    })
    def test_get_shipstation_key_production(self):
        """Тест получения production ключа ShipStation"""
        manager = APIConfigManager()
        manager.set_environment('production')
        
        key = manager.get_shipstation_key()
        assert key == 'prod_key_456'
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key_123',
        'SHIPSTATION_API_KEY_PROD': 'prod_key_456'
    })
    def test_get_shipstation_key_test(self):
        """Тест получения test ключа ShipStation"""
        manager = APIConfigManager()
        manager.set_environment('test')
        
        key = manager.get_shipstation_key()
        assert key == 'test_key_123'
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key_123',
        'SHIPSTATION_API_KEY_PROD': 'prod_key_456'
    })
    def test_get_shipstation_key_explicit_environment(self):
        """Тест получения ключа для явно указанного окружения"""
        manager = APIConfigManager()
        manager.set_environment('production')
        
        # Явно запросить test ключ
        test_key = manager.get_shipstation_key('test')
        assert test_key == 'test_key_123'
        
        # Явно запросить prod ключ
        prod_key = manager.get_shipstation_key('production')
        assert prod_key == 'prod_key_456'
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_DEFAULT': 'default_key'
    }, clear=True)
    def test_get_shipstation_key_fallback_to_default(self):
        """Тест fallback на default ключ"""
        # Установить только default ключ
        os.environ['SHIPSTATION_API_KEY'] = 'default_key'
        
        manager = APIConfigManager()
        key = manager.get_shipstation_key('test')
        assert key == 'default_key'
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_shipstation_key_not_configured(self):
        """Тест ошибки при отсутствии ключа"""
        manager = APIConfigManager()
        
        with pytest.raises(ValueError, match="ShipStation API key not configured"):
            manager.get_shipstation_key('test')
    
    @patch.dict(os.environ, {'OXAPAY_API_KEY': 'oxapay_key_123'})
    def test_get_oxapay_key(self):
        """Тест получения Oxapay ключа"""
        manager = APIConfigManager()
        
        key = manager.get_oxapay_key()
        assert key == 'oxapay_key_123'
    
    @patch.dict(os.environ, {'CRYPTOBOT_TOKEN': 'cryptobot_token_123'})
    def test_get_cryptobot_token(self):
        """Тест получения CryptoBot токена"""
        manager = APIConfigManager()
        
        token = manager.get_cryptobot_token()
        assert token == 'cryptobot_token_123'
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key',
        'SHIPSTATION_API_KEY_PROD': 'prod_key',
        'OXAPAY_API_KEY': 'oxapay_key',
        'CRYPTOBOT_TOKEN': 'cryptobot_token'
    })
    def test_configuration_checks(self):
        """Тест проверки конфигурации"""
        manager = APIConfigManager()
        
        assert manager.is_shipstation_configured('test')
        assert manager.is_shipstation_configured('production')
        assert manager.is_oxapay_configured()
        assert manager.is_cryptobot_configured()
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key',
        'SHIPSTATION_API_KEY_PROD': 'prod_key'
    })
    def test_get_shipstation_headers(self):
        """Тест получения headers для ShipStation"""
        manager = APIConfigManager()
        
        headers = manager.get_shipstation_headers('production')
        
        assert 'API-Key' in headers
        assert headers['API-Key'] == 'prod_key'
        assert headers['Content-Type'] == 'application/json'
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key_123',
        'SHIPSTATION_API_KEY_PROD': 'prod_key_456'
    })
    def test_environment_switching(self):
        """Тест переключения окружения"""
        manager = APIConfigManager()
        
        # По умолчанию production
        assert manager.get_current_environment() == 'production'
        assert manager.get_shipstation_key() == 'prod_key_456'
        
        # Переключить на test
        manager.set_environment('test')
        assert manager.get_current_environment() == 'test'
        assert manager.get_shipstation_key() == 'test_key_123'
        
        # Переключить обратно
        manager.set_environment('production')
        assert manager.get_current_environment() == 'production'
        assert manager.get_shipstation_key() == 'prod_key_456'
    
    def test_mask_key(self):
        """Тест маскирования ключа"""
        manager = APIConfigManager()
        
        # Длинный ключ
        masked = manager._mask_key('abcdefghijklmnopqrstuvwxyz', visible_chars=4)
        assert masked == 'abcd******************wxyz'
        
        # Короткий ключ
        masked_short = manager._mask_key('abc', visible_chars=4)
        assert masked_short == '***'
    
    @patch.dict(os.environ, {
        'SHIPSTATION_API_KEY_TEST': 'test_key',
        'SHIPSTATION_API_KEY_PROD': '',  # Explicitly clear prod key for test isolation
        'SHIPSTATION_API_KEY': '',  # Clear default key too
        'OXAPAY_API_KEY': 'oxapay_key'
    })
    def test_get_all_keys_status(self):
        """Тест получения статуса всех ключей"""
        manager = APIConfigManager()
        manager.set_environment('test')
        
        status = manager.get_all_keys_status()
        
        assert status['environment'] == 'test'
        assert status['shipstation']['test_configured']
        assert not status['shipstation']['prod_configured']
        assert status['oxapay']['configured']
    
    @patch.dict(os.environ, {'SHIPSTATION_API_KEY_TEST': 'cached_key'})
    def test_key_caching(self):
        """Тест кеширования ключей"""
        manager = APIConfigManager()
        manager.set_environment('test')
        
        # Первый вызов - кеш пустой
        key1 = manager.get_shipstation_key()
        assert 'shipstation_test' in manager._active_keys_cache
        
        # Второй вызов - из кеша
        key2 = manager.get_shipstation_key()
        assert key1 == key2
        
        # Смена окружения очищает кеш
        manager.set_environment('production')
        assert len(manager._active_keys_cache) == 0
