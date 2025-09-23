# ============================================================================
# microservices/api-gateway/routers/orchestration.py
# ============================================================================
"""
Orchestration router for API Gateway service.
Handles orchestration requests and routes them to orchestration service.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.models.orchestration import OrchestrationRequest, OrchestrationResponse, OrchestrationPattern
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
        "roles": ["user"]
    }

@router.get("/orchestration/patterns")
async def list_orchestration_patterns(
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    List available orchestration patterns.
    
    Args:
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: List of orchestration patterns
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
            url=f"{selected_url}/patterns",
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

@router.get("/orchestration/sessions", response_model=PaginatedResponse)
async def list_orchestration_sessions(
    pagination: PaginationParams = Depends(),
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    List orchestration sessions.
    
    Args:
        pagination: Pagination parameters
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        PaginatedResponse: List of orchestration sessions
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
            url=f"{selected_url}/sessions",
            params={
                "page": pagination.page,
                "size": pagination.size,
                "sort_by": pagination.sort_by,
                "sort_order": pagination.sort_order,
                "user_id": current_user["user_id"]
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

@router.get("/orchestration/sessions/{session_id}")
async def get_orchestration_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Get orchestration session details.
    
    Args:
        session_id: Session identifier
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Session details
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
            url=f"{selected_url}/sessions/{session_id}",
            params={"user_id": current_user["user_id"]},
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

@router.delete("/orchestration/sessions/{session_id}")
async def delete_orchestration_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Delete orchestration session.
    
    Args:
        session_id: Session identifier
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Deletion result
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
            method="DELETE",
            url=f"{selected_url}/sessions/{session_id}",
            params={"user_id": current_user["user_id"]},
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

@router.get("/orchestration/metrics")
async def get_orchestration_metrics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Get orchestration metrics.
    
    Args:
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Orchestration metrics
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
            url=f"{selected_url}/metrics",
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
