# ============================================================================
# microservices/api-gateway/routers/documents.py
# ============================================================================
"""
Documents router for API Gateway service.
Handles document management requests and routes them to RAG agent service.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Upload a document to the RAG agent service.
    
    Args:
        file: Document file to upload
        metadata: Optional metadata for the document
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Upload result
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file provided"
            )
        
        # Check file size (10MB limit)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum size is 10MB"
            )
        
        # Route request to RAG agent service
        rag_service_url = await routing_service.get_service_url("rag-agent")
        if not rag_service_url:
            raise HTTPException(
                status_code=503,
                detail="RAG agent service not available"
            )
        
        # Select RAG agent service instance
        selected_url = await load_balancer.select_instance("rag-agent", rag_service_url)
        
        # Prepare form data
        form_data = {
            "file": (file.filename, file_content, file.content_type),
            "user_id": current_user["user_id"]
        }
        
        if metadata:
            form_data["metadata"] = metadata
        
        # Make request to RAG agent service
        response = await routing_service.forward_request(
            method="POST",
            url=f"{selected_url}/documents/upload",
            data=form_data,
            headers={
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"RAG agent service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/documents", response_model=PaginatedResponse)
async def list_documents(
    pagination: PaginationParams = Depends(),
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    List documents in the RAG agent service.
    
    Args:
        pagination: Pagination parameters
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        PaginatedResponse: List of documents
    """
    try:
        # Route request to RAG agent service
        rag_service_url = await routing_service.get_service_url("rag-agent")
        if not rag_service_url:
            raise HTTPException(
                status_code=503,
                detail="RAG agent service not available"
            )
        
        # Select RAG agent service instance
        selected_url = await load_balancer.select_instance("rag-agent", rag_service_url)
        
        # Make request to RAG agent service
        response = await routing_service.forward_request(
            method="GET",
            url=f"{selected_url}/documents",
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
                detail=f"RAG agent service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Get document details.
    
    Args:
        document_id: Document identifier
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Document details
    """
    try:
        # Route request to RAG agent service
        rag_service_url = await routing_service.get_service_url("rag-agent")
        if not rag_service_url:
            raise HTTPException(
                status_code=503,
                detail="RAG agent service not available"
            )
        
        # Select RAG agent service instance
        selected_url = await load_balancer.select_instance("rag-agent", rag_service_url)
        
        # Make request to RAG agent service
        response = await routing_service.forward_request(
            method="GET",
            url=f"{selected_url}/documents/{document_id}",
            params={"user_id": current_user["user_id"]},
            headers={
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"RAG agent service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Delete a document.
    
    Args:
        document_id: Document identifier
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Deletion result
    """
    try:
        # Route request to RAG agent service
        rag_service_url = await routing_service.get_service_url("rag-agent")
        if not rag_service_url:
            raise HTTPException(
                status_code=503,
                detail="RAG agent service not available"
            )
        
        # Select RAG agent service instance
        selected_url = await load_balancer.select_instance("rag-agent", rag_service_url)
        
        # Make request to RAG agent service
        response = await routing_service.forward_request(
            method="DELETE",
            url=f"{selected_url}/documents/{document_id}",
            params={"user_id": current_user["user_id"]},
            headers={
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"RAG agent service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/documents/search")
async def search_documents(
    query: str,
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
    routing_service: RoutingService = Depends(get_routing_service),
    load_balancer: LoadBalancer = Depends(get_load_balancer)
):
    """
    Search documents in the RAG agent service.
    
    Args:
        query: Search query
        limit: Maximum number of results
        current_user: Current authenticated user
        routing_service: Service for routing requests
        load_balancer: Load balancer for service selection
        
    Returns:
        Dict[str, Any]: Search results
    """
    try:
        # Route request to RAG agent service
        rag_service_url = await routing_service.get_service_url("rag-agent")
        if not rag_service_url:
            raise HTTPException(
                status_code=503,
                detail="RAG agent service not available"
            )
        
        # Select RAG agent service instance
        selected_url = await load_balancer.select_instance("rag-agent", rag_service_url)
        
        # Make request to RAG agent service
        response = await routing_service.forward_request(
            method="POST",
            url=f"{selected_url}/documents/search",
            data={
                "query": query,
                "limit": limit,
                "user_id": current_user["user_id"]
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {current_user.get('token', '')}"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"RAG agent service error: {response.text}"
            )
        
        return response.json()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
