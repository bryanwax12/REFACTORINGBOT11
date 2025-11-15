"""
Database Operations with Profiling
Профилируемые операции с базой данных для мониторинга производительности
"""
from utils.db_wrappers import profile_db_query


@profile_db_query("find_user_by_telegram_id")
async def find_user_by_telegram_id(telegram_id: int, projection: dict = None):
    """
    Профилируемый поиск пользователя по telegram_id
    
    Args:
        telegram_id: Telegram user ID
        projection: Optional projection dict (ignored, kept for compatibility)
    
    Returns:
        User document or None
    """
    from repositories import get_user_repo
    user_repo = get_user_repo()
    return await user_repo.find_by_telegram_id(telegram_id)


@profile_db_query("find_order_by_id")
async def find_order_by_id(order_id: str, projection: dict = None):
    """Профилируемый поиск заказа по ID"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.orders.find_by_id(order_id)


@profile_db_query("find_template_by_id")
async def find_template_by_id(template_id: str, projection: dict = None):
    """Профилируемый поиск шаблона по ID"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.templates.find_by_id(template_id)


@profile_db_query("find_payment_by_invoice")
async def find_payment_by_invoice(invoice_id: int, projection: dict = None):
    """Профилируемый поиск платежа по invoice_id"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.payments.find_by_invoice_id(invoice_id)


@profile_db_query("find_pending_order")
async def find_pending_order(telegram_id: int, projection: dict = None):
    """Профилируемый поиск незавершенного заказа"""
    from server import db
    if projection is None:
        projection = {"_id": 0}
    return await db.pending_orders.find_one({"telegram_id": telegram_id}, projection)


@profile_db_query("count_user_templates")
async def count_user_templates(telegram_id: int):
    """Профилируемый подсчет шаблонов пользователя"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.templates.count_user_templates(telegram_id)


@profile_db_query("find_user_templates")
async def find_user_templates(telegram_id: int, limit: int = 10):
    """Профилируемый поиск шаблонов пользователя"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.templates.get_user_templates(telegram_id, limit=limit)


@profile_db_query("update_order")
async def update_order(order_id: str, update_data: dict):
    """Профилируемое обновление заказа"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.orders.update_by_id(order_id, update_data)


@profile_db_query("insert_payment")
async def insert_payment(payment_dict: dict):
    """Профилируемая вставка платежа"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.payments.collection.insert_one(payment_dict)


@profile_db_query("insert_pending_order")
async def insert_pending_order(order_dict: dict):
    """Профилируемая вставка незавершенного заказа"""
    from server import db
    return await db.pending_orders.insert_one(order_dict)


@profile_db_query("delete_pending_order")
async def delete_pending_order(telegram_id: int):
    """Профилируемое удаление незавершенного заказа"""
    from server import db
    return await db.pending_orders.delete_one({"telegram_id": telegram_id})


@profile_db_query("insert_template")
async def insert_template(template_dict: dict):
    """Профилируемая вставка шаблона"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.templates.collection.insert_one(template_dict)


@profile_db_query("update_template")
async def update_template(template_id: str, update_data: dict):
    """Профилируемое обновление шаблона"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.templates.update_by_id(template_id, update_data)


@profile_db_query("delete_template")
async def delete_template(template_id: str):
    """Профилируемое удаление шаблона"""
    from repositories import get_repositories
    repos = get_repositories()
    return await repos.templates.delete_by_id(template_id)
