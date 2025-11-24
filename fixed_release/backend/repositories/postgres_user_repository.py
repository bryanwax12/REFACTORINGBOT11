"""
PostgreSQL User Repository
Replacement for MongoDB user_repository
"""
import logging
from typing import Dict, List, Optional
from utils.simple_cache import cached, clear_user_cache

logger = logging.getLogger(__name__)


class PostgresUserRepository:
    """User repository for PostgreSQL"""
    
    def __init__(self, db_adapter):
        self.db = db_adapter
    
    @cached(ttl=30, key_prefix="user")
    async def find_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Find user by telegram ID (with 30s cache)"""
        return await self.db.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1",
            telegram_id
        )
    
    async def create_user(
        self,
        telegram_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
        initial_balance: float = 0.0
    ) -> Dict:
        """Create new user"""
        return await self.db.fetchrow('''
            INSERT INTO users (
                telegram_id, username, first_name, last_name, balance
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name
            RETURNING *
        ''', telegram_id, username, first_name, last_name, initial_balance)
    
    async def update_balance(self, telegram_id: int, new_balance: float) -> bool:
        """Update user balance"""
        result = await self.db.execute(
            "UPDATE users SET balance = $1, updated_at = NOW() WHERE telegram_id = $2",
            new_balance, telegram_id
        )
        if result:
            clear_user_cache(telegram_id)
        return result is not None
    
    async def get_balance(self, telegram_id: int) -> float:
        """Get user balance"""
        balance = await self.db.fetchval(
            "SELECT balance FROM users WHERE telegram_id = $1",
            telegram_id
        )
        return float(balance) if balance else 0.0
    
    async def update_user_field(self, telegram_id: int, field: str, value: any) -> bool:
        """Update user field"""
        # Sanitize field name (prevent SQL injection)
        allowed_fields = ['username', 'first_name', 'last_name', 'balance', 'blocked', 'is_channel_member']
        if field not in allowed_fields:
            logger.error(f"Attempt to update non-allowed field: {field}")
            return False
        
        result = await self.db.execute(
            f"UPDATE users SET {field} = $1, updated_at = NOW() WHERE telegram_id = $2",
            value, telegram_id
        )
        if result:
            clear_user_cache(telegram_id)
        return result is not None
    
    async def get_all_users(self) -> List[Dict]:
        """Get all users"""
        return await self.db.fetch("SELECT * FROM users ORDER BY created_at DESC")
    
    async def block_user(self, telegram_id: int) -> bool:
        """Block user"""
        return await self.update_user_field(telegram_id, 'blocked', True)
    
    async def unblock_user(self, telegram_id: int) -> bool:
        """Unblock user"""
        return await self.update_user_field(telegram_id, 'blocked', False)
