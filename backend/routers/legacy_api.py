"""
Legacy API Router
Provides backward compatibility for old API endpoints used by frontend
"""
from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Optional
import httpx

router = APIRouter(prefix="/api", tags=["legacy"])

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify admin API key"""
    import os
    admin_key = os.environ.get('ADMIN_API_KEY', 'sk_admin_e19063c3f82f447ba4ccf49cd97dd9fd_2024')
    if not x_api_key or x_api_key != admin_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


@router.get("/stats")
async def legacy_get_stats(api_key: str = Depends(verify_api_key)):
    """Legacy stats endpoint"""
    from server import db
    from repositories import get_repositories
    repos = get_repositories()
    
    users_count = await repos.users.collection.count_documents({})
    orders_count = await repos.orders.collection.count_documents({})
    
    return {
        "users_count": users_count,
        "orders_count": orders_count,
        "revenue": 0
    }


@router.get("/stats/expenses")
async def legacy_get_expense_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Legacy expense stats endpoint"""
    return {"expenses": [], "total": 0}


@router.get("/orders")
async def legacy_get_orders(api_key: str = Depends(verify_api_key)):
    """Legacy orders endpoint"""
    from server import db
    orders = await db.orders.find({}, {"_id": 0}).limit(100).to_list(100)
    return {"orders": orders}


@router.get("/users")
async def legacy_get_users(api_key: str = Depends(verify_api_key)):
    """Legacy users endpoint"""
    from server import db
    users = await db.users.find({}, {"_id": 0}).limit(100).to_list(100)
    return {"users": users}


@router.get("/topups")
async def legacy_get_topups(api_key: str = Depends(verify_api_key)):
    """Legacy topups endpoint"""
    from server import db
    payments = await db.payments.find(
        {"type": "topup"},
        {"_id": 0}
    ).limit(100).to_list(100)
    return {"topups": payments}


@router.get("/users/leaderboard")
async def legacy_get_leaderboard(api_key: str = Depends(verify_api_key)):
    """Legacy leaderboard endpoint"""
    from routers.users import get_users_leaderboard
    return await get_users_leaderboard(limit=10)
