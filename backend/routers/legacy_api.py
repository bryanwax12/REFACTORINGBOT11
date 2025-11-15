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
async def get_stats(api_key: str = Depends(verify_api_key)):
    """Legacy stats endpoint - redirects to admin stats"""
    from routers.stats import get_stats_data
    from server import db
    return await get_stats_data(db)


@router.get("/stats/expenses")
async def get_expense_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Legacy expense stats endpoint"""
    from routers.stats import get_expense_stats as get_expenses
    from server import db
    return await get_expenses(db, date_from, date_to)


@router.get("/orders")
async def get_orders(api_key: str = Depends(verify_api_key)):
    """Legacy orders endpoint"""
    from routers.orders import get_all_orders_admin
    from server import db
    return await get_all_orders_admin(db)


@router.get("/users")
async def get_users(api_key: str = Depends(verify_api_key)):
    """Legacy users endpoint"""
    from routers.users import get_all_users_admin
    from server import db
    return await get_all_users_admin(db, limit=1000)


@router.get("/topups")
async def get_topups(api_key: str = Depends(verify_api_key)):
    """Legacy topups endpoint"""
    from routers.stats import get_topups_data
    from server import db
    return await get_topups_data(db)


@router.get("/users/leaderboard")
async def get_leaderboard(api_key: str = Depends(verify_api_key)):
    """Legacy leaderboard endpoint"""
    from routers.users import get_users_leaderboard
    from server import db
    return await get_users_leaderboard(db)
