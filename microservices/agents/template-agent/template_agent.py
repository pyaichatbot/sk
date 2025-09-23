# ============================================================================
# microservices/agents/template-agent/template_agent.py
# ============================================================================
"""
Template Agent implementation for microservice
Copy this template and customize for your specific agent needs
"""

import os
import asyncio
from typing import AsyncIterator, List, Dict, Any, Optional
from pathlib import Path
import hashlib
from datetime import datetime

from shared.models import AgentCapabilities, AgentResponse
from shared.infrastructure.observability.logging import get_logger
from shared.infrastructure.ai_services.service_factory import AIServiceFactory
from shared.config.settings import MicroserviceSettings

logger = get_logger(__name__)

class TemplateAgent:
    """Template agent - customize this class for your specific needs"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.agent_id = "template-agent-001"  # Change this for your agent
        self.capabilities = AgentCapabilities(
            agent_name="TemplateAgent",  # Change this for your agent
            capabilities=["template_processing", "data_analysis", "custom_operations"],  # Customize capabilities
            input_formats=["text", "json"],  # Customize input formats
            output_formats=["text", "json"],  # Customize output formats
            max_input_size=10000,  # Adjust based on your needs
            rate_limit=100,  # Adjust based on your needs
            timeout=30  # Adjust based on your needs
        )
        
        # Agent configuration - customize as needed
        self.name = "TemplateAgent"
        self.description = "Template agent for creating new agents - customize as needed"
        self.instructions = """
        You are a template AI agent. This is a skeleton implementation that should be customized for specific use cases.
        
        Your capabilities include:
        1. Template data processing
        2. Basic analysis and transformation
        3. Custom operations as defined
        
        Always provide accurate, helpful, and ethical responses.
        This template should be customized based on specific requirements.
        """
        
        # Initialize agent state
        self._initialized = False
        self._agent = None
        self.kernel = None
        
        # Metrics tracking
        self._metrics = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "average_response_time": 0.0
        }
        
        self.logger = get_logger(f"agent.{self.name}")
        self._start_time = datetime.utcnow()
        
        self.logger.info(
            "Template Agent initialized",
            agent_name=self.name,
            agent_id=self.agent_id,
            capabilities=self.capabilities.capabilities
        )
    
    async def initialize(self):
        """Initialize the agent with kernel and services"""
        if self._initialized:
            return
        
        try:
            # Create kernel
            self.kernel = await AIServiceFactory.create_kernel()
            
            # Create ChatCompletion agent
            from semantic_kernel.agents import ChatCompletionAgent
            self._agent = ChatCompletionAgent(
                kernel=self.kernel,
                name=self.name,
                instructions=self.instructions,
                description=self.description
            )
            
            self._initialized = True
            
            self.logger.info(
                "Template Agent initialization complete",
                agent_name=self.name
            )
            
        except Exception as e:
            self.logger.error(f"Template Agent initialization failed: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup agent resources"""
        try:
            if self._agent:
                # Cleanup agent if needed
                pass
            if self.kernel:
                # Cleanup kernel if needed
                pass
            self.logger.info("Template Agent cleanup completed")
        except Exception as e:
            self.logger.error(f"Template Agent cleanup failed: {e}")
    
    async def invoke(
        self,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """Invoke the template agent - customize this method for your needs"""
        if not self._initialized:
            raise RuntimeError("Agent not initialized")
        
        start_time = datetime.utcnow()
        
        try:
            # Update metrics
            self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
            
            # Customize this logic based on your agent's needs
            # This is a basic template implementation
            result = f"Template agent processed: {message}"
            
            # Create response
            response = AgentResponse(
                content=result,
                agent_id=self.agent_id,
                agent_name=self.name,
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                metadata={
                    "user_id": user_id,
                    "session_id": session_id,
                    "processed_at": datetime.utcnow().isoformat(),
                    "template_version": "1.0.0"
                }
            )
            
            return response
            
        except Exception as e:
            # Update metrics
            self._update_metrics(False, (datetime.utcnow() - start_time).total_seconds())
            
            self.logger.error(f"Template agent invocation failed: {e}")
            
            return AgentResponse(
                content="",
                agent_id=self.agent_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                error_code=type(e).__name__,
                metadata={"error_type": type(e).__name__}
            )
    
    async def invoke_stream(
        self,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[AgentResponse]:
        """Streaming version of invoke - customize for your needs"""
        if not self._initialized:
            raise RuntimeError("Agent not initialized")
        
        start_time = datetime.utcnow()
        
        try:
            # Customize this streaming logic based on your agent's needs
            # This is a basic template implementation
            chunks = [
                f"Template agent processing: {message}",
                "Step 1: Analyzing input...",
                "Step 2: Processing data...",
                "Step 3: Generating response...",
                f"Template agent completed processing: {message}"
            ]
            
            for i, chunk in enumerate(chunks):
                yield AgentResponse(
                    content=chunk,
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    metadata={
                        "user_id": user_id,
                        "session_id": session_id,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "streaming": True
                    }
                )
                # Simulate processing time
                await asyncio.sleep(0.1)
            
            # Update metrics
            self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
            
        except Exception as e:
            self.logger.error(f"Template agent streaming failed: {e}")
            yield AgentResponse(
                content="",
                agent_id=self.agent_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                error_code=type(e).__name__
            )
    
    async def process_data(self, data: str, user_id: Optional[str] = None, **kwargs) -> str:
        """Template-specific data processing method - customize as needed"""
        try:
            # Customize this method based on your agent's specific needs
            # This is a basic template implementation
            
            # Example processing logic
            processed_data = f"Processed: {data}"
            
            # Add any custom processing logic here
            # For example: data validation, transformation, analysis, etc.
            
            self.logger.info(
                "Template data processing completed",
                user_id=user_id,
                data_length=len(data)
            )
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Template data processing failed: {e}")
            raise
    
    def _update_metrics(self, success: bool, response_time: float):
        """Update agent metrics"""
        self._metrics["requests_total"] += 1
        if success:
            self._metrics["requests_successful"] += 1
        else:
            self._metrics["requests_failed"] += 1
        
        # Update average response time
        total_requests = self._metrics["requests_total"]
        current_avg = self._metrics["average_response_time"]
        self._metrics["average_response_time"] = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        from datetime import datetime
        
        return {
            **self._metrics,
            "agent_name": self.name,
            "agent_id": self.agent_id,
            "uptime": (datetime.utcnow() - self._start_time).total_seconds()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get agent health status"""
        success_rate = 0
        if self._metrics["requests_total"] > 0:
            success_rate = self._metrics["requests_successful"] / self._metrics["requests_total"]
        
        return {
            "status": "healthy" if success_rate > 0.8 else "degraded",
            "service": "template-agent",
            "version": "1.0.0",
            "uptime": (datetime.utcnow() - self._start_time).total_seconds(),
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "agent_initialized": self._initialized,
                "success_rate": success_rate,
                "average_response_time": self._metrics["average_response_time"]
            },
            "dependencies": {
                "kernel": self.kernel is not None,
                "agent": self._agent is not None
            },
            "metadata": {
                "capabilities": self.capabilities.capabilities,
                "input_formats": self.capabilities.input_formats,
                "output_formats": self.capabilities.output_formats
            }
        }
