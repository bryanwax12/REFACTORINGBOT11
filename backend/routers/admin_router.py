"""
Admin API Router
Centralized router for all admin-only API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from handlers.admin_handlers import verify_admin_key
import logging

logger = logging.getLogger(__name__)

# Create admin router with prefix
admin_router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)]  # All routes require admin auth
)


# Note: Admin endpoints are currently defined in server.py
# This router is created as a foundation for future refactoring
# 
# Future refactoring tasks:
# TODO: Move 19 admin endpoints from server.py to this router:
#   - GET /users (get_users)
#   - POST /block/{telegram_id} (block_user)
#   - POST /unblock/{telegram_id} (unblock_user)
#   - POST /invite/{telegram_id} (invite_user_to_channel)
#   - POST /invite/all (invite_all_users_to_channel)
#   - GET /maintenance (get_maintenance_status)
#   - POST /maintenance/enable (enable_maintenance_mode)
#   - POST /maintenance/disable (disable_maintenance_mode)
#   - GET /api-mode (get_api_mode)
#   - POST /api-mode (set_api_mode)
#   - GET /health (get_bot_health)
#   - GET /logs (get_bot_logs)
#   - GET /metrics (get_bot_metrics)
#   - GET /check-bot-access/{telegram_id} (check_bot_access)
#   - GET /check-bot-access/all (check_all_bot_access)
#   - GET /channel-status/{telegram_id} (check_user_channel_status)
#   - GET /channel-status/all (check_all_users_channel_status)
#   - GET /stats (get_stats)
#   - GET /topups (get_topups)
#
# Benefits of moving to this router:
# - Centralized admin endpoint management
# - Consistent URL structure (/api/admin/*)
# - Easier to add middleware or logging for admin actions
# - Cleaner separation from main API routes


# Example of how endpoints will look after refactoring:
# @admin_router.get("/users")
# async def get_users(db):
#     """Get all users"""
#     users = await db.users.find({}, {"_id": 0}).to_list(100)
#     return users
