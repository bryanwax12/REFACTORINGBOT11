"""
Unit tests for Template Service
Tests all 8 functions in services/template_service.py
"""
import pytest
from unittest.mock import Mock, AsyncMock
from services.template_service import (
    get_user_templates,
    create_template,
    update_template_name,
    delete_template,
    load_template_to_context,
    validate_template_data
)


# ============================================================
# TEMPLATE CRUD TESTS
# ============================================================

@pytest.mark.asyncio
async def test_get_user_templates_success(sample_template):
    """Test getting user templates"""
    async def mock_find_templates(telegram_id, limit):
        return [sample_template]
    
    templates = await get_user_templates(
        telegram_id=123456789,
        find_user_templates_func=mock_find_templates,
        limit=10
    )
    
    assert len(templates) == 1
    assert templates[0]['id'] == sample_template['id']


@pytest.mark.asyncio
async def test_get_user_templates_empty():
    """Test getting templates when user has none"""
    async def mock_find_none(telegram_id, limit):
        return []
    
    templates = await get_user_templates(
        telegram_id=123456789,
        find_user_templates_func=mock_find_none
    )
    
    assert templates == []


@pytest.mark.asyncio
async def test_create_template_success(sample_order_data):
    """Test successful template creation"""
    async def mock_count(telegram_id):
        return 5  # Below limit
    
    async def mock_insert(data):
        assert 'id' in data
        assert data['name'] == 'My Template'
        assert data['from_name'] == sample_order_data['from_name']
    
    success, template_id, error = await create_template(
        telegram_id=123456789,
        template_name='My Template',
        order_data=sample_order_data,
        insert_template_func=mock_insert,
        count_user_templates_func=mock_count,
        max_templates=10
    )
    
    assert success is True
    assert template_id is not None
    assert error is None


@pytest.mark.asyncio
async def test_create_template_limit_reached():
    """Test template creation when limit is reached"""
    async def mock_count_max(telegram_id):
        return 10  # At limit
    
    async def mock_insert(data):
        pass
    
    success, template_id, error = await create_template(
        telegram_id=123456789,
        template_name='New Template',
        order_data={},
        insert_template_func=mock_insert,
        count_user_templates_func=mock_count_max,
        max_templates=10
    )
    
    assert success is False
    assert error is not None
    assert 'limit' in error.lower()


@pytest.mark.asyncio
async def test_create_template_empty_name():
    """Test template creation with empty name"""
    async def mock_count(telegram_id):
        return 5
    
    async def mock_insert(data):
        pass
    
    success, template_id, error = await create_template(
        telegram_id=123456789,
        template_name='',
        order_data={},
        insert_template_func=mock_insert,
        count_user_templates_func=mock_count
    )
    
    assert success is False
    assert 'empty' in error.lower()


@pytest.mark.asyncio
async def test_create_template_name_too_long():
    """Test template creation with name exceeding length limit"""
    async def mock_count(telegram_id):
        return 5
    
    async def mock_insert(data):
        pass
    
    long_name = 'A' * 60  # Over 50 char limit
    
    success, template_id, error = await create_template(
        telegram_id=123456789,
        template_name=long_name,
        order_data={},
        insert_template_func=mock_insert,
        count_user_templates_func=mock_count
    )
    
    assert success is False
    assert 'long' in error.lower()


@pytest.mark.asyncio
async def test_update_template_name_success():
    """Test successful template rename"""
    async def mock_update(template_id, data):
        assert 'name' in data
        assert data['name'] == 'New Name'
        assert 'updated_at' in data
    
    success, error = await update_template_name(
        template_id='template_123',
        new_name='New Name',
        update_template_func=mock_update
    )
    
    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_update_template_name_empty():
    """Test renaming with empty name"""
    async def mock_update(template_id, data):
        pass
    
    success, error = await update_template_name(
        template_id='template_123',
        new_name='   ',  # Whitespace only
        update_template_func=mock_update
    )
    
    assert success is False
    assert 'empty' in error.lower()


@pytest.mark.asyncio
async def test_delete_template_success(sample_template):
    """Test successful template deletion"""
    async def mock_find(template_id, projection):
        return sample_template
    
    async def mock_delete(template_id):
        pass
    
    success, template_name, error = await delete_template(
        template_id=sample_template['id'],
        telegram_id=sample_template['telegram_id'],
        find_template_func=mock_find,
        delete_template_func=mock_delete
    )
    
    assert success is True
    assert template_name == sample_template['name']
    assert error is None


@pytest.mark.asyncio
async def test_delete_template_not_found():
    """Test deleting non-existent template"""
    async def mock_find_none(template_id, projection):
        return None
    
    async def mock_delete(template_id):
        pass
    
    success, template_name, error = await delete_template(
        template_id='nonexistent',
        telegram_id=123456789,
        find_template_func=mock_find_none,
        delete_template_func=mock_delete
    )
    
    assert success is False
    assert error == "Template not found"


@pytest.mark.asyncio
async def test_delete_template_unauthorized(sample_template):
    """Test deleting template owned by another user"""
    async def mock_find(template_id, projection):
        return sample_template
    
    async def mock_delete(template_id):
        pass
    
    success, template_name, error = await delete_template(
        template_id=sample_template['id'],
        telegram_id=999999,  # Different user
        find_template_func=mock_find,
        delete_template_func=mock_delete
    )
    
    assert success is False
    assert 'unauthorized' in error.lower()


# ============================================================
# TEMPLATE USAGE TESTS
# ============================================================

@pytest.mark.asyncio
async def test_load_template_to_context_success(sample_template, mock_telegram_context):
    """Test loading template into context"""
    async def mock_find(template_id, projection):
        return sample_template
    
    success, error = await load_template_to_context(
        template_id=sample_template['id'],
        telegram_id=sample_template['telegram_id'],
        context=mock_telegram_context,
        find_template_func=mock_find
    )
    
    assert success is True
    assert error is None
    
    # Check that context was populated
    assert mock_telegram_context.user_data['from_name'] == sample_template['from_name']
    assert mock_telegram_context.user_data['to_city'] == sample_template['to_city']
    assert mock_telegram_context.user_data['weight'] == sample_template['weight']


@pytest.mark.asyncio
async def test_load_template_not_found(mock_telegram_context):
    """Test loading non-existent template"""
    async def mock_find_none(template_id, projection):
        return None
    
    success, error = await load_template_to_context(
        template_id='nonexistent',
        telegram_id=123456789,
        context=mock_telegram_context,
        find_template_func=mock_find_none
    )
    
    assert success is False
    assert error == "Template not found"


@pytest.mark.asyncio
async def test_load_template_unauthorized(sample_template, mock_telegram_context):
    """Test loading template owned by another user"""
    async def mock_find(template_id, projection):
        return sample_template
    
    success, error = await load_template_to_context(
        template_id=sample_template['id'],
        telegram_id=999999,  # Different user
        context=mock_telegram_context,
        find_template_func=mock_find
    )
    
    assert success is False
    assert 'unauthorized' in error.lower()


# ============================================================
# VALIDATION TESTS
# ============================================================

def test_validate_template_data_valid(sample_order_data):
    """Test validation with valid template data"""
    is_valid, error = validate_template_data(sample_order_data)
    
    assert is_valid is True
    assert error is None


def test_validate_template_data_missing_fields():
    """Test validation with missing required fields"""
    incomplete_data = {
        'from_name': 'John',
        'to_name': 'Jane',
        # Missing many required fields
    }
    
    is_valid, error = validate_template_data(incomplete_data)
    
    assert is_valid is False
    assert error is not None
    assert 'missing' in error.lower()


def test_validate_template_data_all_missing():
    """Test validation with all fields missing"""
    is_valid, error = validate_template_data({})
    
    assert is_valid is False
    assert len(error) > 0


# ============================================================
# INTEGRATION TESTS
# ============================================================

@pytest.mark.asyncio
async def test_full_template_lifecycle(sample_order_data, mock_telegram_context):
    """Test complete template lifecycle: create, load, update, delete"""
    created_template_id = None
    
    # 1. Validate data
    is_valid, error = validate_template_data(sample_order_data)
    assert is_valid
    
    # 2. Create template
    async def mock_count(telegram_id):
        return 5
    
    async def mock_insert(data):
        nonlocal created_template_id
        created_template_id = data['id']
    
    success, template_id, error = await create_template(
        telegram_id=123456789,
        template_name='Test Template',
        order_data=sample_order_data,
        insert_template_func=mock_insert,
        count_user_templates_func=mock_count
    )
    assert success
    assert template_id is not None
    
    # 3. Load template
    async def mock_find(tid, projection):
        if tid == template_id:
            return {
                'id': template_id,
                'telegram_id': 123456789,
                'name': 'Test Template',
                **{k.replace('_', '_', 1): v for k, v in sample_order_data.items()}
            }
        return None
    
    success, error = await load_template_to_context(
        template_id=template_id,
        telegram_id=123456789,
        context=mock_telegram_context,
        find_template_func=mock_find
    )
    assert success
    
    # 4. Update name
    async def mock_update(tid, data):
        assert tid == template_id
    
    success, error = await update_template_name(
        template_id=template_id,
        new_name='Updated Template',
        update_template_func=mock_update
    )
    assert success
    
    # 5. Delete
    async def mock_delete(tid):
        assert tid == template_id
    
    success, name, error = await delete_template(
        template_id=template_id,
        telegram_id=123456789,
        find_template_func=mock_find,
        delete_template_func=mock_delete
    )
    assert success


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
