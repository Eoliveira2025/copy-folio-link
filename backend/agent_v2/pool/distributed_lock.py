"""V2 Distributed Lock — prevents duplicate execution across multiple VPS/processes."""

import time
from uuid import UUID
from typing import Optional
from .redis_client import get_redis, k
from .utils.logger import get_logger
from .config import get_v2_settings

class DistributedLock:
    """Redis-based distributed lock for account execution isolation."""
    
    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("distributed_lock")
        self.vps_id = self.settings.V2_VPS_ID

    def acquire(self, account_id: UUID, ttl: int = None) -> bool:
        """Try to acquire lock for an account."""
        ttl = ttl or self.settings.V2_DISTRIBUTED_LOCK_TTL_S
        lock_key = f"lock:account:{account_id}"
        
        # NX = set if not exists, EX = expire in seconds
        # Value is VPS_ID so we know who owns it
        success = get_redis().set(k(lock_key), self.vps_id, nx=True, ex=ttl)
        
        if success:
            self.log.debug("lock acquired", extra={"account_id": str(account_id), "vps_id": self.vps_id})
            return True
            
        # Check if we already own it (re-entrant-ish for same VPS)
        current_owner = get_redis().get(k(lock_key))
        if current_owner == self.vps_id:
            # Refresh TTL
            get_redis().expire(k(lock_key), ttl)
            return True
            
        self.log.warning("lock acquisition failed - account owned by another VPS", 
                         extra={"account_id": str(account_id), "owner": current_owner})
        return False

    def release(self, account_id: UUID):
        """Release lock only if we own it."""
        lock_key = f"lock:account:{account_id}"
        # Script to ensure atomicity
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        get_redis().eval(lua, 1, k(lock_key), self.vps_id)

    def is_locked_by_me(self, account_id: UUID) -> bool:
        lock_key = f"lock:account:{account_id}"
        return get_redis().get(k(lock_key)) == self.vps_id
