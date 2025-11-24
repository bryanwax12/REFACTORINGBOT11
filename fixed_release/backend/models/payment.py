"""Payment models"""
from pydantic import BaseModel, ConfigDict
from typing import Optional

class Payment(BaseModel):
    """Payment model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    invoice_id: str
    telegram_id: int
    amount: float
    status: str
    created_at: str
    order_id: Optional[str] = None
    type: str = "order"  # "order" or "topup"
