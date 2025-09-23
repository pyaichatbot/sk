"""
Enterprise Orchestration Service - Production Ready
==================================================

This service implements Microsoft Semantic Kernel Agent Orchestration framework
for coordinating complex multi-agent workflows with enterprise-grade features.

Features:
- Microsoft SK Agent Orchestration patterns (Sequential, Concurrent, Handoff, Group Chat, Magentic)
- Redis-based session management and context persistence
- Real-time streaming via WebSocket
- Enterprise-grade error handling and observability
- Production-ready health checks and metrics
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from semantic_kernel.agents.runtime.in_process.in_process_runtime import InProcessRuntime
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread

# Shared infrastructure
from shared.config.settings import MicroserviceSettings
from shared.infrastructure.database import DatabaseManager
from shared.models import (
    AgentRequest, AgentResponse, HealthResponse, 
    OrchestrationRequest, OrchestrationResponse, OrchestrationPattern,
    OrchestrationStatus, OrchestrationStep, OrchestrationMetrics
)
import logging

# Import orchestration implementation
from orchestration_engine import EnterpriseOrchestrationEngine
from session_manager import SessionManager
from agent_factory import AgentFactory

# Import intermediate messaging
from intermediate_messaging_endpoints import (
    websocket_agent_calls, get_event_history, get_messaging_metrics,
    get_messaging_health, get_active_connections, emit_agent_call_event
)
from shared.infrastructure.intermediate_messaging import (
    IntermediateMessagingService, set_intermediate_messaging_service
)

logger = logging.getLogger(__name__)

# Global instances
orchestration_engine: Optional[EnterpriseOrchestrationEngine] = None
session_manager: Optional[SessionManager] = None
agent_factory: Optional[AgentFactory] = None
intermediate_messaging_service: Optional[IntermediateMessagingService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global orchestration_engine, session_manager, agent_factory, intermediate_messaging_service
    
    try:
        logger.info("Initializing Orchestration Service")
        
        # Initialize shared infrastructure
        settings = MicroserviceSettings()
        
        # Initialize database (optional for development)
        try:
            db_manager = DatabaseManager(settings)
            await db_manager.initialize()
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.warning(f"Database connection failed (continuing without database): {e}")
            db_manager = None
        
        # Initialize components
        session_manager = SessionManager(settings)
        agent_factory = AgentFactory(settings)
        
        # Initialize intermediate messaging service (MANDATORY)
        intermediate_messaging_service = IntermediateMessagingService(settings)
        await intermediate_messaging_service.initialize()
        set_intermediate_messaging_service(intermediate_messaging_service)
        
        orchestration_engine = EnterpriseOrchestrationEngine(
            session_manager=session_manager,
            agent_factory=agent_factory,
            settings=settings
        )
        
        # Initialize orchestration engine
        await orchestration_engine.initialize()
        
        logger.info("Orchestration Service initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize Orchestration Service: {e}")
        raise
    finally:
        logger.info("Shutting down Orchestration Service")
        
        # Cleanup orchestration engine
        if orchestration_engine:
            try:
                await asyncio.wait_for(orchestration_engine.cleanup(), timeout=10.0)
                logger.info("Orchestration engine cleaned up successfully")
            except asyncio.TimeoutError:
                logger.warning("Orchestration engine cleanup timed out")
            except Exception as e:
                logger.error(f"Error cleaning up orchestration engine: {e}")
        
        # Cleanup intermediate messaging service
        if intermediate_messaging_service:
            try:
                await asyncio.wait_for(intermediate_messaging_service.cleanup(), timeout=10.0)
                logger.info("Intermediate messaging service cleaned up successfully")
            except asyncio.TimeoutError:
                logger.warning("Intermediate messaging service cleanup timed out")
            except Exception as e:
                logger.error(f"Error cleaning up intermediate messaging service: {e}")
        
        # Cleanup session manager
        if session_manager:
            try:
                await asyncio.wait_for(session_manager.cleanup(), timeout=5.0)
                logger.info("Session manager cleaned up successfully")
            except asyncio.TimeoutError:
                logger.warning("Session manager cleanup timed out")
            except Exception as e:
                logger.error(f"Error cleaning up session manager: {e}")
        
        logger.info("Orchestration Service shutdown completed")

# FastAPI application
app = FastAPI(
    title="Enterprise Orchestration Service",
    description="Microsoft Semantic Kernel Agent Orchestration for Enterprise Workflows",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency injection
async def get_orchestration_engine() -> EnterpriseOrchestrationEngine:
    """Get orchestration engine instance"""
    if not orchestration_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return orchestration_engine

async def get_session_manager() -> SessionManager:
    """Get session manager instance"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return session_manager

# Pydantic models
class OrchestrationRequestModel(BaseModel):
    """Request model for orchestration"""
    message: str = Field(..., min_length=1, max_length=10000, description="Task message")
    pattern: OrchestrationPattern = Field(..., description="Orchestration pattern to use")
    agents: List[str] = Field(default_factory=list, description="Specific agents to use")
    session_id: Optional[str] = Field(default=None, description="Session ID for context")
    user_id: str = Field(..., description="User identifier")
    streaming: bool = Field(default=False, description="Enable streaming response")
    max_iterations: int = Field(default=10, ge=1, le=50, description="Maximum iterations")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")

class SessionInfo(BaseModel):
    """Session information model"""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    active_agents: List[str]
    conversation_count: int

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        if not orchestration_engine:
            return HealthResponse(
                status="unhealthy",
                service="orchestration-service",
                version="1.0.0",
                uptime=0,
                checks={"orchestration_engine": {"status": "not_initialized"}}
            )
        
        health_status = await orchestration_engine.get_health_status()
        return HealthResponse(
            status=health_status.get("status", "healthy"),
            service="orchestration-service",
            version="1.0.0",
            uptime=health_status.get("uptime", 0),
            checks=health_status.get("checks", {}),
            dependencies=health_status.get("dependencies", {})
        )
    except Exception as e:
        logger.error("Health check failed", error=e)
        return HealthResponse(
            status="unhealthy",
            service="orchestration-service",
            version="1.0.0",
            uptime=0,
            checks={"error": {"status": str(e)}}
        )

# Orchestration endpoints
@app.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(
    request: OrchestrationRequestModel,
    engine: EnterpriseOrchestrationEngine = Depends(get_orchestration_engine)
):
    """Execute orchestration with specified pattern"""
    try:
        logger.info(
            "Processing orchestration request",
            pattern=request.pattern,
            user_id=request.user_id,
            session_id=request.session_id,
            streaming=request.streaming
        )
        
        # Convert to internal request model
        orchestration_request = OrchestrationRequest(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id or str(uuid.uuid4()),
            pattern=request.pattern,
            agents_required=request.agents,
            context=request.context,
            streaming=request.streaming,
            max_iterations=request.max_iterations
        )
        
        # Execute orchestration
        result = await engine.orchestrate(orchestration_request)
        
        return result
        
    except Exception as e:
        logger.error("Orchestration failed", error=e, user_id=request.user_id)
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")

@app.post("/orchestrate/stream")
async def orchestrate_stream(
    request: OrchestrationRequestModel,
    engine: EnterpriseOrchestrationEngine = Depends(get_orchestration_engine)
):
    """Execute orchestration with streaming response"""
    try:
        logger.info(
            "Processing streaming orchestration request",
            pattern=request.pattern,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        # Convert to internal request model
        orchestration_request = OrchestrationRequest(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id or str(uuid.uuid4()),
            pattern=request.pattern,
            agents_required=request.agents,
            context=request.context,
            streaming=True,
            max_iterations=request.max_iterations
        )
        
        async def generate_stream():
            try:
                async for step in engine.orchestrate_stream(orchestration_request):
                    yield f"data: {json.dumps(step.dict())}\n\n"
            except Exception as e:
                error_response = {
                    "step_id": f"error-{datetime.utcnow().timestamp()}",
                    "agent_name": "orchestrator",
                    "status": OrchestrationStatus.ERROR.value,
                    "success": False,
                    "error": str(e),
                    "error_code": type(e).__name__
                }
                yield f"data: {json.dumps(error_response)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except Exception as e:
        logger.error("Streaming orchestration failed", error=e, user_id=request.user_id)
        raise HTTPException(status_code=500, detail=f"Streaming orchestration failed: {str(e)}")

# WebSocket endpoint for real-time communication
@app.websocket("/orchestrate/ws/{session_id}")
async def orchestrate_websocket(
    websocket: WebSocket,
    session_id: str,
    engine: EnterpriseOrchestrationEngine = Depends(get_orchestration_engine)
):
    """WebSocket endpoint for real-time orchestration"""
    await websocket.accept()
    
    try:
        logger.info("WebSocket connection established", session_id=session_id)
        
        while True:
            # Receive request from client
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
            # Create orchestration request
            orchestration_request = OrchestrationRequest(
                message=request_data["message"],
                user_id=request_data["user_id"],
                session_id=session_id,
                pattern=OrchestrationPattern(request_data["pattern"]),
                agents_required=request_data.get("agents", []),
                context=request_data.get("context", {}),
                streaming=True,
                max_iterations=request_data.get("max_iterations", 10)
            )
            
            # Stream orchestration steps
            async for step in engine.orchestrate_stream(orchestration_request):
                await websocket.send_text(json.dumps(step.dict()))
                
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed", session_id=session_id)
    except Exception as e:
        logger.error("WebSocket orchestration failed", error=e, session_id=session_id)
        await websocket.close(code=1011, reason=str(e))

# ============================================================================
# INTERMEDIATE MESSAGING ENDPOINTS (MANDATORY)
# ============================================================================

# WebSocket endpoint for real-time agent call events
@app.websocket("/ws/agent-calls/{session_id}")
async def websocket_agent_calls_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: str = Query(..., description="User identifier"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    agent_names: Optional[str] = Query(None, description="Comma-separated agent names to filter"),
    function_names: Optional[str] = Query(None, description="Comma-separated function names to filter")
):
    """
    WebSocket endpoint for real-time agent call events (MANDATORY)
    
    This endpoint provides real-time streaming of agent call events to consumers/UI,
    enabling visibility into the orchestration process as it happens.
    """
    await websocket_agent_calls(
        websocket=websocket,
        session_id=session_id,
        user_id=user_id,
        event_types=event_types,
        agent_names=agent_names,
        function_names=function_names
    )

# HTTP endpoints for intermediate messaging
@app.post("/events/history")
async def get_event_history_endpoint(
    request: dict,
    messaging_service: IntermediateMessagingService = Depends(lambda: intermediate_messaging_service)
):
    """Get historical agent call events for a session"""
    from intermediate_messaging_endpoints import EventHistoryRequest
    history_request = EventHistoryRequest(**request)
    return await get_event_history(history_request, messaging_service)

@app.get("/events/metrics")
async def get_messaging_metrics_endpoint(
    messaging_service: IntermediateMessagingService = Depends(lambda: intermediate_messaging_service)
):
    """Get metrics for the intermediate messaging service"""
    return await get_messaging_metrics(messaging_service)

@app.get("/events/health")
async def get_messaging_health_endpoint(
    messaging_service: IntermediateMessagingService = Depends(lambda: intermediate_messaging_service)
):
    """Get health status of the intermediate messaging service"""
    return await get_messaging_health(messaging_service)

@app.get("/events/connections")
async def get_active_connections_endpoint():
    """Get information about active WebSocket connections"""
    return await get_active_connections()

# Session management endpoints
@app.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    session_mgr: SessionManager = Depends(get_session_manager)
):
    """Get session information"""
    try:
        session_info = await session_mgr.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_info
    except Exception as e:
        logger.error("Failed to get session", error=e, session_id=session_id)
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")

@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    session_mgr: SessionManager = Depends(get_session_manager)
):
    """Delete session and cleanup resources"""
    try:
        await session_mgr.delete_session(session_id)
        return {"message": "Session deleted successfully"}
    except Exception as e:
        logger.error("Failed to delete session", error=e, session_id=session_id)
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

@app.get("/sessions")
async def list_sessions(
    user_id: Optional[str] = None,
    limit: int = 20,
    session_mgr: SessionManager = Depends(get_session_manager)
):
    """List active sessions"""
    try:
        sessions = await session_mgr.list_sessions(user_id=user_id, limit=limit)
        return {"sessions": sessions}
    except Exception as e:
        logger.error("Failed to list sessions", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

# Pattern and agent information endpoints
@app.get("/patterns")
async def get_available_patterns():
    """Get available orchestration patterns"""
    return {
        "patterns": [
            {
                "name": "sequential",
                "description": "Execute agents one after another in sequence",
                "use_case": "Step-by-step workflows, pipelines, multi-stage processing"
            },
            {
                "name": "concurrent", 
                "description": "Execute multiple agents simultaneously",
                "use_case": "Parallel analysis, independent subtasks, ensemble decision making"
            },
            {
                "name": "handoff",
                "description": "Dynamically pass control between agents based on context",
                "use_case": "Dynamic workflows, escalation, fallback, expert handoff scenarios"
            },
            {
                "name": "group_chat",
                "description": "All agents participate in collaborative discussion",
                "use_case": "Brainstorming, collaborative problem solving, consensus building"
            },
            {
                "name": "magentic",
                "description": "Group chat-like orchestration inspired by MagenticOne",
                "use_case": "Complex, generalist multi-agent collaboration"
            }
        ]
    }

@app.get("/agents")
async def get_available_agents(
    engine: EnterpriseOrchestrationEngine = Depends(get_orchestration_engine)
):
    """Get available agents and their capabilities"""
    try:
        agents_info = await engine.get_agents_info()
        return {"agents": agents_info}
    except Exception as e:
        logger.error("Failed to get agents info", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to get agents info: {str(e)}")

# Metrics and monitoring endpoints
@app.get("/metrics")
async def get_metrics(
    engine: EnterpriseOrchestrationEngine = Depends(get_orchestration_engine)
):
    """Get orchestration metrics"""
    try:
        metrics = await engine.get_metrics()
        return metrics
    except Exception as e:
        logger.error("Failed to get metrics", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@app.get("/history")
async def get_orchestration_history(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 10,
    engine: EnterpriseOrchestrationEngine = Depends(get_orchestration_engine)
):
    """Get orchestration history"""
    try:
        history = await engine.get_history(
            session_id=session_id,
            user_id=user_id,
            limit=limit
        )
        return {"history": history}
    except Exception as e:
        logger.error("Failed to get history", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
