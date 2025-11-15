"""
Fixtures for unit tests
"""
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os


@pytest_asyncio.fixture(scope='function')
async def test_db():
    """Provide a test database connection for unit tests"""
    from services.service_factory import reset_service_factory
    from repositories import reset_repositories
    
    reset_service_factory()
    reset_repositories()
    
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db_name = os.environ.get('MONGODB_DB_NAME', 'telegram_shipping_bot')
    db = client[db_name]
    
    # Initialize repositories and services
    from repositories import init_repositories
    from services.service_factory import init_service_factory
    
    init_repositories(db)
    init_service_factory(db)
    
    # Cleanup before test
    await db.users.delete_many({"telegram_id": 123456789})
    await db.templates.delete_many({"telegram_id": 123456789})
    
    yield db
    
    # Cleanup after test
    await db.users.delete_many({"telegram_id": 123456789})
    await db.templates.delete_many({"telegram_id": 123456789})
    
    client.close()
    reset_service_factory()
    reset_repositories()
