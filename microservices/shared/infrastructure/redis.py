# ============================================================================
# microservices/shared/infrastructure/redis.py
# ============================================================================
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import redis.asyncio as redis
import logging

from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class RedisManager:
    """Redis connection manager for microservices"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.client: Optional[redis.Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
    
    async def initialize(self) -> None:
        """Initialize Redis connection"""
        try:
            # Create connection pool
            self._connection_pool = redis.ConnectionPool.from_url(
                self.settings.redis_url,
                max_connections=self.settings.redis_pool_size,
                retry_on_timeout=True,
                socket_connect_timeout=self.settings.redis_timeout,
                socket_timeout=self.settings.redis_timeout
            )
            
            # Create Redis client
            self.client = redis.Redis(connection_pool=self._connection_pool)
            
            # Test connection
            await self.client.ping()
            
            logger.info(
                "Redis connection established",
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            raise
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.client:
            await self.client.close()
        if self._connection_pool:
            await self._connection_pool.disconnect()
        logger.info("Redis connection closed")
    
    @asynccontextmanager
    async def get_client(self):
        """Get Redis client from pool"""
        if not self.client:
            raise RuntimeError("Redis client not initialized")
        
        try:
            yield self.client
        finally:
            pass  # Client is managed by connection pool
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a key-value pair"""
        try:
            async with self.get_client() as client:
                return await client.set(key, value, ex=expire)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        try:
            async with self.get_client() as client:
                return await client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key"""
        try:
            async with self.get_client() as client:
                result = await client.delete(key)
                return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            async with self.get_client() as client:
                result = await client.exists(key)
                return result > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key"""
        try:
            async with self.get_client() as client:
                return await client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform Redis health check"""
        try:
            if not self.client:
                return {
                    "status": "unhealthy",
                    "error": "Redis client not initialized"
                }
            
            start_time = asyncio.get_event_loop().time()
            
            # Test basic connectivity
            await self.client.ping()
            
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            # Get Redis info
            info = await self.client.info()
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory": info.get("used_memory_human"),
                "uptime": info.get("uptime_in_seconds")
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Global Redis manager instance
_redis_manager: Optional[RedisManager] = None

def get_redis_manager() -> Optional[RedisManager]:
    """Get the global Redis manager instance"""
    return _redis_manager

def set_redis_manager(manager: RedisManager) -> None:
    """Set the global Redis manager instance"""
    global _redis_manager
    _redis_manager = manager
