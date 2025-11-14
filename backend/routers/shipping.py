"""
Shipping Router
Эндпоинты для управления доставкой и метками
"""
from fastapi import APIRouter, HTTPException, Depends
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shipping", tags=["shipping"])


@router.post("/create-label")
async def create_shipping_label():
    """
    Create shipping label
    TODO: Move implementation from server.py
    """
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/track/{tracking_number}")
async def track_shipment(tracking_number: str):
    """
    Track shipment by tracking number
    TODO: Move implementation from server.py
    """
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/calculate")
async def calculate_shipping():
    """
    Calculate shipping rates
    TODO: Move implementation from server.py
    """
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/carriers")
async def get_carriers():
    """
    Get available carriers
    TODO: Move implementation from server.py
    """
    raise HTTPException(status_code=501, detail="Not implemented yet")
