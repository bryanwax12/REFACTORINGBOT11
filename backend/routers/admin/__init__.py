"""
Admin Routers Package
Modular admin API structure
"""
from fastapi import APIRouter
from routers.admin import users, stats, system

# Create main admin router
admin_router_v2 = APIRouter(prefix="/api/admin", tags=["admin"])

# Include sub-routers
admin_router_v2.include_router(users.router)
admin_router_v2.include_router(stats.router)
admin_router_v2.include_router(system.router)

__all__ = ['admin_router_v2']
