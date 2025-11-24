"""
Shipping Router
Эндпоинты для управления доставкой и метками
"""
from fastapi import APIRouter, HTTPException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["shipping"])


@router.post("/shipping/create-label")
async def create_shipping_label(order_id: str):
    """Create shipping label for an order"""
    # Import here to avoid circular dependency
    from server import (
        create_and_send_label,
        db,
        SHIPSTATION_API_KEY
    )
    from repositories import get_repositories
    
    try:
        repos = get_repositories()
        order = await repos.orders.find_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order['payment_status'] != 'paid':
            raise HTTPException(status_code=400, detail="Order not paid")
        
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        result = await create_and_send_label(order_id, order['telegram_id'], None)
        
        if result:
            label = await db.shipping_labels.find_one({"order_id": order_id}, {"_id": 0})
            return {
                "order_id": order_id,
                "tracking_number": label['tracking_number'],
                "label_url": label['label_url'],
                "status": "success"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create label")
        
    except Exception as e:
        logger.error(f"Error creating label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shipping/track/{tracking_number}")
async def track_shipment(tracking_number: str, carrier: str):
    """Get detailed tracking information with progress status"""
    from server import SHIPSTATION_API_KEY
    import httpx
    
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        headers = {
            'API-Key': SHIPSTATION_API_KEY,
            'Content-Type': 'application/json'
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f'https://api.shipstation.com/v2/tracking?tracking_number={tracking_number}&carrier_code={carrier}',
                headers=headers
            )
        
        if response.status_code == 200:
            tracking_data = response.json()
            status_code = tracking_data.get('status_code', 'UNKNOWN')
            
            status_map = {
                'NY': {'name': 'Not Yet Shipped', 'progress': 0, 'color': 'gray'},
                'IT': {'name': 'In Transit', 'progress': 50, 'color': 'blue'},
                'DE': {'name': 'Delivered', 'progress': 100, 'color': 'green'},
                'EX': {'name': 'Exception', 'progress': 25, 'color': 'red'},
                'UN': {'name': 'Unknown', 'progress': 0, 'color': 'gray'},
                'AT': {'name': 'Attempted Delivery', 'progress': 75, 'color': 'orange'},
            }
            
            status_info = status_map.get(status_code, {'name': 'Unknown', 'progress': 0, 'color': 'gray'})
            
            return {
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status_code": status_code,
                "status_name": status_info['name'],
                "progress": status_info['progress'],
                "progress_color": status_info['color'],
                "estimated_delivery": tracking_data.get('estimated_delivery_date'),
                "actual_delivery": tracking_data.get('actual_delivery_date'),
                "events": tracking_data.get('events', [])
            }
        else:
            return {
                "tracking_number": tracking_number,
                "carrier": carrier,
                "status_code": "UN",
                "status_name": "Unknown",
                "progress": 0,
                "progress_color": "gray",
                "message": "Tracking information not available"
            }
    except Exception as e:
        logger.error(f"Error tracking shipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labels/{label_id}/download")
async def download_label(label_id: str):
    """Proxy endpoint to download label PDF from ShipStation"""
    from server import SHIPSTATION_API_KEY, db
    from fastapi.responses import Response
    import httpx
    
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        label = await db.shipping_labels.find_one({"label_id": label_id}, {"_id": 0})
        if not label:
            raise HTTPException(status_code=404, detail="Label not found")
        
        label_url = label.get('label_url')
        if not label_url:
            raise HTTPException(status_code=404, detail="Label URL not available")
        
        headers = {'API-Key': SHIPSTATION_API_KEY}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(label_url, headers=headers)
        
        if response.status_code == 200:
            return Response(
                content=response.content,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=label_{label_id}.pdf"}
            )
        else:
            logger.error(f"Failed to download label: {response.status_code}")
            raise HTTPException(status_code=502, detail="Failed to download label from ShipStation")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carriers")
async def get_carriers():
    """Get available carriers from ShipStation"""
    from server import SHIPSTATION_API_KEY
    import httpx
    
    try:
        if not SHIPSTATION_API_KEY:
            raise HTTPException(status_code=500, detail="ShipStation API not configured")
        
        headers = {'API-Key': SHIPSTATION_API_KEY}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                'https://api.shipstation.com/carriers',
                headers=headers
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=502, detail="Failed to fetch carriers")
            
    except Exception as e:
        logger.error(f"Error fetching carriers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-shipping")
async def calculate_shipping():
    """Calculate shipping rates"""
    # This endpoint is complex and needs more context
    # Keeping as placeholder for now
    raise HTTPException(status_code=501, detail="Use /api/calculate-shipping for now")
