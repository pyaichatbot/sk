# ============================================================================
# microservices/api-gateway/routers/chat.py
# ============================================================================
"""
Chat router for API Gateway service.
Handles chat requests and routes them to the orchestration service.
"""

import asyncio
import json
from typing import Dict, Any, Optional, AsyncIterator
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.models.agent import AgentRequest, AgentResponse
from shared.models.orchestration import OrchestrationRequest, OrchestrationResponse, OrchestrationPattern
from shared.models.common import ErrorResponse
from shared.config.settings import MicroserviceSettings
from services.routing_service import RoutingService
from services.load_balancer import LoadBalancer
from middleware.security import SecurityMiddleware

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
    # For now, return a mock user
    return {
        "user_id": "user_123",
        "username": "test_user",
        "roles": ["user"]
    }

@router.post("/chat", response_model=OrchestrationResponse)
async def chat(
    request: OrchestrationRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer),
    settings: MicroserviceSettings = Depends(get_settings)
):
    """
    Process chat request through orchestration service.
    
    Args:
        request: Orchestration request
        background_tasks: Background tasks for async processing
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        OrchestrationResponse: Orchestration result
    """
    try:
        # Validate request
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )
        
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
            url=f"{selected_url}/orchestrate",
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
        
        # Parse response
        result = response.json()
        return OrchestrationResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/chat/stream")
async def chat_stream(
    request: OrchestrationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer),
    settings: MicroserviceSettings = Depends(get_settings)
):
    """
    Process streaming chat request through orchestration service.
    
    Args:
        request: Orchestration request with streaming enabled
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        StreamingResponse: Server-sent events stream
    """
    try:
        # Validate request
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )
        
        # Enable streaming
        request.streaming = True
        
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
        
        # Create streaming response
        async def generate_stream():
            try:
                # Make streaming request to orchestration service
                async with routing_service.stream_request(
                    method="POST",
                    url=f"{selected_url}/orchestrate/stream",
                    data=request.dict(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {current_user.get('token', '')}"
                    }
                ) as response:
                    
                    if response.status != 200:
                        error_data = await response.text()
                        yield f"data: {json.dumps({'error': f'Orchestration service error: {error_data}'})}\n\n"
                        return
                    
                    # Stream response data
                    async for chunk in response.content.iter_chunked(1024):
                        if chunk:
                            yield f"data: {chunk.decode('utf-8')}\n\n"
                            
            except Exception as e:
                error_response = {
                    "error": f"Streaming error: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(error_response)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Get chat history for a session.
    
    Args:
        session_id: Session identifier
        limit: Maximum number of messages to return
        offset: Number of messages to skip
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        JSONResponse: Chat history
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
            url=f"{selected_url}/sessions/{session_id}/history",
            params={"limit": limit, "offset": offset},
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

@router.delete("/chat/history/{session_id}")
async def delete_chat_history(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Delete chat history for a session.
    
    Args:
        session_id: Session identifier
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        JSONResponse: Deletion result
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
