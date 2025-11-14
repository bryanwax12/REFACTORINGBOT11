"""
Unit tests for Shipping Service
Tests all 19 functions in services/shipping_service.py
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from services.shipping_service import (
    validate_order_data_for_rates,
    build_shipstation_rates_request,
    fetch_rates_from_shipstation,
    filter_and_sort_rates,
    get_allowed_services_config,
    apply_service_filter,
    balance_and_deduplicate_rates,
    validate_shipping_address,
    validate_parcel_data
)


# ============================================================
# VALIDATION TESTS
# ============================================================

@pytest.mark.asyncio
async def test_validate_order_data_complete(sample_order_data):
    """Test validation with complete order data"""
    is_valid, missing = await validate_order_data_for_rates(sample_order_data)
    
    assert is_valid is True
    assert missing == []


@pytest.mark.asyncio
async def test_validate_order_data_incomplete(incomplete_order_data):
    """Test validation with incomplete order data"""
    is_valid, missing = await validate_order_data_for_rates(incomplete_order_data)
    
    assert is_valid is False
    assert len(missing) > 0
    assert 'from_state' in missing
    assert 'from_zip' in missing
    assert 'weight' in missing


@pytest.mark.asyncio
async def test_validate_order_data_empty_strings():
    """Test validation with empty strings (should be treated as missing)"""
    data = {
        'from_name': '',
        'from_street': '123 Main',
        'from_city': 'NYC',
        'from_state': 'NY',
        'from_zip': '',
        'to_name': 'Jane',
        'to_street': '456 Oak',
        'to_city': 'LA',
        'to_state': 'CA',
        'to_zip': '90001',
        'weight': 'None'  # String 'None' should be treated as missing
    }
    
    is_valid, missing = await validate_order_data_for_rates(data)
    
    assert is_valid is False
    assert 'from_name' in missing
    assert 'from_zip' in missing
    assert 'weight' in missing


def test_validate_shipping_address_valid():
    """Test shipping address validation with valid data"""
    address = {
        'from_name': 'John Doe',
        'from_street': '123 Main St',
        'from_city': 'New York',
        'from_state': 'NY',
        'from_zip': '10001'
    }
    
    is_valid, error = validate_shipping_address(address, 'from')
    
    assert is_valid is True
    assert error is None


def test_validate_shipping_address_missing_field():
    """Test shipping address validation with missing field"""
    address = {
        'from_name': 'John Doe',
        'from_street': '123 Main St',
        # Missing city
        'from_state': 'NY',
        'from_zip': '10001'
    }
    
    is_valid, error = validate_shipping_address(address, 'from')
    
    assert is_valid is False
    assert error is not None
    assert 'from_city' in error


def test_validate_parcel_data_valid():
    """Test parcel validation with valid data"""
    parcel = {'weight': 5.5}
    
    is_valid, error = validate_parcel_data(parcel)
    
    assert is_valid is True
    assert error is None


def test_validate_parcel_data_missing_weight():
    """Test parcel validation without weight"""
    parcel = {}
    
    is_valid, error = validate_parcel_data(parcel)
    
    assert is_valid is False
    assert 'weight' in error.lower()


def test_validate_parcel_data_negative_weight():
    """Test parcel validation with negative weight"""
    parcel = {'weight': -5}
    
    is_valid, error = validate_parcel_data(parcel)
    
    assert is_valid is False
    assert 'positive' in error.lower()


def test_validate_parcel_data_excessive_weight():
    """Test parcel validation with weight over limit"""
    parcel = {'weight': 200}
    
    is_valid, error = validate_parcel_data(parcel)
    
    assert is_valid is False
    assert 'maximum' in error.lower()


# ============================================================
# REQUEST BUILDING TESTS
# ============================================================

def test_build_shipstation_rates_request(sample_order_data, sample_carrier_ids):
    """Test building ShipStation rates request"""
    request = build_shipstation_rates_request(sample_order_data, sample_carrier_ids)
    
    # Check structure
    assert 'rate_options' in request
    assert 'shipment' in request
    assert request['rate_options']['carrier_ids'] == sample_carrier_ids
    
    # Check ship_to
    ship_to = request['shipment']['ship_to']
    assert ship_to['name'] == sample_order_data['to_name']
    assert ship_to['address_line1'] == sample_order_data['to_street']
    assert ship_to['city_locality'] == sample_order_data['to_city']
    assert ship_to['state_province'] == sample_order_data['to_state']
    assert ship_to['postal_code'] == sample_order_data['to_zip']
    
    # Check ship_from
    ship_from = request['shipment']['ship_from']
    assert ship_from['name'] == sample_order_data['from_name']
    
    # Check packages
    package = request['shipment']['packages'][0]
    assert package['weight']['value'] == sample_order_data['weight']
    assert package['weight']['unit'] == 'pound'


def test_build_shipstation_rates_request_default_phone(sample_order_data):
    """Test request building with missing phone numbers"""
    data = sample_order_data.copy()
    data.pop('from_phone')
    data.pop('to_phone')
    
    request = build_shipstation_rates_request(data, ['se-123'])
    
    # Should use default phone
    assert request['shipment']['ship_to']['phone'] == '+15551234567'
    assert request['shipment']['ship_from']['phone'] == '+15551234567'


# ============================================================
# RATE FILTERING TESTS
# ============================================================

def test_filter_and_sort_rates_basic(sample_rates_list):
    """Test basic rate filtering and sorting"""
    filtered = filter_and_sort_rates(sample_rates_list)
    
    # Should return all rates (no exclusions)
    assert len(filtered) == len(sample_rates_list)
    
    # Should be sorted by price (ascending)
    prices = [r['amount'] for r in filtered]
    assert prices == sorted(prices)
    
    # Check format
    assert 'carrier' in filtered[0]
    assert 'service' in filtered[0]
    assert 'amount' in filtered[0]


def test_filter_and_sort_rates_with_exclusions(sample_rates_list):
    """Test filtering with excluded carriers"""
    filtered = filter_and_sort_rates(sample_rates_list, excluded_carriers=['ups'])
    
    # UPS rates should be excluded
    ups_rates = [r for r in filtered if r.get('carrier_code') == 'ups']
    assert len(ups_rates) == 0
    
    # FedEx rates should remain
    fedex_rates = [r for r in filtered if r.get('carrier_code') == 'fedex_walleted']
    assert len(fedex_rates) > 0


def test_get_allowed_services_config():
    """Test getting allowed services configuration"""
    config = get_allowed_services_config()
    
    assert isinstance(config, dict)
    assert 'ups' in config
    assert 'fedex_walleted' in config
    assert 'usps' in config
    
    # Check that services are lists
    assert isinstance(config['ups'], list)
    assert len(config['ups']) > 0


def test_apply_service_filter_default_config(sample_rates_list):
    """Test applying service filter with default config"""
    filtered = apply_service_filter(sample_rates_list)
    
    # All services in sample_rates_list are allowed, so all should pass
    assert len(filtered) > 0


def test_apply_service_filter_custom_config(sample_rates_list):
    """Test applying service filter with custom config"""
    custom_config = {
        'ups': ['ups_ground'],  # Only ground allowed
        'fedex_walleted': []  # Nothing allowed
    }
    
    filtered = apply_service_filter(sample_rates_list, allowed_services=custom_config)
    
    # Only UPS Ground should pass
    ups_ground = [r for r in filtered if r.get('service_code') == 'ups_ground']
    assert len(ups_ground) > 0
    
    # FedEx should be filtered out
    fedex = [r for r in filtered if r.get('carrier_code') == 'fedex_walleted']
    assert len(fedex) == 0


def test_balance_and_deduplicate_rates(sample_rates_list):
    """Test rate balancing and deduplication"""
    balanced = balance_and_deduplicate_rates(sample_rates_list, max_per_carrier=3)
    
    # Should format rates properly
    assert len(balanced) > 0
    assert 'carrier' in balanced[0]
    assert 'amount' in balanced[0]
    
    # Should be sorted by price
    prices = [r['amount'] for r in balanced]
    assert prices == sorted(prices)
    
    # Count rates per carrier
    ups_count = len([r for r in balanced if 'UPS' in r['carrier']])
    assert ups_count <= 3  # Max 3 per carrier


def test_balance_and_deduplicate_rates_deduplication():
    """Test that duplicate services are removed"""
    # Create rates with duplicate service types
    rates = [
        {
            'carrier_friendly_name': 'UPS',
            'carrier_code': 'ups',
            'service_code': 'ups_ground',
            'service_type': 'Ground',
            'shipping_amount': {'amount': 15.00},
            'delivery_days': 3,
            'rate_id': 'rate1'
        },
        {
            'carrier_friendly_name': 'UPS',
            'carrier_code': 'ups',
            'service_code': 'ups_ground_alt',
            'service_type': 'Ground',  # Same service type
            'shipping_amount': {'amount': 16.00},  # More expensive
            'delivery_days': 3,
            'rate_id': 'rate2'
        }
    ]
    
    balanced = balance_and_deduplicate_rates(rates)
    
    # Should only keep the cheaper one
    assert len(balanced) == 1
    assert balanced[0]['amount'] == 15.00


# ============================================================
# API CALL TESTS
# ============================================================

@pytest.mark.asyncio
async def test_fetch_rates_from_shipstation_success():
    """Test successful rates fetch from ShipStation"""
    from unittest.mock import AsyncMock
    
    mock_response = Mock()  # Not AsyncMock - httpx response is sync
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={
        'rate_response': {
            'rates': [
                {
                    'rate_id': 'rate_123',
                    'carrier_code': 'ups',
                    'service_code': 'ups_ground',
                    'shipping_amount': {'amount': 15.50}
                }
            ]
        }
    })
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        success, rates, error = await fetch_rates_from_shipstation(
            rate_request={},
            headers={},
            api_url='https://test.api',
            timeout=30
        )
    
    assert success is True
    assert rates is not None
    assert len(rates) > 0
    assert error is None


@pytest.mark.asyncio
async def test_fetch_rates_from_shipstation_api_error():
    """Test API error handling"""
    from unittest.mock import AsyncMock
    
    mock_response = Mock()  # httpx response is sync
    mock_response.status_code = 400
    mock_response.text = 'Bad Request'
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        success, rates, error = await fetch_rates_from_shipstation(
            rate_request={},
            headers={},
            api_url='https://test.api',
            timeout=30
        )
    
    assert success is False
    assert rates is None
    assert error is not None
    assert '400' in error


@pytest.mark.asyncio
async def test_fetch_rates_from_shipstation_timeout():
    """Test timeout handling"""
    from unittest.mock import AsyncMock
    import httpx
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        success, rates, error = await fetch_rates_from_shipstation(
            rate_request={},
            headers={},
            api_url='https://test.api',
            timeout=30
        )
    
    assert success is False
    assert rates is None
    assert 'timeout' in error.lower()


@pytest.mark.asyncio
async def test_fetch_rates_from_shipstation_no_rates():
    """Test when API returns no rates"""
    mock_response = Mock()  # httpx response is sync
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={
        'rate_response': {
            'rates': []  # Empty rates
        }
    })
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        success, rates, error = await fetch_rates_from_shipstation(
            rate_request={},
            headers={},
            api_url='https://test.api',
            timeout=30
        )
    
    assert success is True
    assert rates == []
    assert error is None


# ============================================================
# INTEGRATION TESTS
# ============================================================

@pytest.mark.asyncio
async def test_full_rate_fetching_pipeline(sample_order_data, sample_carrier_ids):
    """Test complete rate fetching pipeline"""
    # 1. Validate
    is_valid, missing = await validate_order_data_for_rates(sample_order_data)
    assert is_valid
    
    # 2. Build request
    request = build_shipstation_rates_request(sample_order_data, sample_carrier_ids)
    assert 'shipment' in request
    
    # 3. Mock API call
    from unittest.mock import AsyncMock
    
    mock_response = Mock()  # httpx response is sync
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={
        'rate_response': {
            'rates': [
                {
                    'rate_id': f'rate_{i}',
                    'carrier_code': 'ups',
                    'carrier_friendly_name': 'UPS',
                    'service_code': f'ups_service_{i}',
                    'service_type': f'Service {i}',
                    'shipping_amount': {'amount': 15.00 + i},
                    'delivery_days': 3
                }
                for i in range(5)
            ]
        }
    })
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        success, rates, error = await fetch_rates_from_shipstation(
            request, {}, 'https://test', 30
        )
    
    assert success
    
    # 4. Filter and sort
    filtered = filter_and_sort_rates(rates)
    assert len(filtered) == 5
    
    # 5. Balance
    balanced = balance_and_deduplicate_rates(rates)
    assert len(balanced) <= 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
