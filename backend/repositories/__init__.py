"""
Repository Manager
Централизованный доступ ко всем репозиториям
"""
from repositories.user_repository import UserRepository
from repositories.order_repository import OrderRepository
from repositories.session_repository import SessionRepository
import logging

logger = logging.getLogger(__name__)


class RepositoryManager:
    """
    Менеджер для управления всеми репозиториями
    
    Предоставляет единую точку доступа ко всем репозиториям
    """
    
    def __init__(self, db):
        """
        Инициализация менеджера
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        
        # Инициализировать репозитории
        self.users = UserRepository(db)
        self.orders = OrderRepository(db)
        self.sessions = SessionRepository(db)
        self.payments = PaymentRepository(db)
        self.templates = TemplateRepository(db)
        
        logger.info("📦 Repository Manager initialized")
    
    async def close(self):
        """Закрыть все соединения (если нужно)"""
        logger.info("📦 Repository Manager closed")


# Глобальный экземпляр (будет инициализирован в server.py)
_repository_manager = None


def init_repositories(db) -> RepositoryManager:
    """
    Инициализировать репозитории
    
    Args:
        db: MongoDB database instance
        
    Returns:
        RepositoryManager экземпляр
    """
    global _repository_manager
    
    _repository_manager = RepositoryManager(db)
    
    return _repository_manager


def get_repositories() -> RepositoryManager:
    """
    Получить глобальный экземпляр RepositoryManager
    
    Returns:
        RepositoryManager экземпляр
        
    Raises:
        RuntimeError: Если репозитории не инициализированы
    """
    if _repository_manager is None:
        raise RuntimeError("Repositories not initialized. Call init_repositories() first.")
    
    return _repository_manager


# Convenience functions для быстрого доступа
def get_user_repo() -> UserRepository:
    """Получить user repository"""
    return get_repositories().users


def get_order_repo() -> OrderRepository:
    """Получить order repository"""
    return get_repositories().orders


def get_session_repo() -> SessionRepository:
    """Получить session repository"""
    return get_repositories().sessions


"""
ИСПОЛЬЗОВАНИЕ:
=============

1. В server.py при запуске:
   ```python
   from repositories import init_repositories
   
   @app.on_event("startup")
   async def startup():
       # Инициализировать репозитории
       init_repositories(db)
   ```

2. В handlers/endpoints:
   ```python
   from repositories import get_user_repo, get_order_repo
   
   async def my_handler(user_id):
       # Получить репозитории
       user_repo = get_user_repo()
       order_repo = get_order_repo()
       
       # Использовать
       user = await user_repo.find_by_telegram_id(user_id)
       orders = await order_repo.find_by_user(user_id)
   ```

3. Альтернативно через менеджер:
   ```python
   from repositories import get_repositories
   
   repos = get_repositories()
   user = await repos.users.find_by_telegram_id(12345)
   ```

ПРЕИМУЩЕСТВА:
=============

- ✅ Единая точка доступа ко всем репозиториям
- ✅ Централизованное управление БД операциями
- ✅ Легко тестировать (mock repositories)
- ✅ Кеширование на уровне репозитория (в будущем)
- ✅ Миграции и индексы в одном месте
- ✅ Type hints для IDE
"""
