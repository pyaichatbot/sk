# ============================================================================
# microservices/agents/template-agent/main.py
# ============================================================================
"""
Template Agent Service - Template for creating new agents
Copy this template and customize for your specific agent needs
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add shared modules to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from shared.config.settings import MicroserviceSettings
from shared.infrastructure.database import DatabaseManager
from shared.models import AgentRequest, AgentResponse, AgentCapabilities, HealthResponse
from shared.infrastructure.observability.logging import get_logger
from shared.infrastructure.discovery_integration import (
    ServiceDiscoveryIntegration,
    create_service_discovery_config,
    set_global_integration
)

# Import template agent implementation
from template_agent import TemplateAgent

# Initialize settings and logger
settings = MicroserviceSettings()
logger = get_logger(__name__)

# Global agent instance
template_agent: Optional[TemplateAgent] = None
service_discovery_integration: Optional[ServiceDiscoveryIntegration] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global template_agent, service_discovery_integration
    
    # Startup
    logger.info("Starting Template Agent Service")
    
    try:
        # Initialize database (optional for development)
        try:
            db_manager = DatabaseManager(settings)
            await db_manager.initialize()
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.warning(f"Database connection failed (continuing without database): {e}")
            db_manager = None
        
        # Initialize service discovery integration
        try:
            service_discovery_config = create_service_discovery_config(
                service_name=settings.service_name,
                service_port=settings.service_port,
                health_endpoint="/health",
                tags=["template-agent", "agent", "template", "customizable"],
                metadata={
                    "version": settings.service_version,
                    "environment": settings.environment.value,
                    "capabilities": ["template_processing", "custom_operations", "data_processing"]
                }
            )
            
            service_discovery_integration = ServiceDiscoveryIntegration(settings, service_discovery_config)
            await service_discovery_integration.initialize()
            
            # Set global integration for easy access
            set_global_integration(service_discovery_integration)
            
            logger.info("Service discovery integration initialized successfully")
        except Exception as e:
            logger.warning(f"Service discovery integration failed (continuing without service discovery): {e}")
            service_discovery_integration = None
        
        # Initialize Template agent
        template_agent = TemplateAgent(settings)
        await template_agent.initialize()
        
        logger.info("Template Agent Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Template Agent Service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Template Agent Service")
    
    if template_agent:
        try:
            await template_agent.cleanup()
            logger.info("Template agent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up template agent: {e}")
    
    if service_discovery_integration:
        try:
            await service_discovery_integration.shutdown()
            logger.info("Service discovery integration cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up service discovery integration: {e}")

# Create FastAPI app
app = FastAPI(
    title="Template Agent Service",
    description="Template microservice for creating new agents - customize as needed",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models - Using Enterprise Standard Models
# All template-specific request models removed - using unified AgentRequest

class TemplateResponse(BaseModel):
    """Response model for template operations"""
    result: str = Field(..., description="Template operation result")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

# Health Check Endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if not template_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Get service discovery health if available
    discovery_health = {}
    if service_discovery_integration and service_discovery_integration.discovery_manager:
        try:
            discovery_health = await service_discovery_integration.discovery_manager.health_check()
        except Exception as e:
            logger.warning(f"Failed to get service discovery health: {e}")
    
    health_status = template_agent.get_health_status()
    
    return HealthResponse(
        status=health_status["status"],
        service="template-agent",
        version="1.0.0",
        uptime=health_status.get("uptime", 0),
        metadata={
            **health_status,
            "service_discovery": discovery_health
        }
    )


@app.get("/service-info", summary="Get service discovery information")
async def get_service_info():
    """
    Get service discovery information for the Template Agent.
    Returns:
        dict: Service discovery information.
    """
    if service_discovery_integration:
        return {
            "service_name": settings.service_name,
            "service_port": settings.service_port,
            "version": settings.service_version,
            "environment": settings.environment.value,
            "tags": ["template-agent", "agent", "template", "customizable"],
            "metadata": {
                "capabilities": ["template_processing", "custom_operations", "data_processing"]
            },
            "is_initialized": service_discovery_integration.is_initialized
        }
    raise HTTPException(status_code=503, detail="Service discovery not initialized")


@app.get("/discovery-metrics", summary="Get service discovery metrics")
async def get_discovery_metrics():
    """
    Get service discovery metrics for the Template Agent.
    Returns:
        dict: Service discovery metrics.
    """
    if service_discovery_integration and service_discovery_integration.discovery_manager:
        try:
            return await service_discovery_integration.discovery_manager.get_metrics()
        except Exception as e:
            logger.error(f"Failed to get service discovery metrics: {e}")
            return {"error": str(e)}
    raise HTTPException(status_code=503, detail="Service discovery not initialized")

# Agent Capabilities Endpoint
@app.get("/capabilities")
async def get_capabilities():
    """Get agent capabilities"""
    if template_agent:
        return template_agent.capabilities
    else:
        raise HTTPException(status_code=503, detail="Agent not initialized")

# Main Agent Invoke Endpoint
@app.post("/invoke", response_model=AgentResponse)
async def invoke_agent(request: AgentRequest):
    """Invoke the template agent"""
    if not template_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Process the request
        response = await template_agent.invoke(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            **request.parameters
        )
        return response
    except Exception as e:
        logger.error(f"Template agent invocation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Streaming Endpoint
@app.post("/invoke/stream")
async def invoke_agent_stream(request: AgentRequest):
    """Invoke the template agent with streaming response"""
    if not template_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Stream the response
        async def generate():
            async for response in template_agent.invoke_stream(
                message=request.message,
                user_id=request.user_id,
                session_id=request.session_id,
                **request.parameters
            ):
                yield f"data: {response.model_dump_json()}\n\n"
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    except Exception as e:
        logger.error(f"Template agent streaming failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Template-specific endpoints (customize as needed)
@app.post("/template/process", response_model=TemplateResponse)
async def process_template(
    data: str = Body(..., description="Data to process"),
    user_id: Optional[str] = Query(None, description="User ID"),
    **kwargs
):
    """Template-specific processing endpoint"""
    if not template_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Customize this method based on your agent's needs
        result = await template_agent.process_data(data, user_id=user_id, **kwargs)
        return TemplateResponse(
            result=result,
            metadata={"processed_at": "2024-01-01T00:00:00Z", "user_id": user_id}
        )
    except Exception as e:
        logger.error(f"Template processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Metrics Endpoint
@app.get("/metrics")
async def get_metrics():
    """Get agent metrics"""
    if template_agent:
        return template_agent.get_metrics()
    else:
        return {"error": "Agent not initialized"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,  # Change this port for your specific agent
        reload=True
    )
