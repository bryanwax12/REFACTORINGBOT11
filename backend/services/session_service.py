"""
Session Service
Сервис для управления сессиями пользователей
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SessionService:
    """
    Сервис для управления сессиями пользователей
    Инкапсулирует бизнес-логику работы с сессиями
    """
    
    def __init__(self, session_repo):
        """
        Инициализация сервиса
        
        Args:
            session_repo: SessionRepository
        """
        self.session_repo = session_repo
    
    async def get_or_create_session(
        self,
        user_id: int,
        session_type: str = "conversation",
        initial_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Получить или создать сессию
        
        Args:
            user_id: Telegram ID пользователя
            session_type: Тип сессии
            initial_data: Начальные данные
            
        Returns:
            Session document
        """
        session = await self.session_repo.get_or_create_session(
            user_id=user_id,
            session_type=session_type,
            initial_data=initial_data or {}
        )
        return session
    
    async def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить сессию пользователя
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Session document или None
        """
        return await self.session_repo.get_session(user_id)
    
    async def update_session_step(
        self,
        user_id: int,
        step: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        Обновить шаг сессии и данные
        
        Args:
            user_id: Telegram ID пользователя
            step: Новый шаг
            data: Данные для сохранения
            
        Returns:
            True если успешно
        """
        # Обновить данные если есть
        if data:
            await self.session_repo.update_temp_data(user_id, data)
        
        # Обновить шаг
        return await self.session_repo.update_step(user_id, step)
    
    async def save_order_field(
        self,
        user_id: int,
        field_name: str,
        field_value: Any
    ) -> bool:
        """
        Сохранить поле заказа в сессию
        
        Args:
            user_id: Telegram ID пользователя
            field_name: Название поля
            field_value: Значение поля
            
        Returns:
            True если успешно
        """
        return await self.session_repo.update_temp_data(
            user_id,
            {field_name: field_value}
        )
    
    async def get_order_data(self, user_id: int) -> Dict[str, Any]:
        """
        Получить данные заказа из сессии
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Данные заказа
        """
        session = await self.session_repo.get_session(user_id)
        if not session:
            return {}
        
        return session.get('temp_data', {})
    
    async def clear_session(self, user_id: int) -> bool:
        """
        Очистить сессию пользователя
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            True если успешно
        """
        return await self.session_repo.clear_session(user_id)
    
    async def validate_session_data(self, session_data: Dict) -> tuple[bool, Optional[str]]:
        """
        Валидировать данные сессии для создания заказа
        
        Args:
            session_data: Данные из сессии
            
        Returns:
            (is_valid, error_message)
        """
        required_fields = [
            'from_name', 'from_address', 'from_city', 'from_state', 'from_zip',
            'to_name', 'to_address', 'to_city', 'to_state', 'to_zip',
            'parcel_weight', 'parcel_length', 'parcel_width', 'parcel_height'
        ]
        
        for field in required_fields:
            if field not in session_data or not session_data[field]:
                return False, f"Missing required field: {field}"
        
        return True, None
