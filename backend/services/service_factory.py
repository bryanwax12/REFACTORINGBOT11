"""
Service Factory
Фабрика для создания сервисов с правильными зависимостями
"""
from typing import Optional
from .order_service import OrderService
from .user_service import UserService
from .session_service import SessionService
from .payment_service import PaymentService


class ServiceFactory:
    """
    Фабрика для создания сервисов
    Централизует создание сервисов с правильными зависимостями
    """
    
    def __init__(self, db):
        """
        Инициализация фабрики
        
        Args:
            db: Database connection
        """
        self.db = db
        self._services = {}
    
    def get_user_service(self) -> UserService:
        """Получить UserService"""
        if 'user_service' not in self._services:
            from repositories import get_user_repo
            user_repo = get_user_repo()
            self._services['user_service'] = UserService(user_repo)
        return self._services['user_service']
    
    def get_session_service(self) -> SessionService:
        """Получить SessionService"""
        if 'session_service' not in self._services:
            from repositories.session_repository import SessionRepository
            session_repo = SessionRepository(self.db)
            self._services['session_service'] = SessionService(session_repo)
        return self._services['session_service']
    
    def get_payment_service(self) -> PaymentService:
        """Получить PaymentService"""
        if 'payment_service' not in self._services:
            from repositories import get_user_repo, get_payment_repo
            user_repo = get_user_repo()
            payment_repo = get_payment_repo()
            self._services['payment_service'] = PaymentService(payment_repo, user_repo)
        return self._services['payment_service']
    
    def get_order_service(self) -> OrderService:
        """Получить OrderService"""
        if 'order_service' not in self._services:
            from repositories import get_order_repo, get_user_repo, get_payment_repo
            order_repo = get_order_repo()
            user_repo = get_user_repo()
            payment_repo = get_payment_repo()
            self._services['order_service'] = OrderService(order_repo, user_repo, payment_repo)
        return self._services['order_service']
    
    def get_template_service(self):
        """Получить TemplateService"""
        if 'template_service' not in self._services:
            from services.template_service import TemplateService
            self._services['template_service'] = TemplateService(self.db)
        return self._services['template_service']
    
    def get_all_services(self) -> dict:
        """Получить все сервисы"""
        return {
            'user_service': self.get_user_service(),
            'session_service': self.get_session_service(),
            'payment_service': self.get_payment_service(),
            'order_service': self.get_order_service(),
            'template_service': self.get_template_service()
        }


# Глобальная фабрика (инициализируется при старте приложения)
_factory: Optional[ServiceFactory] = None


def init_service_factory(db):
    """
    Инициализировать глобальную фабрику сервисов
    
    Args:
        db: Database connection
    """
    global _factory
    _factory = ServiceFactory(db)


def get_service_factory() -> ServiceFactory:
    """
    Получить глобальную фабрику сервисов
    
    Returns:
        ServiceFactory instance
        
    Raises:
        RuntimeError: Если фабрика не инициализирована
    """
    if _factory is None:
        raise RuntimeError("Service factory not initialized. Call init_service_factory() first.")
    return _factory


def get_user_service() -> UserService:
    """Получить UserService из глобальной фабрики"""
    return get_service_factory().get_user_service()


def get_session_service() -> SessionService:
    """Получить SessionService из глобальной фабрики"""
    return get_service_factory().get_session_service()


def get_payment_service() -> PaymentService:
    """Получить PaymentService из глобальной фабрики"""
    return get_service_factory().get_payment_service()


def get_order_service() -> OrderService:
    """Получить OrderService из глобальной фабрики"""
    return get_service_factory().get_order_service()
