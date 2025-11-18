"""
Refunds API Router
Handles label refund requests from users
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from handlers.admin_handlers import verify_admin_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/refunds", tags=["refunds"])


# Request/Response Models
class RefundRequest(BaseModel):
    label_ids: List[str]  # Can be multiple label IDs


class RefundRequestResponse(BaseModel):
    request_id: str
    valid_labels: List[str]
    invalid_labels: List[dict]  # {label_id, reason}


class RefundStatusUpdate(BaseModel):
    status: str  # approved, rejected, processed
    admin_notes: Optional[str] = None
    refund_amount: Optional[float] = None


@router.post("/request", response_model=RefundRequestResponse)
async def create_refund_request(request: RefundRequest, telegram_id: int):
    """
    Create a refund request from user
    Validates label age (must be older than 5 days)
    """
    from server import db
    from uuid import uuid4
    
    try:
        valid_labels = []
        invalid_labels = []
        
        # Check each label
        for label_id in request.label_ids:
            # Find order with this label
            order = await db.orders.find_one(
                {"label_id": label_id, "telegram_id": telegram_id},
                {"_id": 0}
            )
            
            if not order:
                invalid_labels.append({
                    "label_id": label_id,
                    "reason": "Лейбл не найден или не принадлежит вам"
                })
                continue
            
            # Check if already has pending refund request
            existing_refund = await db.refund_requests.find_one({
                "label_id": label_id,
                "status": {"$in": ["pending", "approved"]}
            })
            
            if existing_refund:
                invalid_labels.append({
                    "label_id": label_id,
                    "reason": "Уже существует активная заявка на возврат"
                })
                continue
            
            # Check if already refunded
            if order.get("refunded"):
                invalid_labels.append({
                    "label_id": label_id,
                    "reason": "Лейбл уже был возвращен"
                })
                continue
            
            # Check label age (must be older than 5 days)
            created_at = order.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            age_days = (datetime.now(timezone.utc) - created_at).days
            
            if age_days < 5:
                invalid_labels.append({
                    "label_id": label_id,
                    "reason": f"Лейбл слишком новый (возраст: {age_days} дней, нужно минимум 5 дней)"
                })
                continue
            
            valid_labels.append(label_id)
        
        # If no valid labels, return error
        if not valid_labels:
            return RefundRequestResponse(
                request_id="",
                valid_labels=[],
                invalid_labels=invalid_labels
            )
        
        # Create refund request
        request_id = str(uuid4())
        refund_doc = {
            "request_id": request_id,
            "telegram_id": telegram_id,
            "label_ids": valid_labels,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "admin_notes": None,
            "refund_amount": None,
            "processed_at": None
        }
        
        await db.refund_requests.insert_one(refund_doc)
        
        # Store individual label refund records
        for label_id in valid_labels:
            await db.refund_requests.update_one(
                {"label_id": label_id},
                {
                    "$set": {
                        "label_id": label_id,
                        "request_id": request_id,
                        "telegram_id": telegram_id,
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
        
        logger.info(f"Created refund request {request_id} for user {telegram_id} with {len(valid_labels)} labels")
        
        return RefundRequestResponse(
            request_id=request_id,
            valid_labels=valid_labels,
            invalid_labels=invalid_labels
        )
    
    except Exception as e:
        logger.error(f"Error creating refund request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/requests")
async def get_refund_requests(
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected, processed"),
    limit: int = Query(100, ge=1, le=1000),
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get all refund requests (Admin only)
    """
    from server import db
    
    try:
        query = {}
        if status:
            query["status"] = status
        
        # Get refund requests with user info
        requests = await db.refund_requests.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Enrich with user and order data
        for req in requests:
            # Get user info
            user = await db.users.find_one(
                {"telegram_id": req["telegram_id"]},
                {"_id": 0, "username": 1, "first_name": 1, "balance": 1}
            )
            req["user"] = user or {}
            
            # Get order details for each label
            label_details = []
            for label_id in req.get("label_ids", []):
                order = await db.orders.find_one(
                    {"label_id": label_id},
                    {"_id": 0, "order_id": 1, "label_id": 1, "cost": 1, "created_at": 1, "carrier": 1, "service": 1}
                )
                if order:
                    label_details.append(order)
            
            req["label_details"] = label_details
        
        return {
            "requests": requests,
            "count": len(requests)
        }
    
    except Exception as e:
        logger.error(f"Error getting refund requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/requests/{request_id}")
async def get_refund_request(
    request_id: str,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Get specific refund request details
    """
    from server import db
    
    try:
        request = await db.refund_requests.find_one(
            {"request_id": request_id},
            {"_id": 0}
        )
        
        if not request:
            raise HTTPException(status_code=404, detail="Refund request not found")
        
        # Get user info
        user = await db.users.find_one(
            {"telegram_id": request["telegram_id"]},
            {"_id": 0, "username": 1, "first_name": 1, "balance": 1, "telegram_id": 1}
        )
        request["user"] = user or {}
        
        # Get order details
        label_details = []
        for label_id in request.get("label_ids", []):
            order = await db.orders.find_one(
                {"label_id": label_id},
                {"_id": 0}
            )
            if order:
                label_details.append(order)
        
        request["label_details"] = label_details
        
        return request
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting refund request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/requests/{request_id}/status")
async def update_refund_status(
    request_id: str,
    update: RefundStatusUpdate,
    authenticated: bool = Depends(verify_admin_key)
):
    """
    Update refund request status (Admin only)
    """
    from server import db, bot_instance
    from handlers.common_handlers import safe_telegram_call
    
    try:
        # Get request
        request = await db.refund_requests.find_one({"request_id": request_id})
        if not request:
            raise HTTPException(status_code=404, detail="Refund request not found")
        
        # Update request
        update_data = {
            "status": update.status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if update.admin_notes:
            update_data["admin_notes"] = update.admin_notes
        
        if update.refund_amount is not None:
            update_data["refund_amount"] = update.refund_amount
        
        if update.status == "processed":
            update_data["processed_at"] = datetime.now(timezone.utc).isoformat()
            
            # If processed, refund balance to user
            if update.refund_amount and update.refund_amount > 0:
                await db.users.update_one(
                    {"telegram_id": request["telegram_id"]},
                    {"$inc": {"balance": update.refund_amount}}
                )
                
                # Mark orders as refunded
                for label_id in request.get("label_ids", []):
                    await db.orders.update_one(
                        {"label_id": label_id},
                        {"$set": {"refunded": True, "refunded_at": datetime.now(timezone.utc).isoformat()}}
                    )
                
                # Send notification to user
                if bot_instance:
                    message = (
                        f"✅ *Возврат средств выполнен!*\n\n"
                        f"Ваша заявка на возврат одобрена.\n"
                        f"💰 Возвращено на баланс: *${update.refund_amount:.2f}*\n\n"
                        f"Лейблы: {', '.join(request.get('label_ids', []))}\n\n"
                        f"Спасибо за использование нашего сервиса!"
                    )
                    
                    try:
                        await safe_telegram_call(
                            bot_instance.send_message(
                                chat_id=request["telegram_id"],
                                text=message,
                                parse_mode='Markdown'
                            )
                        )
                    except Exception as e:
                        logger.error(f"Failed to send refund notification: {e}")
        
        elif update.status == "rejected":
            # Send rejection notification
            if bot_instance:
                message = (
                    "❌ *Заявка на возврат отклонена*\n\n"
                    "К сожалению, ваша заявка на возврат была отклонена.\n\n"
                )
                
                if update.admin_notes:
                    message += f"Причина: {update.admin_notes}\n\n"
                
                message += "Если у вас есть вопросы, свяжитесь с поддержкой."
                
                try:
                    await safe_telegram_call(
                        bot_instance.send_message(
                            chat_id=request["telegram_id"],
                            text=message,
                            parse_mode='Markdown'
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to send rejection notification: {e}")
        
        result = await db.refund_requests.update_one(
            {"request_id": request_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated refund request {request_id} to status {update.status}")
            return {"success": True, "message": f"Refund request updated to {update.status}"}
        else:
            return {"success": False, "message": "No changes made"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating refund status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/requests")
async def get_user_refund_requests(telegram_id: int):
    """
    Get user's own refund requests
    """
    from server import db
    
    try:
        requests = await db.refund_requests.find(
            {"telegram_id": telegram_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        return {
            "requests": requests,
            "count": len(requests)
        }
    
    except Exception as e:
        logger.error(f"Error getting user refund requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))
