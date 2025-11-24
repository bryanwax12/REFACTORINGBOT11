"""
Template Service Module
Handles all template-related operations including CRUD and template usage
"""
import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ============================================================
# TEMPLATE CRUD OPERATIONS
# ============================================================

async def get_user_templates(
    telegram_id: int,
    find_user_templates_func,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get all templates for a user
    
    Args:
        telegram_id: Telegram user ID
        find_user_templates_func: Function to find templates
        limit: Maximum number of templates to return
    
    Returns:
        List of template dictionaries
    """
    try:
        templates = await find_user_templates_func(telegram_id, limit=limit)
        logger.info(f"📋 Retrieved {len(templates)} templates for user {telegram_id}")
        return templates
    except Exception as e:
        logger.error(f"❌ Error retrieving templates: {e}")
        return []


async def create_template(
    telegram_id: int,
    template_name: str,
    order_data: Dict[str, Any],
    insert_template_func,
    count_user_templates_func,
    max_templates: int = 10
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Create a new template from order data
    
    Args:
        telegram_id: Telegram user ID
        template_name: Name for the template
        order_data: Order data to save
        insert_template_func: Function to insert template
        count_user_templates_func: Function to count templates
        max_templates: Maximum templates per user
    
    Returns:
        (success, template_id, error_message)
    """
    try:
        # Check template limit
        template_count = await count_user_templates_func(telegram_id)
        if template_count >= max_templates:
            return False, None, f"Maximum template limit reached ({max_templates})"
        
        # Validate template name
        if not template_name or len(template_name.strip()) == 0:
            return False, None, "Template name cannot be empty"
        
        if len(template_name) > 50:
            return False, None, "Template name too long (max 50 characters)"
        
        # Create template dict
        from uuid import uuid4
        template_id = str(uuid4())
        
        template_dict = {
            'id': template_id,
            'telegram_id': telegram_id,
            'name': template_name.strip(),
            'from_name': order_data.get('from_name', ''),
            'from_street1': order_data.get('from_address', ''),  # Fixed: from_address instead of from_street
            'from_street2': order_data.get('from_address2', ''),
            'from_city': order_data.get('from_city', ''),
            'from_state': order_data.get('from_state', ''),
            'from_zip': order_data.get('from_zip', ''),
            'from_phone': order_data.get('from_phone', ''),
            'to_name': order_data.get('to_name', ''),
            'to_street1': order_data.get('to_address', ''),  # Fixed: to_address instead of to_street
            'to_street2': order_data.get('to_address2', ''),
            'to_city': order_data.get('to_city', ''),
            'to_state': order_data.get('to_state', ''),
            'to_zip': order_data.get('to_zip', ''),
            'to_phone': order_data.get('to_phone', ''),
            'weight': order_data.get('weight', ''),
            'length': order_data.get('length', ''),
            'width': order_data.get('width', ''),
            'height': order_data.get('height', ''),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        # Insert template
        await insert_template_func(template_dict)
        
        logger.info(f"✅ Template created: id={template_id}, name={template_name}, user={telegram_id}")
        return True, template_id, None
        
    except Exception as e:
        logger.error(f"❌ Error creating template: {e}")
        return False, None, str(e)


async def update_template_name(
    template_id: str,
    new_name: str,
    update_template_func
) -> Tuple[bool, Optional[str]]:
    """
    Update template name
    
    Args:
        template_id: Template ID
        new_name: New name for template
        update_template_func: Function to update template
    
    Returns:
        (success, error_message)
    """
    try:
        # Validate new name
        if not new_name or len(new_name.strip()) == 0:
            return False, "Template name cannot be empty"
        
        if len(new_name) > 50:
            return False, "Template name too long (max 50 characters)"
        
        # Update template
        await update_template_func(
            template_id,
            {
                'name': new_name.strip(),
                'updated_at': datetime.now(timezone.utc)
            }
        )
        
        logger.info(f"✅ Template renamed: id={template_id}, new_name={new_name}")
        return True, None
        
    except Exception as e:
        logger.error(f"❌ Error renaming template: {e}")
        return False, str(e)


async def delete_template(
    template_id: str,
    telegram_id: int,
    find_template_func,
    delete_template_func
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Delete a template
    
    Args:
        template_id: Template ID
        telegram_id: Telegram user ID (for authorization)
        find_template_func: Function to find template
        delete_template_func: Function to delete template
    
    Returns:
        (success, template_name, error_message)
    """
    try:
        # Verify template exists and belongs to user
        template = await find_template_func(template_id, projection={'_id': 0})
        
        if not template:
            return False, None, "Template not found"
        
        if template.get('telegram_id') != telegram_id:
            return False, None, "Unauthorized: Template belongs to another user"
        
        template_name = template.get('name', 'Unknown')
        
        # Delete template
        await delete_template_func(template_id)
        
        logger.info(f"🗑 Template deleted: id={template_id}, name={template_name}, user={telegram_id}")
        return True, template_name, None
        
    except Exception as e:
        logger.error(f"❌ Error deleting template: {e}")
        return False, None, str(e)


# ============================================================
# TEMPLATE USAGE
# ============================================================

async def load_template_to_context(
    template_id: str,
    telegram_id: int,
    context,
    find_template_func
) -> Tuple[bool, Optional[str]]:
    """
    Load template data into conversation context
    
    Args:
        template_id: Template ID
        telegram_id: Telegram user ID (for authorization)
        context: Telegram context to load data into
        find_template_func: Function to find template
    
    Returns:
        (success, error_message)
    """
    try:
        # Get template
        template = await find_template_func(template_id, projection={'_id': 0})
        
        if not template:
            return False, "Template not found"
        
        if template.get('telegram_id') != telegram_id:
            return False, "Unauthorized: Template belongs to another user"
        
        # Load data into context
        context.user_data['from_name'] = template.get('from_name', '')
        context.user_data['from_street'] = template.get('from_street1', '')
        context.user_data['from_street2'] = template.get('from_street2', '')
        context.user_data['from_city'] = template.get('from_city', '')
        context.user_data['from_state'] = template.get('from_state', '')
        context.user_data['from_zip'] = template.get('from_zip', '')
        context.user_data['from_phone'] = template.get('from_phone', '')
        
        context.user_data['to_name'] = template.get('to_name', '')
        context.user_data['to_street'] = template.get('to_street1', '')
        context.user_data['to_street2'] = template.get('to_street2', '')
        context.user_data['to_city'] = template.get('to_city', '')
        context.user_data['to_state'] = template.get('to_state', '')
        context.user_data['to_zip'] = template.get('to_zip', '')
        context.user_data['to_phone'] = template.get('to_phone', '')
        
        context.user_data['weight'] = template.get('weight', '')
        context.user_data['length'] = template.get('length', '10')
        context.user_data['width'] = template.get('width', '10')
        context.user_data['height'] = template.get('height', '10')
        
        logger.info(f"📋 Template loaded: id={template_id}, user={telegram_id}")
        return True, None
        
    except Exception as e:
        logger.error(f"❌ Error loading template: {e}")
        return False, str(e)


def format_template_for_display(template: Dict[str, Any]) -> str:
    """
    Format template data for display
    
    Args:
        template: Template dictionary
    
    Returns:
        Formatted string
    """
    from utils.ui_utils import TemplateManagementUI
    return TemplateManagementUI.format_template_item(1, template)


# ============================================================
# VALIDATION
# ============================================================

def validate_template_data(order_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate order data before saving as template
    
    Args:
        order_data: Order data to validate
    
    Returns:
        (is_valid, error_message)
    """
    required_fields = [
        'from_name', 'from_street', 'from_city', 'from_state', 'from_zip',
        'to_name', 'to_street', 'to_city', 'to_state', 'to_zip',
        'weight'
    ]
    
    missing_fields = []
    for field in required_fields:
        if not order_data.get(field):
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, None


# ============================================================
# MODULE DOCUMENTATION
# ============================================================

"""
TEMPLATE SERVICE ARCHITECTURE:

This module centralizes all template-related operations:
1. CRUD operations (Create, Read, Update, Delete)
2. Template usage and loading
3. Template validation
4. Template formatting for display
5. User authorization checks

BENEFITS:
- Single source of truth for template logic
- Easy to test template operations
- Centralized validation
- Clear authorization rules
- Consistent error handling
"""
