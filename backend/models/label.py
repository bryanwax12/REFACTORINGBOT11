"""Shipping label models"""
from pydantic import BaseModel, ConfigDict
from typing import Optional

class ShippingLabel(BaseModel):
    """Shipping label model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    order_id: str
    telegram_id: int
    tracking_number: str
    label_url: str
    carrier: str
    service_level: str
    amount: float
    status: str = "created"
    created_at: str
