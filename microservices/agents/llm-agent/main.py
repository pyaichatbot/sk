# ============================================================================
# microservices/agents/llm-agent/main.py
# ============================================================================
"""
LLM Agent Service - General purpose language processing microservice
Handles text generation, summarization, analysis, and conversation
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

# Import LLM agent implementation
from llm_agent import LLMAgent

# Initialize settings and logger
settings = MicroserviceSettings()
logger = get_logger(__name__)

# Global agent instance
llm_agent: Optional[LLMAgent] = None
service_discovery_integration: Optional[ServiceDiscoveryIntegration] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global llm_agent, service_discovery_integration
    
    # Startup
    logger.info("Starting LLM Agent Service")
    
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
                tags=["llm-agent", "agent", "llm", "language-processing"],
                metadata={
                    "version": settings.service_version,
                    "environment": settings.environment.value,
                    "capabilities": ["text_generation", "summarization", "sentiment_analysis", "translation", "code_explanation"]
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
        
        # Initialize LLM agent
        llm_agent = LLMAgent(settings)
        await llm_agent.initialize()
        
        logger.info("LLM Agent Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start LLM Agent Service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down LLM Agent Service")
    
    if llm_agent:
        try:
            await llm_agent.cleanup()
            logger.info("LLM agent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up LLM agent: {e}")
    
    if service_discovery_integration:
        try:
            await service_discovery_integration.shutdown()
            logger.info("Service discovery integration cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up service discovery integration: {e}")

# Create FastAPI app
app = FastAPI(
    title="LLM Agent Service",
    description="General purpose language processing microservice for text generation and analysis",
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
# All LLM-specific request models removed - using unified AgentRequest

class SentimentResponse(BaseModel):
    """Response model for sentiment analysis"""
    sentiment: str
    confidence: float
    emotions: List[str]
    reasoning: str

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Get service discovery health if available
    discovery_health = {}
    if service_discovery_integration and service_discovery_integration.discovery_manager:
        try:
            discovery_health = await service_discovery_integration.discovery_manager.health_check()
        except Exception as e:
            logger.warning(f"Failed to get service discovery health: {e}")
    
    health_status = llm_agent.get_health_status()
    
    return HealthResponse(
        status=health_status["status"],
        service="llm-agent",
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
    Get service discovery information for the LLM Agent.
    Returns:
        dict: Service discovery information.
    """
    if service_discovery_integration:
        return {
            "service_name": settings.service_name,
            "service_port": settings.service_port,
            "version": settings.service_version,
            "environment": settings.environment.value,
            "tags": ["llm-agent", "agent", "llm", "language-processing"],
            "metadata": {
                "capabilities": ["text_generation", "summarization", "sentiment_analysis", "translation", "code_explanation"]
            },
            "is_initialized": service_discovery_integration.is_initialized
        }
    raise HTTPException(status_code=503, detail="Service discovery not initialized")


@app.get("/discovery-metrics", summary="Get service discovery metrics")
async def get_discovery_metrics():
    """
    Get service discovery metrics for the LLM Agent.
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

# General LLM endpoint
@app.post("/generate", response_model=AgentResponse)
async def generate_text(request: AgentRequest):
    """Generate text using the LLM"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Processing LLM generation request", message_length=len(request.message))
        
        response = await llm_agent.invoke(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id,
            temperature=request.parameters.get("temperature", 0.7),
            max_tokens=request.parameters.get("max_tokens", 4096)
        )
        
        return response
        
    except Exception as e:
        logger.error("LLM generation failed", error=e)
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")

# Streaming generation endpoint
@app.post("/generate/stream")
async def generate_text_stream(request: AgentRequest):
    """Generate text with streaming response"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        from fastapi.responses import StreamingResponse
        import json
        
        async def generate_stream():
            try:
                async for chunk in llm_agent.invoke_stream(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    temperature=request.parameters.get("temperature", 0.7),
                    max_tokens=request.parameters.get("max_tokens", 4096)
                ):
                    yield f"data: {json.dumps(chunk.dict())}\n\n"
            except Exception as e:
                error_response = {
                    "content": "",
                    "metadata": {},
                    "agent_id": llm_agent.metadata.agent_id,
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
        logger.error("Streaming LLM generation failed", error=e)
        raise HTTPException(status_code=500, detail=f"Streaming generation failed: {str(e)}")

# Summarization endpoint
@app.post("/summarize", response_model=AgentResponse)
async def summarize_text(request: AgentRequest):
    """Summarize text using the LLM"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Extract parameters from unified request
        text = request.parameters.get("text")
        max_length = request.parameters.get("max_length", 200)
        style = request.parameters.get("style", "concise")
        
        logger.info("Processing text summarization", text_length=len(text))
        
        response = await llm_agent.summarize(
            text=text,
            max_length=max_length,
            style=style,
            user_id=request.user_id
        )
        
        return response
        
    except Exception as e:
        logger.error("Text summarization failed", error=e)
        raise HTTPException(status_code=500, detail=f"Text summarization failed: {str(e)}")

# Sentiment analysis endpoint
@app.post("/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(request: AgentRequest):
    """Analyze sentiment of text"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Extract parameters from unified request
        text = request.parameters.get("text")
        
        logger.info("Processing sentiment analysis", text_length=len(text))
        
        result = await llm_agent.analyze_sentiment(
            text=text,
            user_id=request.user_id
        )
        
        # Parse the result to extract structured data
        if isinstance(result, dict) and "error" not in result:
            return SentimentResponse(
                sentiment=result.get("sentiment", "neutral"),
                confidence=result.get("confidence", 0.5),
                emotions=result.get("emotions", []),
                reasoning=result.get("reasoning", "")
            )
        else:
            # Fallback if parsing fails
            return SentimentResponse(
                sentiment="neutral",
                confidence=0.0,
                emotions=[],
                reasoning=result.get("raw_result", "Analysis failed")
            )
        
    except Exception as e:
        logger.error("Sentiment analysis failed", error=e)
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")

# Text analysis endpoint
@app.post("/analyze")
async def analyze_text(
    text: str = Body(..., embed=True),
    analysis_type: str = Query("general", description="Type of analysis (general, grammar, style, readability)"),
    user_id: Optional[str] = Query(None)
):
    """Perform various types of text analysis"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Processing text analysis", text_length=len(text), analysis_type=analysis_type)
        
        # Create analysis prompt based on type
        if analysis_type == "grammar":
            prompt = f"Please analyze the following text for grammar, spelling, and punctuation errors:\n\n{text}\n\nProvide corrections and suggestions."
        elif analysis_type == "style":
            prompt = f"Please analyze the following text for writing style, tone, and clarity:\n\n{text}\n\nProvide suggestions for improvement."
        elif analysis_type == "readability":
            prompt = f"Please analyze the following text for readability and complexity:\n\n{text}\n\nProvide readability score and suggestions."
        else:  # general
            prompt = f"Please provide a comprehensive analysis of the following text:\n\n{text}\n\nInclude insights about content, structure, and quality."
        
        response = await llm_agent.invoke(
            message=prompt,
            user_id=user_id
        )
        
        return {
            "text": text,
            "analysis_type": analysis_type,
            "analysis": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error("Text analysis failed", error=e)
        raise HTTPException(status_code=500, detail=f"Text analysis failed: {str(e)}")

# Translation endpoint
@app.post("/translate")
async def translate_text(
    text: str = Body(..., embed=True),
    target_language: str = Query(..., description="Target language for translation"),
    source_language: Optional[str] = Query(None, description="Source language (auto-detect if not provided)"),
    user_id: Optional[str] = Query(None)
):
    """Translate text to another language"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Processing text translation", text_length=len(text), target_language=target_language)
        
        # Create translation prompt
        if source_language:
            prompt = f"Please translate the following text from {source_language} to {target_language}:\n\n{text}\n\nProvide only the translation."
        else:
            prompt = f"Please translate the following text to {target_language}:\n\n{text}\n\nProvide only the translation."
        
        response = await llm_agent.invoke(
            message=prompt,
            user_id=user_id
        )
        
        return {
            "original_text": text,
            "source_language": source_language or "auto-detected",
            "target_language": target_language,
            "translation": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error("Text translation failed", error=e)
        raise HTTPException(status_code=500, detail=f"Text translation failed: {str(e)}")

# Code explanation endpoint
@app.post("/explain-code")
async def explain_code(
    code: str = Body(..., embed=True),
    language: Optional[str] = Query(None, description="Programming language"),
    user_id: Optional[str] = Query(None)
):
    """Explain code functionality"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info("Processing code explanation", code_length=len(code), language=language)
        
        # Create code explanation prompt
        if language:
            prompt = f"Please explain the following {language} code:\n\n```{language}\n{code}\n```\n\nProvide a clear explanation of what the code does, how it works, and any important details."
        else:
            prompt = f"Please explain the following code:\n\n```\n{code}\n```\n\nProvide a clear explanation of what the code does, how it works, and any important details."
        
        response = await llm_agent.invoke(
            message=prompt,
            user_id=user_id
        )
        
        return {
            "code": code,
            "language": language or "auto-detected",
            "explanation": response.content,
            "status": response.status
        }
        
    except Exception as e:
        logger.error("Code explanation failed", error=e)
        raise HTTPException(status_code=500, detail=f"Code explanation failed: {str(e)}")

# Get agent metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Get agent performance metrics"""
    if not llm_agent:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        metrics = llm_agent.get_metrics()
        return metrics
        
    except Exception as e:
        logger.error("Failed to get metrics", error=e)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )
