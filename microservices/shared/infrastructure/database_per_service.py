# ============================================================================
# microservices/shared/infrastructure/database_per_service.py
# ============================================================================
"""
Database Per Service Implementation for Microservices Architecture.
Provides isolated database schemas and connection management for each service.
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
from contextlib import asynccontextmanager
from enum import Enum
from dataclasses import dataclass
import asyncpg
from asyncpg import Pool, Connection
import logging
from datetime import datetime

from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class ServiceDatabase(str, Enum):
    """Service-specific database identifiers"""
    API_GATEWAY = "api_gateway"
    ORCHESTRATION = "orchestration"
    RAG_AGENT = "rag_agent"
    SEARCH_AGENT = "search_agent"
    JIRA_AGENT = "jira_agent"
    LLM_AGENT = "llm_agent"

@dataclass
class DatabaseSchema:
    """Database schema configuration"""
    service_name: str
    schema_name: str
    tables: List[str]
    indexes: List[str]
    functions: List[str]
    triggers: List[str]

@dataclass
class DatabaseMigration:
    """Database migration definition"""
    version: str
    description: str
    up_sql: str
    down_sql: str
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

class ServiceDatabaseManager:
    """Enterprise Database Manager with per-service isolation"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.service_name = settings.service_name
        self.pools: Dict[str, Pool] = {}
        self.schemas: Dict[str, DatabaseSchema] = {}
        self.migrations: Dict[str, List[DatabaseMigration]] = {}
        self._initialized = False
        
        # Initialize service-specific schemas
        self._initialize_service_schemas()
        self._initialize_migrations()
    
    def _initialize_service_schemas(self) -> None:
        """Initialize database schemas for each service"""
        
        # API Gateway Schema
        self.schemas[ServiceDatabase.API_GATEWAY] = DatabaseSchema(
            service_name="api_gateway",
            schema_name="api_gateway",
            tables=[
                "api_keys", "rate_limits", "request_logs", "user_sessions",
                "api_versions", "endpoint_configs", "security_policies"
            ],
            indexes=[
                "idx_api_keys_key", "idx_rate_limits_user", "idx_request_logs_timestamp",
                "idx_user_sessions_token", "idx_endpoint_configs_path"
            ],
            functions=[
                "check_rate_limit", "log_api_request", "validate_api_key",
                "cleanup_expired_sessions", "get_endpoint_config"
            ],
            triggers=[
                "trg_update_request_log", "trg_cleanup_old_logs"
            ]
        )
        
        # Orchestration Schema
        self.schemas[ServiceDatabase.ORCHESTRATION] = DatabaseSchema(
            service_name="orchestration",
            schema_name="orchestration",
            tables=[
                "orchestration_sessions", "orchestration_steps", "agent_coordinations",
                "workflow_templates", "execution_metrics", "session_contexts"
            ],
            indexes=[
                "idx_sessions_id", "idx_steps_session", "idx_coordinations_agents",
                "idx_templates_name", "idx_metrics_timestamp", "idx_contexts_session"
            ],
            functions=[
                "create_orchestration_session", "add_orchestration_step",
                "update_session_context", "get_agent_coordination",
                "calculate_execution_metrics"
            ],
            triggers=[
                "trg_update_session_modified", "trg_log_step_completion"
            ]
        )
        
        # RAG Agent Schema
        self.schemas[ServiceDatabase.RAG_AGENT] = DatabaseSchema(
            service_name="rag_agent",
            schema_name="rag_agent",
            tables=[
                "documents", "document_chunks", "embeddings", "document_metadata",
                "search_queries", "retrieval_results", "document_versions"
            ],
            indexes=[
                "idx_documents_id", "idx_chunks_document", "idx_embeddings_vector",
                "idx_metadata_document", "idx_queries_timestamp", "idx_results_query"
            ],
            functions=[
                "store_document", "create_embeddings", "search_similar_chunks",
                "update_document_metadata", "get_document_history"
            ],
            triggers=[
                "trg_update_document_modified", "trg_create_document_version"
            ]
        )
        
        # Search Agent Schema
        self.schemas[ServiceDatabase.SEARCH_AGENT] = DatabaseSchema(
            service_name="search_agent",
            schema_name="search_agent",
            tables=[
                "search_queries", "search_results", "search_cache", "search_engines",
                "query_analytics", "result_ratings", "search_history"
            ],
            indexes=[
                "idx_queries_timestamp", "idx_results_query", "idx_cache_key",
                "idx_engines_name", "idx_analytics_date", "idx_ratings_result"
            ],
            functions=[
                "store_search_query", "cache_search_result", "get_search_analytics",
                "rate_search_result", "cleanup_old_cache"
            ],
            triggers=[
                "trg_update_query_timestamp", "trg_log_search_analytics"
            ]
        )
        
        # JIRA Agent Schema
        self.schemas[ServiceDatabase.JIRA_AGENT] = DatabaseSchema(
            service_name="jira_agent",
            schema_name="jira_agent",
            tables=[
                "jira_projects", "jira_issues", "jira_users", "jira_workflows",
                "issue_comments", "issue_attachments", "project_metrics"
            ],
            indexes=[
                "idx_projects_key", "idx_issues_id", "idx_users_email",
                "idx_workflows_project", "idx_comments_issue", "idx_attachments_issue"
            ],
            functions=[
                "sync_jira_project", "update_issue_status", "get_project_metrics",
                "store_issue_comment", "track_issue_changes"
            ],
            triggers=[
                "trg_update_issue_modified", "trg_log_issue_changes"
            ]
        )
        
        # LLM Agent Schema
        self.schemas[ServiceDatabase.LLM_AGENT] = DatabaseSchema(
            service_name="llm_agent",
            schema_name="llm_agent",
            tables=[
                "llm_models", "conversation_sessions", "conversation_messages",
                "model_metrics", "token_usage", "response_cache"
            ],
            indexes=[
                "idx_models_name", "idx_sessions_id", "idx_messages_session",
                "idx_metrics_model", "idx_usage_timestamp", "idx_cache_key"
            ],
            functions=[
                "store_conversation", "track_token_usage", "get_model_metrics",
                "cache_llm_response", "cleanup_old_sessions"
            ],
            triggers=[
                "trg_update_session_modified", "trg_log_token_usage"
            ]
        )
    
    def _initialize_migrations(self) -> None:
        """Initialize database migrations for each service"""
        
        # Common migration for all services
        common_migration = DatabaseMigration(
            version="001",
            description="Create service schema and basic tables",
            up_sql="""
                CREATE SCHEMA IF NOT EXISTS {schema_name};
                GRANT USAGE ON SCHEMA {schema_name} TO {service_user};
                GRANT CREATE ON SCHEMA {schema_name} TO {service_user};
                GRANT ALL ON ALL TABLES IN SCHEMA {schema_name} TO {service_user};
                GRANT ALL ON ALL SEQUENCES IN SCHEMA {schema_name} TO {service_user};
            """,
            down_sql="DROP SCHEMA IF EXISTS {schema_name} CASCADE;"
        )
        
        for service_db in ServiceDatabase:
            self.migrations[service_db] = [common_migration]
    
    async def initialize(self) -> None:
        """Initialize database connections and schemas for the service"""
        try:
            # Create main connection pool
            await self._create_connection_pool()
            
            # Create service schema
            await self._create_service_schema()
            
            # Run migrations
            await self._run_migrations()
            
            # Create tables, indexes, functions, and triggers
            await self._create_database_objects()
            
            self._initialized = True
            
            logger.info(
                "Service database initialized successfully",
                service=self.service_name,
                schema=self.schemas.get(self.service_name, {}).schema_name
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize service database",
                service=self.service_name,
                error=str(e)
            )
            raise
    
    async def _create_connection_pool(self) -> None:
        """Create database connection pool for the service"""
        try:
            pool = await asyncpg.create_pool(
                host=self.settings.postgres_host,
                port=self.settings.postgres_port,
                user=self.settings.postgres_user,
                password=self.settings.postgres_password,
                database=self.settings.postgres_db,
                min_size=2,
                max_size=self.settings.postgres_pool_size,
                max_queries=50000,
                max_inactive_connection_lifetime=300.0,
                command_timeout=60,
                server_settings={
                    'application_name': f"{self.service_name}_microservice",
                    'jit': 'off',
                    'search_path': f"{self.schemas.get(self.service_name, {}).schema_name}, public"
                }
            )
            
            self.pools[self.service_name] = pool
            
            logger.info(
                "Database connection pool created",
                service=self.service_name,
                pool_size=self.settings.postgres_pool_size
            )
            
        except Exception as e:
            logger.error(
                "Failed to create database connection pool",
                service=self.service_name,
                error=str(e)
            )
            raise
    
    async def _create_service_schema(self) -> None:
        """Create database schema for the service"""
        schema = self.schemas.get(self.service_name)
        if not schema:
            logger.warning(
                "No schema configuration found for service",
                service=self.service_name
            )
            return
        
        try:
            async with self.get_connection() as conn:
                # Create schema
                await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema.schema_name}")
                
                # Set permissions
                await conn.execute(f"GRANT USAGE ON SCHEMA {schema.schema_name} TO {self.settings.postgres_user}")
                await conn.execute(f"GRANT CREATE ON SCHEMA {schema.schema_name} TO {self.settings.postgres_user}")
                
                logger.info(
                    "Service schema created",
                    service=self.service_name,
                    schema=schema.schema_name
                )
                
        except Exception as e:
            logger.error(
                "Failed to create service schema",
                service=self.service_name,
                schema=schema.schema_name,
                error=str(e)
            )
            raise
    
    async def _run_migrations(self) -> None:
        """Run database migrations for the service"""
        service_migrations = self.migrations.get(self.service_name, [])
        if not service_migrations:
            logger.info(
                "No migrations found for service",
                service=self.service_name
            )
            return
        
        try:
            async with self.get_connection() as conn:
                # Create migrations table if not exists
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS public.schema_migrations (
                        service_name VARCHAR(50) NOT NULL,
                        version VARCHAR(20) NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (service_name, version)
                    )
                """)
                
                # Get applied migrations
                applied_migrations = await conn.fetch(
                    "SELECT version FROM public.schema_migrations WHERE service_name = $1",
                    self.service_name
                )
                applied_versions = {row['version'] for row in applied_migrations}
                
                # Run pending migrations
                for migration in service_migrations:
                    if migration.version not in applied_versions:
                        logger.info(
                            "Running migration",
                            service=self.service_name,
                            version=migration.version,
                            description=migration.description
                        )
                        
                        # Execute migration SQL
                        up_sql = migration.up_sql.format(
                            schema_name=self.schemas.get(self.service_name, {}).schema_name,
                            service_user=self.settings.postgres_user
                        )
                        await conn.execute(up_sql)
                        
                        # Record migration
                        await conn.execute(
                            "INSERT INTO public.schema_migrations (service_name, version) VALUES ($1, $2)",
                            self.service_name, migration.version
                        )
                        
                        logger.info(
                            "Migration completed",
                            service=self.service_name,
                            version=migration.version
                        )
                
        except Exception as e:
            logger.error(
                "Failed to run migrations",
                service=self.service_name,
                error=str(e)
            )
            raise
    
    async def _create_database_objects(self) -> None:
        """Create tables, indexes, functions, and triggers for the service"""
        schema = self.schemas.get(self.service_name)
        if not schema:
            return
        
        try:
            async with self.get_connection() as conn:
                # Create service-specific tables
                await self._create_service_tables(conn, schema)
                
                # Create indexes
                await self._create_service_indexes(conn, schema)
                
                # Create functions
                await self._create_service_functions(conn, schema)
                
                # Create triggers
                await self._create_service_triggers(conn, schema)
                
                logger.info(
                    "Database objects created",
                    service=self.service_name,
                    tables=len(schema.tables),
                    indexes=len(schema.indexes),
                    functions=len(schema.functions),
                    triggers=len(schema.triggers)
                )
                
        except Exception as e:
            logger.error(
                "Failed to create database objects",
                service=self.service_name,
                error=str(e)
            )
            raise
    
    async def _create_service_tables(self, conn: Connection, schema: DatabaseSchema) -> None:
        """Create service-specific tables"""
        table_definitions = self._get_table_definitions(schema.service_name)
        
        for table_name, table_sql in table_definitions.items():
            try:
                await conn.execute(table_sql)
                logger.debug(
                    "Table created",
                    service=self.service_name,
                    table=table_name
                )
            except Exception as e:
                logger.error(
                    "Failed to create table",
                    service=self.service_name,
                    table=table_name,
                    error=str(e)
                )
                raise
    
    async def _create_service_indexes(self, conn: Connection, schema: DatabaseSchema) -> None:
        """Create service-specific indexes"""
        index_definitions = self._get_index_definitions(schema.service_name)
        
        for index_name, index_sql in index_definitions.items():
            try:
                await conn.execute(index_sql)
                logger.debug(
                    "Index created",
                    service=self.service_name,
                    index=index_name
                )
            except Exception as e:
                logger.error(
                    "Failed to create index",
                    service=self.service_name,
                    index=index_name,
                    error=str(e)
                )
                raise
    
    async def _create_service_functions(self, conn: Connection, schema: DatabaseSchema) -> None:
        """Create service-specific functions"""
        function_definitions = self._get_function_definitions(schema.service_name)
        
        for function_name, function_sql in function_definitions.items():
            try:
                await conn.execute(function_sql)
                logger.debug(
                    "Function created",
                    service=self.service_name,
                    function=function_name
                )
            except Exception as e:
                logger.error(
                    "Failed to create function",
                    service=self.service_name,
                    function=function_name,
                    error=str(e)
                )
                raise
    
    async def _create_service_triggers(self, conn: Connection, schema: DatabaseSchema) -> None:
        """Create service-specific triggers"""
        trigger_definitions = self._get_trigger_definitions(schema.service_name)
        
        for trigger_name, trigger_sql in trigger_definitions.items():
            try:
                await conn.execute(trigger_sql)
                logger.debug(
                    "Trigger created",
                    service=self.service_name,
                    trigger=trigger_name
                )
            except Exception as e:
                logger.error(
                    "Failed to create trigger",
                    service=self.service_name,
                    trigger=trigger_name,
                    error=str(e)
                )
                raise
    
    def _get_table_definitions(self, service_name: str) -> Dict[str, str]:
        """Get table definitions for the service"""
        schema_name = self.schemas.get(service_name, {}).schema_name
        
        if service_name == "api_gateway":
            return {
                "api_keys": f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.api_keys (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        key_hash VARCHAR(255) UNIQUE NOT NULL,
                        service_name VARCHAR(100) NOT NULL,
                        permissions JSONB DEFAULT '{{}}',
                        rate_limit INTEGER DEFAULT 1000,
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "rate_limits": f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.rate_limits (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        api_key_id UUID REFERENCES {schema_name}.api_keys(id),
                        endpoint VARCHAR(255) NOT NULL,
                        request_count INTEGER DEFAULT 0,
                        window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "request_logs": f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.request_logs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        api_key_id UUID REFERENCES {schema_name}.api_keys(id),
                        endpoint VARCHAR(255) NOT NULL,
                        method VARCHAR(10) NOT NULL,
                        status_code INTEGER,
                        response_time_ms INTEGER,
                        request_size INTEGER,
                        response_size INTEGER,
                        user_agent TEXT,
                        ip_address INET,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            }
        
        elif service_name == "orchestration":
            return {
                "orchestration_sessions": f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.orchestration_sessions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        session_id VARCHAR(255) UNIQUE NOT NULL,
                        pattern VARCHAR(50) NOT NULL,
                        status VARCHAR(20) DEFAULT 'active',
                        context JSONB DEFAULT '{{}}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """,
                "orchestration_steps": f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.orchestration_steps (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        session_id UUID REFERENCES {schema_name}.orchestration_sessions(id),
                        step_order INTEGER NOT NULL,
                        agent_name VARCHAR(100) NOT NULL,
                        input_data JSONB,
                        output_data JSONB,
                        status VARCHAR(20) DEFAULT 'pending',
                        error_message TEXT,
                        execution_time_ms INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """
            }
        
        elif service_name == "rag_agent":
            return {
                "documents": f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.documents (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        document_id VARCHAR(255) UNIQUE NOT NULL,
                        file_name VARCHAR(255) NOT NULL,
                        file_type VARCHAR(50) NOT NULL,
                        file_size INTEGER NOT NULL,
                        content_hash VARCHAR(255) NOT NULL,
                        metadata JSONB DEFAULT '{{}}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "document_chunks": f"""
                    CREATE TABLE IF NOT EXISTS {schema_name}.document_chunks (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        document_id UUID REFERENCES {schema_name}.documents(id),
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding_vector VECTOR(1536),
                        metadata JSONB DEFAULT '{{}}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            }
        
        # Add more service-specific table definitions as needed
        return {}
    
    def _get_index_definitions(self, service_name: str) -> Dict[str, str]:
        """Get index definitions for the service"""
        schema_name = self.schemas.get(service_name, {}).schema_name
        
        if service_name == "api_gateway":
            return {
                "idx_api_keys_key": f"CREATE INDEX IF NOT EXISTS idx_api_keys_key ON {schema_name}.api_keys(key_hash)",
                "idx_rate_limits_user": f"CREATE INDEX IF NOT EXISTS idx_rate_limits_user ON {schema_name}.rate_limits(api_key_id, endpoint)",
                "idx_request_logs_timestamp": f"CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON {schema_name}.request_logs(created_at)"
            }
        
        elif service_name == "orchestration":
            return {
                "idx_sessions_id": f"CREATE INDEX IF NOT EXISTS idx_sessions_id ON {schema_name}.orchestration_sessions(session_id)",
                "idx_steps_session": f"CREATE INDEX IF NOT EXISTS idx_steps_session ON {schema_name}.orchestration_steps(session_id, step_order)"
            }
        
        elif service_name == "rag_agent":
            return {
                "idx_documents_id": f"CREATE INDEX IF NOT EXISTS idx_documents_id ON {schema_name}.documents(document_id)",
                "idx_chunks_document": f"CREATE INDEX IF NOT EXISTS idx_chunks_document ON {schema_name}.document_chunks(document_id, chunk_index)"
            }
        
        return {}
    
    def _get_function_definitions(self, service_name: str) -> Dict[str, str]:
        """Get function definitions for the service"""
        schema_name = self.schemas.get(service_name, {}).schema_name
        
        if service_name == "api_gateway":
            return {
                "check_rate_limit": f"""
                    CREATE OR REPLACE FUNCTION {schema_name}.check_rate_limit(
                        p_api_key_id UUID,
                        p_endpoint VARCHAR(255),
                        p_limit INTEGER DEFAULT 1000
                    ) RETURNS BOOLEAN AS $$
                    DECLARE
                        current_count INTEGER;
                    BEGIN
                        SELECT request_count INTO current_count
                        FROM {schema_name}.rate_limits
                        WHERE api_key_id = p_api_key_id
                        AND endpoint = p_endpoint
                        AND window_start > CURRENT_TIMESTAMP - INTERVAL '1 minute';
                        
                        IF current_count IS NULL THEN
                            INSERT INTO {schema_name}.rate_limits (api_key_id, endpoint, request_count)
                            VALUES (p_api_key_id, p_endpoint, 1);
                            RETURN TRUE;
                        ELSIF current_count < p_limit THEN
                            UPDATE {schema_name}.rate_limits
                            SET request_count = request_count + 1
                            WHERE api_key_id = p_api_key_id AND endpoint = p_endpoint;
                            RETURN TRUE;
                        ELSE
                            RETURN FALSE;
                        END IF;
                    END;
                    $$ LANGUAGE plpgsql;
                """
            }
        
        return {}
    
    def _get_trigger_definitions(self, service_name: str) -> Dict[str, str]:
        """Get trigger definitions for the service"""
        schema_name = self.schemas.get(service_name, {}).schema_name
        
        if service_name == "api_gateway":
            return {
                "trg_update_request_log": f"""
                    CREATE OR REPLACE FUNCTION {schema_name}.update_request_log()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                    
                    CREATE TRIGGER trg_update_request_log
                    BEFORE UPDATE ON {schema_name}.request_logs
                    FOR EACH ROW EXECUTE FUNCTION {schema_name}.update_request_log();
                """
            }
        
        return {}
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self._initialized:
            raise RuntimeError("Database manager not initialized")
        
        pool = self.pools.get(self.service_name)
        if not pool:
            raise RuntimeError(f"No connection pool found for service: {self.service_name}")
        
        connection = None
        try:
            connection = await pool.acquire()
            yield connection
        finally:
            if connection:
                await pool.release(connection)
    
    async def execute_query(
        self,
        query: str,
        *args,
        fetch: bool = False,
        fetch_one: bool = False
    ) -> Any:
        """Execute database query in service schema"""
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
                "SELECT 1 as health_check, NOW() as timestamp, current_schema() as current_schema",
                fetch_one=True
            )
            
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000
            
            # Get connection pool stats
            pool = self.pools.get(self.service_name)
            pool_stats = {
                "size": pool.get_size() if pool else 0,
                "idle_size": pool.get_idle_size() if pool else 0,
                "max_size": self.settings.postgres_pool_size
            }
            
            return {
                "status": "healthy",
                "service": self.service_name,
                "schema": result["current_schema"] if result else None,
                "response_time_ms": response_time,
                "timestamp": result["timestamp"] if result else None,
                "pool_stats": pool_stats
            }
            
        except Exception as e:
            logger.error(
                "Database health check failed",
                service=self.service_name,
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "service": self.service_name,
                "error": str(e),
                "pool_stats": {
                    "size": 0,
                    "idle_size": 0,
                    "max_size": self.settings.postgres_pool_size
                }
            }
    
    async def close(self) -> None:
        """Close database connections"""
        for service_name, pool in self.pools.items():
            try:
                await pool.close()
                logger.info(
                    "Database connection pool closed",
                    service=service_name
                )
            except Exception as e:
                logger.error(
                    "Error closing database connection pool",
                    service=service_name,
                    error=str(e)
                )
        
        self._initialized = False

# Global service database manager instance
_service_database_manager: Optional[ServiceDatabaseManager] = None

def get_service_database_manager() -> Optional[ServiceDatabaseManager]:
    """Get the global service database manager instance"""
    return _service_database_manager

def set_service_database_manager(manager: ServiceDatabaseManager) -> None:
    """Set the global service database manager instance"""
    global _service_database_manager
    _service_database_manager = manager
