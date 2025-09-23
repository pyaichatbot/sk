# ============================================================================
# microservices/orchestration/database_integration.py
# ============================================================================
"""
Database integration for Orchestration Service using Database Per Service pattern.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from shared.infrastructure.database_per_service import ServiceDatabaseManager
from shared.config.settings import MicroserviceSettings
from shared.models import OrchestrationRequest, OrchestrationResponse, OrchestrationStep

logger = logging.getLogger(__name__)

class OrchestrationDatabaseIntegration:
    """Database integration for orchestration service with per-service isolation"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.db_manager: Optional[ServiceDatabaseManager] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection and schema"""
        try:
            self.db_manager = ServiceDatabaseManager(self.settings)
            await self.db_manager.initialize()
            self._initialized = True
            
            logger.info(
                "Orchestration database integration initialized",
                service=self.settings.service_name
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize orchestration database integration",
                error=str(e),
                service=self.settings.service_name
            )
            raise
    
    async def create_orchestration_session(
        self,
        session_id: str,
        pattern: str,
        context: Dict[str, Any] = None
    ) -> str:
        """Create a new orchestration session"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            session_uuid = await self.db_manager.execute_query(
                """
                INSERT INTO orchestration.orchestration_sessions 
                (session_id, pattern, status, context, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                session_id,
                pattern,
                "active",
                json.dumps(context or {}),
                datetime.utcnow(),
                datetime.utcnow(),
                fetch_one=True
            )
            
            logger.info(
                "Orchestration session created",
                session_id=session_id,
                pattern=pattern,
                session_uuid=session_uuid["id"]
            )
            
            return str(session_uuid["id"])
            
        except Exception as e:
            logger.error(
                "Failed to create orchestration session",
                session_id=session_id,
                error=str(e)
            )
            raise
    
    async def add_orchestration_step(
        self,
        session_id: str,
        step_order: int,
        agent_name: str,
        input_data: Dict[str, Any] = None,
        output_data: Dict[str, Any] = None,
        status: str = "pending"
    ) -> str:
        """Add a step to an orchestration session"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            # Get session UUID
            session = await self.db_manager.execute_query(
                "SELECT id FROM orchestration.orchestration_sessions WHERE session_id = $1",
                session_id,
                fetch_one=True
            )
            
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            
            step_uuid = await self.db_manager.execute_query(
                """
                INSERT INTO orchestration.orchestration_steps
                (session_id, step_order, agent_name, input_data, output_data, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                session["id"],
                step_order,
                agent_name,
                json.dumps(input_data or {}),
                json.dumps(output_data or {}),
                status,
                datetime.utcnow(),
                fetch_one=True
            )
            
            logger.debug(
                "Orchestration step added",
                session_id=session_id,
                step_order=step_order,
                agent_name=agent_name,
                step_uuid=step_uuid["id"]
            )
            
            return str(step_uuid["id"])
            
        except Exception as e:
            logger.error(
                "Failed to add orchestration step",
                session_id=session_id,
                step_order=step_order,
                error=str(e)
            )
            raise
    
    async def update_orchestration_step(
        self,
        step_id: str,
        output_data: Dict[str, Any] = None,
        status: str = None,
        error_message: str = None,
        execution_time_ms: int = None
    ) -> None:
        """Update an orchestration step"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            update_fields = []
            update_values = []
            param_count = 1
            
            if output_data is not None:
                update_fields.append(f"output_data = ${param_count}")
                update_values.append(json.dumps(output_data))
                param_count += 1
            
            if status is not None:
                update_fields.append(f"status = ${param_count}")
                update_values.append(status)
                param_count += 1
            
            if error_message is not None:
                update_fields.append(f"error_message = ${param_count}")
                update_values.append(error_message)
                param_count += 1
            
            if execution_time_ms is not None:
                update_fields.append(f"execution_time_ms = ${param_count}")
                update_values.append(execution_time_ms)
                param_count += 1
            
            update_fields.append(f"completed_at = ${param_count}")
            update_values.append(datetime.utcnow())
            param_count += 1
            
            update_values.append(step_id)
            
            query = f"""
                UPDATE orchestration.orchestration_steps
                SET {', '.join(update_fields)}
                WHERE id = ${param_count}
            """
            
            await self.db_manager.execute_query(query, *update_values)
            
            logger.debug(
                "Orchestration step updated",
                step_id=step_id,
                status=status
            )
            
        except Exception as e:
            logger.error(
                "Failed to update orchestration step",
                step_id=step_id,
                error=str(e)
            )
            raise
    
    async def get_orchestration_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get orchestration session details"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            session = await self.db_manager.execute_query(
                """
                SELECT id, session_id, pattern, status, context, created_at, updated_at, completed_at
                FROM orchestration.orchestration_sessions
                WHERE session_id = $1
                """,
                session_id,
                fetch_one=True
            )
            
            if session:
                session["context"] = json.loads(session["context"]) if session["context"] else {}
            
            return dict(session) if session else None
            
        except Exception as e:
            logger.error(
                "Failed to get orchestration session",
                session_id=session_id,
                error=str(e)
            )
            raise
    
    async def get_orchestration_steps(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all steps for an orchestration session"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            steps = await self.db_manager.execute_query(
                """
                SELECT id, step_order, agent_name, input_data, output_data, status, 
                       error_message, execution_time_ms, created_at, completed_at
                FROM orchestration.orchestration_steps
                WHERE session_id = (SELECT id FROM orchestration.orchestration_sessions WHERE session_id = $1)
                ORDER BY step_order
                """,
                session_id,
                fetch=True
            )
            
            # Parse JSON fields
            for step in steps:
                if step["input_data"]:
                    step["input_data"] = json.loads(step["input_data"])
                if step["output_data"]:
                    step["output_data"] = json.loads(step["output_data"])
            
            return [dict(step) for step in steps]
            
        except Exception as e:
            logger.error(
                "Failed to get orchestration steps",
                session_id=session_id,
                error=str(e)
            )
            raise
    
    async def update_session_context(
        self,
        session_id: str,
        context: Dict[str, Any]
    ) -> None:
        """Update orchestration session context"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            await self.db_manager.execute_query(
                """
                UPDATE orchestration.orchestration_sessions
                SET context = $1, updated_at = $2
                WHERE session_id = $3
                """,
                json.dumps(context),
                datetime.utcnow(),
                session_id
            )
            
            logger.debug(
                "Orchestration session context updated",
                session_id=session_id
            )
            
        except Exception as e:
            logger.error(
                "Failed to update session context",
                session_id=session_id,
                error=str(e)
            )
            raise
    
    async def complete_orchestration_session(
        self,
        session_id: str,
        status: str = "completed"
    ) -> None:
        """Mark orchestration session as completed"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            await self.db_manager.execute_query(
                """
                UPDATE orchestration.orchestration_sessions
                SET status = $1, completed_at = $2, updated_at = $2
                WHERE session_id = $3
                """,
                status,
                datetime.utcnow(),
                session_id
            )
            
            logger.info(
                "Orchestration session completed",
                session_id=session_id,
                status=status
            )
            
        except Exception as e:
            logger.error(
                "Failed to complete orchestration session",
                session_id=session_id,
                error=str(e)
            )
            raise
    
    async def get_orchestration_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get orchestration metrics"""
        if not self._initialized:
            raise RuntimeError("Database integration not initialized")
        
        try:
            # Default to last 24 hours if no dates provided
            if not start_date:
                start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            if not end_date:
                end_date = datetime.utcnow()
            
            # Get session metrics
            session_metrics = await self.db_manager.execute_query(
                """
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_sessions,
                    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_execution_time_seconds
                FROM orchestration.orchestration_sessions
                WHERE created_at BETWEEN $1 AND $2
                """,
                start_date,
                end_date,
                fetch_one=True
            )
            
            # Get step metrics
            step_metrics = await self.db_manager.execute_query(
                """
                SELECT 
                    COUNT(*) as total_steps,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_steps,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_steps,
                    AVG(execution_time_ms) as avg_step_execution_time_ms
                FROM orchestration.orchestration_steps
                WHERE created_at BETWEEN $1 AND $2
                """,
                start_date,
                end_date,
                fetch_one=True
            )
            
            # Get pattern distribution
            pattern_distribution = await self.db_manager.execute_query(
                """
                SELECT pattern, COUNT(*) as count
                FROM orchestration.orchestration_sessions
                WHERE created_at BETWEEN $1 AND $2
                GROUP BY pattern
                ORDER BY count DESC
                """,
                start_date,
                end_date,
                fetch=True
            )
            
            return {
                "session_metrics": dict(session_metrics) if session_metrics else {},
                "step_metrics": dict(step_metrics) if step_metrics else {},
                "pattern_distribution": [dict(row) for row in pattern_distribution] if pattern_distribution else [],
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(
                "Failed to get orchestration metrics",
                error=str(e)
            )
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        if not self._initialized or not self.db_manager:
            return {
                "status": "unhealthy",
                "error": "Database integration not initialized"
            }
        
        return await self.db_manager.health_check()
    
    async def close(self) -> None:
        """Close database connections"""
        if self.db_manager:
            await self.db_manager.close()
            self._initialized = False
            logger.info("Orchestration database integration closed")

# Global database integration instance
_orchestration_db_integration: Optional[OrchestrationDatabaseIntegration] = None

def get_orchestration_db_integration() -> Optional[OrchestrationDatabaseIntegration]:
    """Get the global orchestration database integration instance"""
    return _orchestration_db_integration

def set_orchestration_db_integration(integration: OrchestrationDatabaseIntegration) -> None:
    """Set the global orchestration database integration instance"""
    global _orchestration_db_integration
    _orchestration_db_integration = integration
