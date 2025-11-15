"""Order models"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any

class OrderCreate(BaseModel):
    """Order creation model"""
    telegram_id: int
    address_from: Dict[str, Any]
    address_to: Dict[str, Any]
    parcel: Dict[str, Any]
    selected_carrier: str
    selected_service: str

class Order(BaseModel):
    """Order model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: str
    telegram_id: int
    address_from: Dict[str, Any]
    address_to: Dict[str, Any]
    parcel: Dict[str, Any]
    amount: float
    payment_status: str
    shipping_status: str
    created_at: str
    selected_carrier: Optional[str] = None
    selected_service: Optional[str] = None
