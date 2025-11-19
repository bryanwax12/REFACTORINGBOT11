"""
Orders Router
Эндпоинты для управления заказами
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging
import io
import csv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["orders"])


@router.post("/orders", response_model=dict)
async def create_order(order_data: dict):
    """Create a new order"""
    from server import OrderCreate, Order, generate_order_id
    from repositories import get_repositories, get_user_repo
    
    try:
        # Validate order_data
        order_create = OrderCreate(**order_data)
        
        user_repo = get_user_repo()
        user = await user_repo.find_by_telegram_id(order_create.telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found. Please /start the bot first.")
        
        order_id = generate_order_id(telegram_id=order_create.telegram_id)
        
        order = Order(
            user_id=user.get('id', user.get('_id', str(user['telegram_id']))),
            order_id=order_id,
            telegram_id=order_create.telegram_id,
            address_from=order_create.address_from,
            address_to=order_create.address_to,
            parcel=order_create.parcel,
            amount=order_create.amount
        )
        
        order_dict = order.model_dump()
        order_dict['created_at'] = order_dict['created_at'].isoformat()
        
        repos = get_repositories()
        await repos.orders.collection.insert_one(order_dict)
        
        return {"order_id": order_id, "status": "created"}
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/search")
async def search_orders(
    query: Optional[str] = None,
    payment_status: Optional[str] = None,
    shipping_status: Optional[str] = None,
    limit: int = 100
):
    """Search orders by tracking number, order ID, or other fields"""
    from server import db
    from repositories import get_repositories, get_user_repo
    
    try:
        search_filter = {}
        
        if query:
            labels = await db.shipping_labels.find(
                {"tracking_number": {"$regex": query, "$options": "i"}},
                {"_id": 0, "order_id": 1}
            ).to_list(100)
            
            matching_order_ids = [label['order_id'] for label in labels]
            
            search_filter["$or"] = [
                {"id": {"$regex": query, "$options": "i"}},
                {"id": {"$in": matching_order_ids}}
            ]
        
        if payment_status:
            search_filter["payment_status"] = payment_status
        
        if shipping_status:
            search_filter["shipping_status"] = shipping_status
        
        repos = get_repositories()
        orders = await repos.orders.find_with_filter(search_filter, limit=limit)
        
        result = []
        user_repo = get_user_repo()
        
        for order in orders:
            labels = await db.shipping_labels.find(
                {"order_id": order['id']},
                {"_id": 0}
            ).sort("created_at", -1).to_list(100)
            
            user = await user_repo.find_by_telegram_id(order["telegram_id"])
            user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
            user_username = user.get('username', '') if user else ''
            
            if labels:
                for label in labels:
                    order_row = order.copy()
                    order_row.update({
                        'tracking_number': label.get('tracking_number', ''),
                        'label_url': label.get('label_url', ''),
                        'carrier': label.get('carrier', ''),
                        'label_id': label.get('label_id', ''),
                        'label_created_at': label.get('created_at', ''),
                        'user_name': user_name,
                        'user_username': user_username
                    })
                    result.append(order_row)
            else:
                order.update({
                    'tracking_number': '',
                    'label_url': '',
                    'carrier': '',
                    'label_id': '',
                    'label_created_at': '',
                    'user_name': user_name,
                    'user_username': user_username
                })
                result.append(order)
        
        return result
    except Exception as e:
        logger.error(f"Error searching orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/export/csv")
async def export_orders_csv(
    payment_status: Optional[str] = None,
    shipping_status: Optional[str] = None
):
    """Export orders to CSV format"""
    from repositories import get_repositories, get_user_repo
    from server import db
    
    try:
        query = {}
        if payment_status:
            query["payment_status"] = payment_status
        if shipping_status:
            query["shipping_status"] = shipping_status
        
        repos = get_repositories()
        orders = await repos.orders.find_with_filter(query, limit=10000)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Order ID', 'User ID', 'Telegram ID', 'Username',
            'Amount', 'Payment Status', 'Shipping Status',
            'Tracking Number', 'Carrier', 'Created At'
        ])
        
        user_repo = get_user_repo()
        
        for order in orders:
            user = await user_repo.find_by_telegram_id(order["telegram_id"])
            username = user.get('username', '') if user else ''
            
            label = await db.shipping_labels.find_one(
                {"order_id": order['id']},
                {"_id": 0}
            )
            
            writer.writerow([
                order.get('id', ''),
                order.get('user_id', ''),
                order.get('telegram_id', ''),
                username,
                order.get('amount', 0),
                order.get('payment_status', ''),
                order.get('shipping_status', ''),
                label.get('tracking_number', '') if label else '',
                label.get('carrier', '') if label else '',
                order.get('created_at', '')
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=orders.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", response_model=List[dict])
async def get_orders(
    limit: int = 100,
    skip: int = 0,
    payment_status: Optional[str] = None
):
    """Get orders list"""
    from repositories import get_repositories
    
    try:
        query = {}
        if payment_status:
            query["payment_status"] = payment_status
        
        repos = get_repositories()
        orders = await repos.orders.find_with_filter(query, limit=limit, skip=skip)
        
        return orders
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order by ID"""
    from repositories import get_repositories
    from server import db
    
    try:
        repos = get_repositories()
        order = await repos.orders.find_by_id(order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get associated label
        label = await db.shipping_labels.find_one(
            {"order_id": order_id},
            {"_id": 0}
        )
        
        if label:
            order['label'] = label
        
        return order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/{order_id}/refund")
async def refund_order(order_id: str, refund_reason: Optional[str] = None):
    """Refund an order - void label and return money"""
    from repositories import get_repositories, get_user_repo
    from server import db, SHIPSTATION_API_KEY
    import httpx
    
    try:
        repos = get_repositories()
        order = await repos.orders.find_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order.get('refund_status') == 'refunded':
            raise HTTPException(status_code=400, detail="Order already refunded")
        
        if order['payment_status'] != 'paid':
            raise HTTPException(status_code=400, detail="Cannot refund unpaid order")
        
        label = await db.shipping_labels.find_one({"order_id": order_id}, {"_id": 0})
        void_success = False
        
        if label and label.get('label_id') and SHIPSTATION_API_KEY:
            try:
                headers = {
                    'API-Key': SHIPSTATION_API_KEY,
                    'Content-Type': 'application/json'
                }
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    void_response = await client.put(
                        f'https://api.shipstation.com/v2/labels/{label["label_id"]}/void',
                        headers=headers
                    )
                
                void_success = void_response.status_code == 200
            except Exception as e:
                logger.warning(f"Failed to void label on ShipStation: {e}")
        
        # Return money to user balance
        user_repo = get_user_repo()
        refund_amount = order.get('amount', 0)
        await user_repo.update_balance(
            order['telegram_id'],
            refund_amount,
            f"Refund for order {order_id}"
        )
        
        # Update order status
        await repos.orders.update_by_id(
            order_id,
            {
                'refund_status': 'refunded',
                'refund_reason': refund_reason or 'Admin refund',
                'refund_amount': refund_amount
            }
        )
        
        return {
            "order_id": order_id,
            "refund_amount": refund_amount,
            "label_voided": void_success,
            "status": "refunded"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refunding order: {e}")
        raise HTTPException(status_code=500, detail=str(e))
