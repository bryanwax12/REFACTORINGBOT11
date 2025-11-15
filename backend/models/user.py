"""User models"""
from pydantic import BaseModel, ConfigDict
from typing import Optional

class User(BaseModel):
    """User model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    balance: float = 0.0
    created_at: str
    blocked: bool = False
    bot_blocked_by_user: bool = False

class UserBalance(BaseModel):
    """User balance update model"""
    telegram_id: int
    amount: float
