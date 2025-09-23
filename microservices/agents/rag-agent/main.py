# ============================================================================
# microservices/agents/rag-agent/main.py
# ============================================================================
"""
RAG Agent Service - Retrieval-Augmented Generation microservice
Handles document processing, vector search, and contextual generation
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add shared modules to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from shared.config.settings import MicroserviceSettings
from shared.infrastructure.database import DatabaseManager
from shared.models import AgentRequest, AgentResponse, AgentCapabilities, HealthResponse
from shared.infrastructure.observability.logging import get_logger

# Import RAG agent implementation
from rag_agent import RAGAgent

# Initialize settings and logger
settings = MicroserviceSettings()
logger = get_logger(__name__)

# Global agent instance
rag_agent: Optional[RAGAgent] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global rag_agent
    
    # Startup
    logger.info("Starting RAG Agent Service")
    
    try:
        # Initialize database (optional for development)
        try:
            db_manager = DatabaseManager(settings)
            await db_manager.initialize()
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.warning(f"Database connection failed (continuing without database): {e}")
            db_manager = None
        
        # Initialize RAG agent
        rag_agent = RAGAgent(settings)
        await rag_agent.initialize()
        
        logger.info("RAG Agent Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start RAG Agent Service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down RAG Agent Service")
    if rag_agent:
        try:
            await rag_agent.cleanup()
            logger.info("RAG agent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up RAG agent: {e}")

# Create FastAPI app
app = FastAPI(
    title="RAG Agent Service",
    description="Retrieval-Augmented Generation microservice for document-based Q&A",
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
class DocumentUploadResponse(BaseModel):
    """Response model for document uploads"""
    document_id: str
    status: str
    message: str

class DocumentListResponse(BaseModel):
    """Response model for document listing"""
    documents: List[Dict[str, Any]]
    total_count: int

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    health_status = rag_agent.get_health_status()
    
    return HealthResponse(
        status=health_status["status"],
        service="rag-agent",
        version="1.0.0",
        uptime=health_status.get("uptime", 0)
    )

# RAG query endpoint
@app.post("/query", response_model=AgentResponse)
async def query_documents(request: AgentRequest):
    """Process a RAG query against the document collection"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Processing RAG query", query_length=len(request.message))
        
        response = await rag_agent.invoke(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            include_sources=request.parameters.get("include_sources", True),
            max_context_docs=request.parameters.get("max_context_docs", None)
        )
        
        return response
        
    except Exception as e:
        logger.error("RAG query failed", error=e)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

# Streaming query endpoint
@app.post("/query/stream")
async def query_documents_stream(request: AgentRequest):
    """Process a RAG query with streaming response"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        from fastapi.responses import StreamingResponse
        import json
        
        async def generate_stream():
            try:
                async for chunk in rag_agent.invoke_stream(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=request.session_id
                ):
                    yield f"data: {json.dumps(chunk.dict())}\n\n"
            except Exception as e:
                error_response = {
                    "content": "",
                    "metadata": {},
                    "agent_id": rag_agent.metadata.agent_id,
                    "status": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_response)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        logger.error("Streaming RAG query failed", error=e)
        raise HTTPException(status_code=500, detail=f"Streaming query failed: {str(e)}")

# Document upload endpoint
@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_id: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None)
):
    """Upload a document to the RAG system"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Parse metadata if provided
        doc_metadata = {}
        if metadata:
            import json
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning("Invalid metadata JSON provided")
        
        # Add document to RAG system
        doc_id = await rag_agent.add_document(
            file_path=temp_path,
            document_id=document_id,
            metadata=doc_metadata
        )
        
        # Clean up temp file
        os.remove(temp_path)
        
        logger.info("Document uploaded successfully", document_id=doc_id, filename=file.filename)
        
        return DocumentUploadResponse(
            document_id=doc_id,
            status="success",
            message="Document uploaded and processed successfully"
        )
        
    except Exception as e:
        logger.error("Document upload failed", error=e, filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")

# Batch document upload endpoint
@app.post("/documents/upload/batch")
async def upload_documents_batch(files: List[UploadFile] = File(...)):
    """Upload multiple documents to the RAG system"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    results = []
    
    for file in files:
        try:
            # Save uploaded file temporarily
            temp_path = f"/tmp/{file.filename}"
            with open(temp_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Add document to RAG system
            doc_id = await rag_agent.add_document(file_path=temp_path)
            
            # Clean up temp file
            os.remove(temp_path)
            
            results.append({
                "filename": file.filename,
                "document_id": doc_id,
                "status": "success"
            })
            
        except Exception as e:
            logger.error("Batch document upload failed", error=e, filename=file.filename)
            results.append({
                "filename": file.filename,
                "document_id": None,
                "status": "error",
                "error": str(e)
            })
    
    return {"results": results}

# List documents endpoint
@app.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """List all documents in the RAG system"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        documents = await rag_agent.list_documents()
        
        return DocumentListResponse(
            documents=documents,
            total_count=len(documents)
        )
        
    except Exception as e:
        logger.error("Failed to list documents", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

# Get document summary endpoint
@app.get("/documents/{document_id}/summary")
async def get_document_summary(document_id: str):
    """Get summary of a specific document"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        summary = await rag_agent.get_document_summary(document_id)
        
        return {
            "document_id": document_id,
            "summary": summary
        }
        
    except Exception as e:
        logger.error("Failed to get document summary", error=e, document_id=document_id)
        raise HTTPException(status_code=500, detail=f"Failed to get document summary: {str(e)}")

# Remove document endpoint
@app.delete("/documents/{document_id}")
async def remove_document(document_id: str):
    """Remove a document from the RAG system"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        success = await rag_agent.remove_document(document_id)
        
        if success:
            return {"message": "Document removed successfully", "document_id": document_id}
        else:
            raise HTTPException(status_code=404, detail="Document not found")
        
    except Exception as e:
        logger.error("Failed to remove document", error=e, document_id=document_id)
        raise HTTPException(status_code=500, detail=f"Failed to remove document: {str(e)}")

# Update RAG settings endpoint
@app.put("/settings")
async def update_settings(
    max_context_length: Optional[int] = Query(None),
    similarity_threshold: Optional[float] = Query(None),
    max_retrieved_docs: Optional[int] = Query(None)
):
    """Update RAG agent settings"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        rag_agent.update_settings(
            max_context_length=max_context_length,
            similarity_threshold=similarity_threshold,
            max_retrieved_docs=max_retrieved_docs
        )
        
        return {
            "message": "Settings updated successfully",
            "settings": {
                "max_context_length": rag_agent.max_context_length,
                "similarity_threshold": rag_agent.similarity_threshold,
                "max_retrieved_docs": rag_agent.max_retrieved_docs
            }
        }
        
    except Exception as e:
        logger.error("Failed to update settings", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")

# Get agent metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Get agent performance metrics"""
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        metrics = rag_agent.get_metrics()
        return metrics
        
    except Exception as e:
        logger.error("Failed to get metrics", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
