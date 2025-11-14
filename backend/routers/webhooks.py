"""
Webhooks Router
Эндпоинты для обработки вебхуков
"""
from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/oxapay")
async def oxapay_webhook(request: Request):
    """
    Oxapay payment webhook
    TODO: Move implementation from server.py
    """
    return {"status": "not implemented"}


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Telegram bot webhook
    TODO: Move implementation from server.py
    """
    return {"status": "not implemented"}
