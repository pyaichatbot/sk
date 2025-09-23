# ============================================================================
# microservices/agents/search-agent/main.py
# ============================================================================
"""
Search Agent Service - Internet search and web scraping microservice
Handles web search, content extraction, and information retrieval
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add shared modules to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from shared.config.settings import MicroserviceSettings
from shared.infrastructure.database import DatabaseManager
from shared.models import AgentRequest, AgentResponse, AgentCapabilities, HealthResponse
from shared.infrastructure.observability.logging import get_logger

# Import Search agent implementation
from search_agent import SearchAgent

# Initialize settings and logger
settings = MicroserviceSettings()
logger = get_logger(__name__)

# Global agent instance
search_agent: Optional[SearchAgent] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global search_agent
    
    # Startup
    logger.info("Starting Search Agent Service")
    
    try:
        # Initialize database (optional for development)
        try:
            db_manager = DatabaseManager(settings)
            await db_manager.initialize()
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.warning(f"Database connection failed (continuing without database): {e}")
            db_manager = None
        
        # Initialize Search agent
        search_agent = SearchAgent(settings)
        await search_agent.initialize()
        
        logger.info("Search Agent Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Search Agent Service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Search Agent Service")
    if search_agent:
        try:
            await search_agent.cleanup()
            logger.info("Search agent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up search agent: {e}")

# Create FastAPI app
app = FastAPI(
    title="Search Agent Service",
    description="Internet search and web scraping microservice for information retrieval",
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
# All Search-specific request models removed - using unified AgentRequest

class SearchResult(BaseModel):
    """Search result model"""
    title: str
    url: str
    snippet: Optional[str] = None
    relevance_score: float
    source: str

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    health_status = search_agent.get_health_status()
    
    return HealthResponse(
        status=health_status["status"],
        service="search-agent",
        version="1.0.0",
        uptime=health_status.get("uptime", 0)
    )

# Search endpoint
@app.post("/search", response_model=AgentResponse)
async def search_web(request: AgentRequest):
    """Perform web search and return results"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Processing search query", query=request.message, max_results=request.parameters.get("max_results", 5))
        
        response = await search_agent.invoke(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            max_results=request.parameters.get("max_results", 5),
            include_snippets=request.parameters.get("include_snippets", True)
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# Streaming search endpoint
@app.post("/search/stream")
async def search_web_stream(request: AgentRequest):
    """Perform web search with streaming response"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        from fastapi.responses import StreamingResponse
        import json
        
        async def generate_stream():
            try:
                async for chunk in search_agent.invoke_stream(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=request.session_id
                ):
                    yield f"data: {json.dumps(chunk.dict())}\n\n"
            except Exception as e:
                error_response = {
                    "content": "",
                    "metadata": {},
                    "agent_id": search_agent.metadata.agent_id,
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
        logger.error(f"Streaming search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming search failed: {str(e)}")

# Web scraping endpoint
@app.post("/scrape", response_model=AgentResponse)
async def scrape_webpage(request: AgentRequest):
    """Scrape content from a webpage"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Extract parameters from unified request
        url = request.parameters.get("url")
        extract_text = request.parameters.get("extract_text", True)
        extract_links = request.parameters.get("extract_links", False)
        extract_images = request.parameters.get("extract_images", False)
        
        logger.info("Scraping webpage", url=url)
        
        # Create scraping prompt
        scrape_prompt = f"""
        Please scrape the following webpage and extract the requested information:
        URL: {url}
        
        Extract:
        - Text content: {extract_text}
        - Links: {extract_links}
        - Images: {extract_images}
        
        Provide a structured response with the extracted information.
        """
        
        response = await search_agent.invoke(
            message=scrape_prompt,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Web scraping failed: {e}, url={url}")
        raise HTTPException(status_code=500, detail=f"Web scraping failed: {str(e)}")

# URL validation endpoint
@app.get("/validate-url")
async def validate_url(url: str = Query(...)):
    """Validate if a URL is accessible and safe"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Use the search agent's URL validation capabilities
        validation_prompt = f"""
        Please validate the following URL for accessibility and safety:
        URL: {url}
        
        Check:
        1. URL format validity
        2. Accessibility (HTTP status)
        3. Content type
        4. Security considerations
        5. Robots.txt compliance
        
        Provide a validation report.
        """
        
        response = await search_agent.invoke(message=validation_prompt)
        
        return {
            "url": url,
            "validation_result": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error(f"URL validation failed: {e}, url={url}")
        raise HTTPException(status_code=500, detail=f"URL validation failed: {str(e)}")

# Search suggestions endpoint
@app.get("/suggestions")
async def get_search_suggestions(query: str = Query(...)):
    """Get search suggestions for a query"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        suggestions_prompt = f"""
        Provide search suggestions for the following query:
        Query: {query}
        
        Generate 5-10 related search terms that might be useful for the user.
        Consider synonyms, related topics, and common variations.
        """
        
        response = await search_agent.invoke(message=suggestions_prompt)
        
        return {
            "query": query,
            "suggestions": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error(f"Search suggestions failed: {e}, query={query}")
        raise HTTPException(status_code=500, detail=f"Search suggestions failed: {str(e)}")

# Get agent metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Get agent performance metrics"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        metrics = search_agent.get_metrics()
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

# Get search history endpoint (if implemented)
@app.get("/history")
async def get_search_history(
    user_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100)
):
    """Get search history for a user"""
    if not search_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # This would typically query a database for search history
        # For now, return a placeholder response
        return {
            "message": "Search history feature not yet implemented",
            "user_id": user_id,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Failed to get search history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get search history: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
