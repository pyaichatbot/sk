# ============================================================================
# microservices/api-gateway/routers/agents.py
# ============================================================================
"""
Agents router for API Gateway service.
Handles agent management requests and routes them to appropriate services.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.models.agent import AgentRequest, AgentResponse, AgentStatus, AgentMetrics
from shared.models.common import PaginationParams, PaginatedResponse
from shared.config.settings import MicroserviceSettings
from services.routing_service import RoutingService
from services.load_balancer import LoadBalancer

router = APIRouter()
security = HTTPBearer()

async def get_routing_service() -> RoutingService:
    """Get routing service instance"""
    from main import routing_service
    return routing_service

async def get_load_balancer() -> LoadBalancer:
    """Get load balancer instance"""
    from main import load_balancer
    return load_balancer

async def get_settings() -> MicroserviceSettings:
    """Get service settings instance"""
    from main import settings
    return settings

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current user from JWT token"""
    # TODO: Implement JWT token validation
    return {
        "user_id": "user_123",
        "username": "test_user",
        "roles": ["admin"]
    }

@router.get("/agents", response_model=PaginatedResponse)
async def list_agents(
    pagination: PaginationParams = Depends(),
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    List all available agents.
    
    Args:
        pagination: Pagination parameters
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        PaginatedResponse: List of agents
    """
    try:
        # Route request to orchestration service
        orchestration_service_url = await routing_service.get_service_url("orchestration")
        if not orchestration_service_url:
            raise HTTPException(
                status_code=503,
                detail="Orchestration service not available"
            )
        
        # Select orchestration service instance
        selected_url = await load_balancer.select_instance("orchestration", orchestration_service_url)
        
        # Make request to orchestration service
        response = await routing_service.forward_request(
            method="GET",
            url=f"{selected_url}/agents",
            params={
                "page": pagination.page,
                "size": pagination.size,
                "sort_by": pagination.sort_by,
                "sort_order": pagination.sort_order
            },
            headers={
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Orchestration service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/agents/{agent_name}", response_model=Dict[str, Any])
async def get_agent(
    agent_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Get agent details.
    
    Args:
        agent_name: Name of the agent
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Agent details
    """
    try:
        # Route request to orchestration service
        orchestration_service_url = await routing_service.get_service_url("orchestration")
        if not orchestration_service_url:
            raise HTTPException(
                status_code=503,
                detail="Orchestration service not available"
            )
        
        # Select orchestration service instance
        selected_url = await load_balancer.select_instance("orchestration", orchestration_service_url)
        
        # Make request to orchestration service
        response = await routing_service.forward_request(
            method="GET",
            url=f"{selected_url}/agents/{agent_name}",
            headers={
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Orchestration service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/agents/{agent_name}/metrics", response_model=AgentMetrics)
async def get_agent_metrics(
    agent_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Get agent metrics.
    
    Args:
        agent_name: Name of the agent
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        AgentMetrics: Agent performance metrics
    """
    try:
        # Route request to orchestration service
        orchestration_service_url = await routing_service.get_service_url("orchestration")
        if not orchestration_service_url:
            raise HTTPException(
                status_code=503,
                detail="Orchestration service not available"
            )
        
        # Select orchestration service instance
        selected_url = await load_balancer.select_instance("orchestration", orchestration_service_url)
        
        # Make request to orchestration service
        response = await routing_service.forward_request(
            method="GET",
            url=f"{selected_url}/agents/{agent_name}/metrics",
            headers={
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Orchestration service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/agents/{agent_name}/health")
async def get_agent_health(
    agent_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Get agent health status.
    
    Args:
        agent_name: Name of the agent
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Agent health status
    """
    try:
        # Route request to orchestration service
        orchestration_service_url = await routing_service.get_service_url("orchestration")
        if not orchestration_service_url:
            raise HTTPException(
                status_code=503,
                detail="Orchestration service not available"
            )
        
        # Select orchestration service instance
        selected_url = await load_balancer.select_instance("orchestration", orchestration_service_url)
        
        # Make request to orchestration service
        response = await routing_service.forward_request(
            method="GET",
            url=f"{selected_url}/agents/{agent_name}/health",
            headers={
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Orchestration service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/agents/{agent_name}/invoke", response_model=AgentResponse)
async def invoke_agent(
    agent_name: str,
    request: AgentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Invoke a specific agent.
    
    Args:
        agent_name: Name of the agent
        request: Agent request
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        AgentResponse: Agent response
    """
    try:
        # Add user context to request
        request.user_id = current_user["user_id"]
        request.context["user"] = current_user
        
        # Route request to orchestration service
        orchestration_service_url = await routing_service.get_service_url("orchestration")
        if not orchestration_service_url:
            raise HTTPException(
                status_code=503,
                detail="Orchestration service not available"
            )
        
        # Select orchestration service instance
        selected_url = await load_balancer.select_instance("orchestration", orchestration_service_url)
        
        # Make request to orchestration service
        response = await routing_service.forward_request(
            method="POST",
            url=f"{selected_url}/agents/{agent_name}/invoke",
            data=request.dict(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Orchestration service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
