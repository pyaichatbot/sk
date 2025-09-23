"""
GitLab Agent Service
Based on Microsoft Semantic Kernel agent template approach
"""

import os
import sys
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path
from datetime import datetime

# Add shared modules to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import json

from shared.config.settings import MicroserviceSettings
from shared.infrastructure.database import DatabaseManager
from shared.models import AgentRequest, AgentResponse, AgentCapabilities, HealthResponse
from shared.infrastructure.observability.logging import get_logger

# Import GitLab agent implementation
from gitlab_agent import GitLabAgent

# Initialize settings and logger
settings = MicroserviceSettings()
logger = get_logger(__name__)

# Global agent instance
gitlab_agent: Optional[GitLabAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global gitlab_agent
    
    # Startup
    logger.info("Starting GitLab Agent Service")
    
    try:
        # Initialize database (optional for development)
        try:
            db_manager = DatabaseManager(settings)
            await db_manager.initialize()
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.warning(f"Database connection failed (continuing without database): {e}")
            db_manager = None
        
        # Initialize GitLab agent
        gitlab_agent = GitLabAgent(settings)
        await gitlab_agent.initialize()
        
        logger.info("GitLab Agent Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start GitLab Agent Service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down GitLab Agent Service")
    if gitlab_agent:
        try:
            await gitlab_agent.cleanup()
            logger.info("GitLab agent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up GitLab agent: {e}")


# Create FastAPI app
app = FastAPI(
    title="GitLab Agent Service",
    description="A GitLab agent microservice for project management and issue tracking",
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


@app.get("/health", response_model=HealthResponse, summary="Health check endpoint")
async def health_check():
    """
    Performs a health check on the GitLab Agent service.
    Returns:
        HealthResponse: The health status of the service.
    """
    if gitlab_agent:
        return HealthResponse(
            status="healthy",
            service="gitlab-agent",
            version=settings.service_version,
            uptime=(datetime.utcnow() - gitlab_agent._start_time).total_seconds() if hasattr(gitlab_agent, '_start_time') else 0,
            timestamp=datetime.utcnow(),
            metadata=gitlab_agent.get_health_status()
        )
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/capabilities", response_model=AgentCapabilities, summary="Get agent capabilities")
async def get_capabilities():
    """
    Returns the capabilities of the GitLab Agent.
    Returns:
        AgentCapabilities: The capabilities of the agent.
    """
    if gitlab_agent:
        return gitlab_agent.capabilities
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.post("/invoke", response_model=AgentResponse, summary="Invoke the agent with a request")
async def invoke_agent(request: AgentRequest):
    """
    Invokes the GitLab Agent to process a request.
    Args:
        request (AgentRequest): The request to be processed by the agent.
    Returns:
        AgentResponse: The response from the agent.
    """
    if gitlab_agent:
        try:
            response = await gitlab_agent.invoke(
                request.input, 
                user_id=request.user_id, 
                session_id=request.session_id
            )
            return response
        except Exception as e:
            logger.error(f"Error invoking GitLab Agent: {e}")
            raise HTTPException(status_code=500, detail=f"Error invoking GitLab Agent: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.post("/invoke/stream", summary="Invoke the agent with streaming response")
async def invoke_agent_stream(request: AgentRequest):
    """
    Invokes the GitLab Agent with streaming response.
    Args:
        request (AgentRequest): The request to be processed by the agent.
    Returns:
        StreamingResponse: Stream of agent responses.
    """
    if gitlab_agent:
        try:
            async def generate_stream():
                async for response in gitlab_agent.invoke(
                    request.input,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    stream=True
                ):
                    yield f"data: {json.dumps(response.dict())}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        except Exception as e:
            logger.error(f"Error invoking GitLab Agent with streaming: {e}")
            raise HTTPException(status_code=500, detail=f"Error invoking GitLab Agent: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


# GitLab-specific endpoints
@app.get("/gitlab/user", summary="Get current GitLab user information")
async def get_current_user():
    """
    Get current authenticated GitLab user information.
    Returns:
        dict: Current user information.
    """
    if gitlab_agent:
        try:
            user_info = await gitlab_agent.get_current_user()
            return user_info
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting current user: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}", summary="Get project information")
async def get_project(project_id: str):
    """
    Get GitLab project information by ID or path.
    Args:
        project_id (str): Project ID or path.
    Returns:
        dict: Project information.
    """
    if gitlab_agent:
        try:
            project_info = await gitlab_agent.get_project_info(project_id)
            return project_info
        except Exception as e:
            logger.error(f"Error getting project info: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting project info: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}/issues", summary="Get project issues")
async def get_project_issues(
    project_id: str,
    state: str = "opened",
    labels: Optional[str] = None,
    assignee_id: Optional[int] = None,
    per_page: int = 20
):
    """
    Get project issues with optional filtering.
    Args:
        project_id (str): Project ID or path.
        state (str): Issue state filter (opened/closed/all).
        labels (str): Comma-separated list of labels to filter by.
        assignee_id (int): Assignee ID to filter by.
        per_page (int): Number of issues per page.
    Returns:
        list: List of project issues.
    """
    if gitlab_agent:
        try:
            issues = await gitlab_agent.get_project_issues(
                project_id, state, labels, assignee_id, per_page
            )
            return issues
        except Exception as e:
            logger.error(f"Error getting project issues: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting project issues: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}/merge_requests", summary="Get project merge requests")
async def get_project_merge_requests(
    project_id: str,
    state: str = "opened",
    per_page: int = 20
):
    """
    Get project merge requests with optional filtering.
    Args:
        project_id (str): Project ID or path.
        state (str): Merge request state filter (opened/closed/merged/all).
        per_page (int): Number of merge requests per page.
    Returns:
        list: List of project merge requests.
    """
    if gitlab_agent:
        try:
            merge_requests = await gitlab_agent.get_project_merge_requests(
                project_id, state, per_page
            )
            return merge_requests
        except Exception as e:
            logger.error(f"Error getting project merge requests: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting project merge requests: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}/commits", summary="Get project commits")
async def get_project_commits(
    project_id: str,
    ref_name: str = "main",
    per_page: int = 20
):
    """
    Get project commits for a specific branch or tag.
    Args:
        project_id (str): Project ID or path.
        ref_name (str): Branch or tag name.
        per_page (int): Number of commits per page.
    Returns:
        list: List of project commits.
    """
    if gitlab_agent:
        try:
            commits = await gitlab_agent.get_project_commits(project_id, ref_name, per_page)
            return commits
        except Exception as e:
            logger.error(f"Error getting project commits: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting project commits: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}/branches", summary="Get project branches")
async def get_project_branches(
    project_id: str,
    per_page: int = 20
):
    """
    Get project branches.
    Args:
        project_id (str): Project ID or path.
        per_page (int): Number of branches per page.
    Returns:
        list: List of project branches.
    """
    if gitlab_agent:
        try:
            branches = await gitlab_agent.get_project_branches(project_id, per_page)
            return branches
        except Exception as e:
            logger.error(f"Error getting project branches: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting project branches: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}/tags", summary="Get project tags")
async def get_project_tags(
    project_id: str,
    per_page: int = 20
):
    """
    Get project tags.
    Args:
        project_id (str): Project ID or path.
        per_page (int): Number of tags per page.
    Returns:
        list: List of project tags.
    """
    if gitlab_agent:
        try:
            tags = await gitlab_agent.get_project_tags(project_id, per_page)
            return tags
        except Exception as e:
            logger.error(f"Error getting project tags: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting project tags: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}/pipelines", summary="Get project pipelines")
async def get_project_pipelines(
    project_id: str,
    ref: Optional[str] = None,
    status: Optional[str] = None,
    per_page: int = 20
):
    """
    Get project pipelines with optional filtering.
    Args:
        project_id (str): Project ID or path.
        ref (str): Branch or tag name to filter by.
        status (str): Pipeline status to filter by.
        per_page (int): Number of pipelines per page.
    Returns:
        list: List of project pipelines.
    """
    if gitlab_agent:
        try:
            pipelines = await gitlab_agent.get_project_pipelines(project_id, ref, status, per_page)
            return pipelines
        except Exception as e:
            logger.error(f"Error getting project pipelines: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting project pipelines: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


@app.get("/gitlab/projects/{project_id}/pipelines/{pipeline_id}", summary="Get specific pipeline")
async def get_pipeline(
    project_id: str,
    pipeline_id: int
):
    """
    Get specific pipeline details.
    Args:
        project_id (str): Project ID or path.
        pipeline_id (int): Pipeline ID.
    Returns:
        dict: Pipeline details.
    """
    if gitlab_agent:
        try:
            pipeline = await gitlab_agent.get_pipeline(project_id, pipeline_id)
            return pipeline
        except Exception as e:
            logger.error(f"Error getting pipeline: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting pipeline: {e}")
    raise HTTPException(status_code=503, detail="GitLab Agent not initialized")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)
