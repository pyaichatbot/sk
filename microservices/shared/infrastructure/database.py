# ============================================================================
# microservices/shared/infrastructure/database.py
# ============================================================================
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import asyncpg
from asyncpg import Pool, Connection
import logging

from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database connection manager for PostgreSQL"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.pool: Optional[Pool] = None
        self._connection_count = 0
        self._max_connections = settings.postgres_pool_size + settings.postgres_max_overflow
    
    async def initialize(self) -> None:
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.settings.postgres_host,
                port=self.settings.postgres_port,
                user=self.settings.postgres_user,
                password=self.settings.postgres_password,
                database=self.settings.postgres_db,
                min_size=1,
                max_size=self.settings.postgres_pool_size,
                max_queries=50000,
                max_inactive_connection_lifetime=300.0,
                command_timeout=60,
                server_settings={
                    'application_name': f"{self.settings.service_name}_microservice",
                    'jit': 'off'
                }
            )
            
            logger.info(
                "Database connection pool initialized",
                service=self.settings.service_name,
                host=self.settings.postgres_host,
                port=self.settings.postgres_port,
                database=self.settings.postgres_db,
                pool_size=self.settings.postgres_pool_size
            )
            
        except Exception as e:
            logger.error(
                f"Failed to initialize database connection pool: {str(e)} (service: {self.settings.service_name})"
            )
            raise
    
    async def close(self) -> None:
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info(
                "Database connection pool closed",
                service=self.settings.service_name
            )
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        connection = None
        try:
            connection = await self.pool.acquire()
            self._connection_count += 1
            yield connection
        finally:
            if connection:
                await self.pool.release(connection)
                self._connection_count -= 1
    
    async def execute_query(
        self, 
        query: str, 
        *args, 
        fetch: bool = False,
        fetch_one: bool = False
    ) -> Any:
        """Execute database query"""
        async with self.get_connection() as conn:
            if fetch_one:
                return await conn.fetchrow(query, *args)
            elif fetch:
                return await conn.fetch(query, *args)
            else:
                return await conn.execute(query, *args)
    
    async def execute_transaction(self, queries: List[tuple]) -> List[Any]:
        """Execute multiple queries in a transaction"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                results = []
                for query, args in queries:
                    if isinstance(args, (list, tuple)):
                        result = await conn.execute(query, *args)
                    else:
                        result = await conn.execute(query, args)
                    results.append(result)
                return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Test basic connectivity
            result = await self.execute_query(
                "SELECT 1 as health_check, NOW() as timestamp",
                fetch_one=True
            )
            
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            # Get connection pool stats
            pool_stats = {
                "size": self.pool.get_size() if self.pool else 0,
                "idle_size": self.pool.get_idle_size() if self.pool else 0,
                "active_connections": self._connection_count,
                "max_connections": self._max_connections
            }
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "timestamp": result["timestamp"] if result else None,
                "pool_stats": pool_stats
            }
            
        except Exception as e:
            logger.error(
                "Database health check failed",
                error=str(e),
                service=self.settings.service_name
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "pool_stats": {
                    "size": 0,
                    "idle_size": 0,
                    "active_connections": self._connection_count,
                    "max_connections": self._max_connections
                }
            }
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get database connection information"""
        try:
            result = await self.execute_query(
                """
                SELECT 
                    current_database() as database,
                    current_user as user,
                    inet_server_addr() as host,
                    inet_server_port() as port,
                    version() as version
                """,
                fetch_one=True
            )
            
            return {
                "database": result["database"],
                "user": result["user"],
                "host": result["host"],
                "port": result["port"],
                "version": result["version"],
                "pool_size": self.pool.get_size() if self.pool else 0,
                "active_connections": self._connection_count
            }
            
        except Exception as e:
            logger.error(
                "Failed to get database connection info",
                error=str(e),
                service=self.settings.service_name
            )
            return {"error": str(e)}

# Global database manager instance
_database_manager: Optional[DatabaseManager] = None

def get_database_manager() -> Optional[DatabaseManager]:
    """Get the global database manager instance"""
    return _database_manager

def set_database_manager(manager: DatabaseManager) -> None:
    """Set the global database manager instance"""
    global _database_manager
    _database_manager = manager
