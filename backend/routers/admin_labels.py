"""
Admin Labels Router
Эндпоинты для управления метками (admin only)
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-labels"])


async def verify_admin_key():
    """Verify admin authorization"""
    # This is a placeholder - actual implementation in server.py
    pass


@router.post("/create-label/{order_id}", dependencies=[Depends(verify_admin_key)])
async def admin_create_label(order_id: str):
    """
    Admin endpoint to manually create shipping label for an order
    """
    from server import create_and_send_label
    from repositories import get_order_repo
    
    try:
        order_repo = get_order_repo()
        order = await order_repo.find_by_id(order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order['payment_status'] != 'paid':
            raise HTTPException(status_code=400, detail="Order must be paid first")
        
        # Create label
        success = await create_and_send_label(
            order_id,
            order['telegram_id'],
            None  # No context in API call
        )
        
        if success:
            logger.info(f"✅ Admin created label for order {order_id}")
            return {
                "status": "success",
                "order_id": order_id,
                "message": "Label created successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create label")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-label-manual", dependencies=[Depends(verify_admin_key)])
async def admin_create_label_manual(
    order_id: str,
    tracking_number: str,
    carrier: str,
    label_url: Optional[str] = None
):
    """
    Admin endpoint to manually add label information without ShipStation
    """
    from server import db
    from repositories import get_order_repo
    from datetime import datetime, timezone
    
    try:
        order_repo = get_order_repo()
        order = await order_repo.find_by_id(order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Create manual label entry
        label_data = {
            "order_id": order_id,
            "telegram_id": order['telegram_id'],
            "tracking_number": tracking_number,
            "carrier": carrier,
            "label_url": label_url or "",
            "label_id": f"manual_{order_id}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "manual": True
        }
        
        await db.shipping_labels.insert_one(label_data)
        
        # Update order status
        await order_repo.update_by_id(
            order_id,
            {"shipping_status": "label_created"}
        )
        
        logger.info(f"✅ Admin manually added label for order {order_id}")
        
        return {
            "status": "success",
            "order_id": order_id,
            "tracking_number": tracking_number,
            "carrier": carrier,
            "message": "Manual label added successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding manual label: {e}")
        raise HTTPException(status_code=500, detail=str(e))
