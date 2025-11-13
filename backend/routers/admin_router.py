"""
Admin API Router
Centralized router for all admin-only API endpoints

Note: Currently endpoints are still in server.py
This is a preparatory structure for gradual migration
"""
from fastapi import APIRouter, Depends
from handlers.admin_handlers import verify_admin_key
import logging

logger = logging.getLogger(__name__)

# Create admin router with prefix
# Note: NOT USING dependencies=[Depends(verify_admin_key)] globally
# because each endpoint in server.py already has this dependency
admin_router = APIRouter(
    prefix="/api/admin",
    tags=["admin"]
)

# ============================================================
# MIGRATION STATUS: 0/22 endpoints moved
# ============================================================
# 
# Remaining in server.py (22 endpoints):
# 1.  GET    /users                         get_users
# 2.  POST   /users/{id}/block              block_user
# 3.  POST   /users/{id}/unblock            unblock_user
# 4.  POST   /users/{id}/invite-channel     invite_user_to_channel
# 5.  POST   /users/invite-channel/all      invite_all_users_to_channel
# 6.  GET    /maintenance                   get_maintenance_status
# 7.  POST   /maintenance/enable            enable_maintenance_mode
# 8.  POST   /maintenance/disable           disable_maintenance_mode
# 9.  GET    /api-mode                      get_api_mode
# 10. POST   /api-mode                      set_api_mode
# 11. GET    /health                        get_bot_health
# 12. GET    /logs                          get_bot_logs
# 13. GET    /metrics                       get_bot_metrics
# 14. GET    /check-bot-access/{id}         check_bot_access
# 15. GET    /check-bot-access/all          check_all_bot_access
# 16. GET    /channel-status/{id}           check_user_channel_status
# 17. GET    /channel-status/all            check_all_users_channel_status
# 18. GET    /stats                         get_stats
# 19. GET    /topups                        get_topups
# 20. POST   /clear-conversations           clear_all_conversations
# 21. POST   /shipstation/check-balance     check_shipstation_balance_endpoint
# 22. GET    /performance/stats             get_performance_stats
#
# ============================================================
# MIGRATION STRATEGY (for future work):
# ============================================================
# 1. Move endpoints one-by-one or in small groups
# 2. Test each migration before proceeding
# 3. Update URL paths from /api/{endpoint} to /api/admin/{endpoint}
# 4. Keep authentication dependency on each endpoint
# 5. Import necessary dependencies (db, bot_instance, etc.)
#
# Benefits after full migration:
# - Clean separation of admin vs public endpoints
# - Consistent /api/admin/* URL structure
# - Easier to add admin-specific middleware
# - Better organization and maintainability
# ============================================================


# Example of migrated endpoint structure:
# @admin_router.get("/users")
# async def get_users(authenticated: bool = Depends(verify_admin_key)):
#     """Get all users"""
#     from server import db
#     users = await db.users.find({}, {"_id": 0}).to_list(100)
#     return users
