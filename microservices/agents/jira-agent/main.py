# ============================================================================
# microservices/agents/jira-agent/main.py
# ============================================================================
"""
JIRA Agent Service - Project management and issue tracking microservice
Handles JIRA integration, issue management, and project tracking
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

# Import JIRA agent implementation
from jira_agent import JiraAgent

# Initialize settings and logger
settings = MicroserviceSettings()
logger = get_logger(__name__)

# Global agent instance
jira_agent: Optional[JiraAgent] = None
service_discovery_integration: Optional[ServiceDiscoveryIntegration] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global jira_agent, service_discovery_integration
    
    # Startup
    logger.info("Starting JIRA Agent Service")
    
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
                tags=["jira-agent", "agent", "jira", "project-management"],
                metadata={
                    "version": settings.service_version,
                    "environment": settings.environment.value,
                    "capabilities": ["issue_management", "project_tracking", "workflow_management", "jql_queries"]
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
        
        # Initialize JIRA agent
        jira_agent = JiraAgent(settings)
        await jira_agent.initialize()
        
        logger.info("JIRA Agent Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start JIRA Agent Service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down JIRA Agent Service")
    
    if jira_agent:
        try:
            await jira_agent.cleanup()
            logger.info("JIRA agent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up JIRA agent: {e}")
    
    if service_discovery_integration:
        try:
            await service_discovery_integration.shutdown()
            logger.info("Service discovery integration cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up service discovery integration: {e}")

# Create FastAPI app
app = FastAPI(
    title="JIRA Agent Service",
    description="Project management and issue tracking microservice with JIRA integration",
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
# All JIRA-specific request models removed - using unified AgentRequest

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Get service discovery health if available
    discovery_health = {}
    if service_discovery_integration and service_discovery_integration.discovery_manager:
        try:
            discovery_health = await service_discovery_integration.discovery_manager.health_check()
        except Exception as e:
            logger.warning(f"Failed to get service discovery health: {e}")
    
    health_status = jira_agent.get_health_status()
    
    return HealthResponse(
        status=health_status["status"],
        service="jira-agent",
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
    Get service discovery information for the JIRA Agent.
    Returns:
        dict: Service discovery information.
    """
    if service_discovery_integration:
        return {
            "service_name": settings.service_name,
            "service_port": settings.service_port,
            "version": settings.service_version,
            "environment": settings.environment.value,
            "tags": ["jira-agent", "agent", "jira", "project-management"],
            "metadata": {
                "capabilities": ["issue_management", "project_tracking", "workflow_management", "jql_queries"]
            },
            "is_initialized": service_discovery_integration.is_initialized
        }
    raise HTTPException(status_code=503, detail="Service discovery not initialized")


@app.get("/discovery-metrics", summary="Get service discovery metrics")
async def get_discovery_metrics():
    """
    Get service discovery metrics for the JIRA Agent.
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

# General JIRA operation endpoint
@app.post("/jira/execute", response_model=AgentResponse)
async def execute_jira_operation(request: AgentRequest):
    """Execute a general JIRA operation"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Executing JIRA operation", operation=request.operation)
        
        # Create operation prompt
        operation_prompt = f"""
        Please perform the following JIRA operation:
        
        Operation: {request.operation}
        Parameters: {request.parameters}
        
        Ensure proper authorization and maintain audit trail.
        """
        
        response = await jira_agent.invoke(
            message=operation_prompt,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        return response
        
    except Exception as e:
        logger.error("JIRA operation failed", error=e)
        raise HTTPException(status_code=500, detail=f"JIRA operation failed: {str(e)}")

# Create issue endpoint
@app.post("/issues", response_model=AgentResponse)
async def create_issue(request: AgentRequest):
    """Create a new JIRA issue"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Extract parameters from unified request
        project_key = request.parameters.get("project_key")
        issue_type = request.parameters.get("issue_type")
        summary = request.parameters.get("summary")
        description = request.parameters.get("description")
        assignee = request.parameters.get("assignee")
        priority = request.parameters.get("priority")
        labels = request.parameters.get("labels", [])
        
        logger.info("Creating JIRA issue", project_key=project_key, issue_type=issue_type)
        
        # Create issue creation prompt
        create_prompt = f"""
        Please create a new JIRA issue with the following details:
        
        Project Key: {project_key}
        Issue Type: {issue_type}
        Summary: {summary}
        Description: {description or 'No description provided'}
        Assignee: {assignee or 'Unassigned'}
        Priority: {priority or 'Medium'}
        Labels: {', '.join(labels) if labels else 'None'}
        
        Create the issue and return the issue key and details.
        """
        
        response = await jira_agent.invoke(
            message=create_prompt,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        return response
        
    except Exception as e:
        logger.error("Issue creation failed", error=e)
        raise HTTPException(status_code=500, detail=f"Issue creation failed: {str(e)}")

# Update issue endpoint
@app.put("/issues/{issue_key}", response_model=AgentResponse)
async def update_issue(issue_key: str, request: AgentRequest):
    """Update an existing JIRA issue"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Extract parameters from unified request
        fields = request.parameters.get("fields", {})
        
        logger.info("Updating JIRA issue", issue_key=issue_key)
        
        # Create update prompt
        update_prompt = f"""
        Please update JIRA issue {issue_key} with the following changes:
        
        Fields to update: {fields}
        
        Ensure proper authorization and maintain audit trail.
        Return the updated issue details.
        """
        
        response = await jira_agent.invoke(
            message=update_prompt,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        return response
        
    except Exception as e:
        logger.error("Issue update failed", error=e, issue_key=issue_key)
        raise HTTPException(status_code=500, detail=f"Issue update failed: {str(e)}")

# Search issues endpoint
@app.post("/issues/search", response_model=AgentResponse)
async def search_issues(request: AgentRequest):
    """Search for JIRA issues"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Extract parameters from unified request
        jql = request.parameters.get("jql")
        project_key = request.parameters.get("project_key")
        assignee = request.parameters.get("assignee")
        status = request.parameters.get("status")
        max_results = request.parameters.get("max_results", 50)
        
        logger.info("Searching JIRA issues", jql=jql, project_key=project_key)
        
        # Create search prompt
        search_prompt = f"""
        Please search for JIRA issues with the following criteria:
        
        JQL Query: {jql or 'Not specified'}
        Project Key: {project_key or 'All projects'}
        Assignee: {assignee or 'All assignees'}
        Status: {status or 'All statuses'}
        Max Results: {max_results}
        
        Return the search results with issue details.
        """
        
        response = await jira_agent.invoke(
            message=search_prompt,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        return response
        
    except Exception as e:
        logger.error("Issue search failed", error=e)
        raise HTTPException(status_code=500, detail=f"Issue search failed: {str(e)}")

# Get issue details endpoint
@app.get("/issues/{issue_key}")
async def get_issue(issue_key: str, user_id: Optional[str] = Query(None)):
    """Get details of a specific JIRA issue"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Getting JIRA issue details", issue_key=issue_key)
        
        # Create get issue prompt
        get_prompt = f"""
        Please retrieve the details for JIRA issue {issue_key}.
        
        Return comprehensive information including:
        - Issue summary and description
        - Current status and assignee
        - Priority and labels
        - Comments and attachments
        - Work log and time tracking
        - Related issues and links
        """
        
        response = await jira_agent.invoke(
            message=get_prompt,
            user_id=user_id
        )
        
        return {
            "issue_key": issue_key,
            "details": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error("Failed to get issue details", error=e, issue_key=issue_key)
        raise HTTPException(status_code=500, detail=f"Failed to get issue details: {str(e)}")

# Transition issue endpoint
@app.post("/issues/{issue_key}/transition")
async def transition_issue(
    issue_key: str,
    transition: str = Body(..., embed=True),
    user_id: Optional[str] = Query(None)
):
    """Transition a JIRA issue to a different status"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Transitioning JIRA issue", issue_key=issue_key, transition=transition)
        
        # Create transition prompt
        transition_prompt = f"""
        Please transition JIRA issue {issue_key} to status: {transition}
        
        Ensure proper authorization and maintain audit trail.
        Return the updated issue status and any relevant information.
        """
        
        response = await jira_agent.invoke(
            message=transition_prompt,
            user_id=user_id
        )
        
        return {
            "issue_key": issue_key,
            "transition": transition,
            "result": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error("Issue transition failed", error=e, issue_key=issue_key)
        raise HTTPException(status_code=500, detail=f"Issue transition failed: {str(e)}")

# Add comment endpoint
@app.post("/issues/{issue_key}/comments")
async def add_comment(
    issue_key: str,
    comment: str = Body(..., embed=True),
    user_id: Optional[str] = Query(None)
):
    """Add a comment to a JIRA issue"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Adding comment to JIRA issue", issue_key=issue_key)
        
        # Create add comment prompt
        comment_prompt = f"""
        Please add the following comment to JIRA issue {issue_key}:
        
        Comment: {comment}
        
        Ensure proper authorization and maintain audit trail.
        Return confirmation of the comment addition.
        """
        
        response = await jira_agent.invoke(
            message=comment_prompt,
            user_id=user_id
        )
        
        return {
            "issue_key": issue_key,
            "comment": comment,
            "result": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error("Failed to add comment", error=e, issue_key=issue_key)
        raise HTTPException(status_code=500, detail=f"Failed to add comment: {str(e)}")

# Get projects endpoint
@app.get("/projects")
async def get_projects(user_id: Optional[str] = Query(None)):
    """Get list of JIRA projects"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Getting JIRA projects")
        
        # Create get projects prompt
        projects_prompt = """
        Please retrieve a list of all accessible JIRA projects.
        
        For each project, return:
        - Project key and name
        - Project description
        - Project lead
        - Issue types available
        - Project status
        """
        
        response = await jira_agent.invoke(
            message=projects_prompt,
            user_id=user_id
        )
        
        return {
            "projects": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error("Failed to get projects", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")

# Get agent metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Get agent performance metrics"""
    if not jira_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        metrics = jira_agent.get_metrics()
        return metrics
        
    except Exception as e:
        logger.error("Failed to get metrics", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
