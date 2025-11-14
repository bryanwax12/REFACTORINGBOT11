"""
System Admin Service
Handles system-level operations for admin
"""
import logging
from typing import Dict, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SystemAdminService:
    """Service for system management operations"""
    
    @staticmethod
    async def get_maintenance_status(db) -> Dict:
        """
        Get maintenance mode status
        
        Args:
            db: Database instance
        
        Returns:
            Maintenance status
        """
        try:
            config = await db.config.find_one({"key": "maintenance_mode"})
            
            if config:
                return {
                    "enabled": config.get("enabled", False),
                    "message": config.get("message", ""),
                    "updated_at": config.get("updated_at")
                }
            else:
                return {
                    "enabled": False,
                    "message": "",
                    "updated_at": None
                }
        
        except Exception as e:
            logger.error(f"Error getting maintenance status: {e}")
            return {"error": str(e)}
    
    
    @staticmethod
    async def enable_maintenance(
        db,
        message: str = "Бот находится на обслуживании. Пожалуйста, попробуйте позже."
    ) -> Tuple[bool, str]:
        """
        Enable maintenance mode
        
        Args:
            db: Database instance
            message: Maintenance message to show users
        
        Returns:
            Tuple of (success, message)
        """
        try:
            await db.config.update_one(
                {"key": "maintenance_mode"},
                {"$set": {
                    "enabled": True,
                    "message": message,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            
            logger.info("Maintenance mode enabled")
            return True, "Maintenance mode enabled"
        
        except Exception as e:
            logger.error(f"Error enabling maintenance: {e}")
            return False, str(e)
    
    
    @staticmethod
    async def disable_maintenance(db) -> Tuple[bool, str]:
        """
        Disable maintenance mode
        
        Args:
            db: Database instance
        
        Returns:
            Tuple of (success, message)
        """
        try:
            await db.config.update_one(
                {"key": "maintenance_mode"},
                {"$set": {
                    "enabled": False,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            
            logger.info("Maintenance mode disabled")
            return True, "Maintenance mode disabled"
        
        except Exception as e:
            logger.error(f"Error disabling maintenance: {e}")
            return False, str(e)
    
    
    @staticmethod
    async def clear_all_sessions(db, session_manager) -> Tuple[bool, int, str]:
        """
        Clear all user sessions
        
        Args:
            db: Database instance
            session_manager: Session manager instance
        
        Returns:
            Tuple of (success, count_cleared, message)
        """
        try:
            result = await db.user_sessions.delete_many({})
            count = result.deleted_count
            
            logger.info(f"Cleared {count} sessions")
            return True, count, f"Cleared {count} sessions"
        
        except Exception as e:
            logger.error(f"Error clearing sessions: {e}")
            return False, 0, str(e)
    
    
    @staticmethod
    async def get_api_mode(db) -> Dict:
        """
        Get API-only mode status
        
        Args:
            db: Database instance
        
        Returns:
            API mode status
        """
        try:
            config = await db.config.find_one({"key": "api_only_mode"})
            
            if config:
                return {
                    "enabled": config.get("enabled", False),
                    "updated_at": config.get("updated_at")
                }
            else:
                return {
                    "enabled": False,
                    "updated_at": None
                }
        
        except Exception as e:
            logger.error(f"Error getting API mode: {e}")
            return {"error": str(e)}
    
    
    @staticmethod
    async def set_api_mode(db, enabled: bool) -> Tuple[bool, str]:
        """
        Set API-only mode
        
        Args:
            db: Database instance
            enabled: Whether to enable API-only mode
        
        Returns:
            Tuple of (success, message)
        """
        try:
            await db.config.update_one(
                {"key": "api_only_mode"},
                {"$set": {
                    "enabled": enabled,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            
            status = "enabled" if enabled else "disabled"
            logger.info(f"API-only mode {status}")
            return True, f"API-only mode {status}"
        
        except Exception as e:
            logger.error(f"Error setting API mode: {e}")
            return False, str(e)
    
    
    @staticmethod
    async def check_shipstation_balance() -> Dict:
        """
        Check ShipStation account balance
        
        Returns:
            Balance information
        """
        import os
        import aiohttp
        import base64
        
        try:
            api_key = os.environ.get('SHIPSTATION_API_KEY')
            api_secret = os.environ.get('SHIPSTATION_API_SECRET')
            
            if not api_key or not api_secret:
                return {"error": "ShipStation credentials not configured"}
            
            # Create basic auth
            credentials = f"{api_key}:{api_secret}"
            encoded = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json"
            }
            
            # Check account info (balance not directly available in API)
            # This is a placeholder - actual implementation depends on ShipStation API
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://ssapi.shipstation.com/accounts/listaccounts",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "data": data,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"API returned {response.status}: {error_text}"
                        }
        
        except Exception as e:
            logger.error(f"Error checking ShipStation balance: {e}")
            return {"success": False, "error": str(e)}
    
    
    @staticmethod
    async def get_system_logs(
        db,
        level: str = "ERROR",
        limit: int = 100
    ) -> Dict:
        """
        Get system logs
        
        Args:
            db: Database instance
            level: Log level filter
            limit: Number of logs to return
        
        Returns:
            System logs
        """
        # This is a placeholder - actual implementation depends on logging setup
        # You might want to read from log files or a logs collection
        
        import subprocess
        
        try:
            # Read from supervisor logs
            cmd = f"tail -n {limit} /var/log/supervisor/backend.err.log"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logs = result.stdout.split('\n')
                # Filter by level if specified
                if level and level != "ALL":
                    logs = [l for l in logs if level in l]
                
                return {
                    "logs": logs[-limit:],
                    "count": len(logs[-limit:]),
                    "level": level
                }
            else:
                return {"error": "Failed to read logs"}
        
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return {"error": str(e)}


# Singleton instance
system_admin_service = SystemAdminService()
