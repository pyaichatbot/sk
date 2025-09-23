# ============================================================================
# microservices/agents/llm-agent/llm_agent.py
# ============================================================================
"""
LLM Agent implementation for microservice
Adapted from monolithic structure with microservice-specific modifications
"""

from typing import AsyncIterator, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

# Add shared modules to path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from semantic_kernel.contents import ChatMessageContent, AuthorRole
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel import Kernel

from shared.models import AgentCapabilities, AgentResponse
from shared.infrastructure.observability.logging import get_logger
from shared.infrastructure.ai_services.service_factory import AIServiceFactory
from shared.config.settings import MicroserviceSettings

logger = get_logger(__name__)

class LLMAgent:
    """General purpose LLM agent for natural language processing"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.agent_id = "llm-agent-001"
        self.capabilities = AgentCapabilities(
            agent_name="LLMAgent",
            capabilities=["text_generation", "summarization", "analysis", "conversation"],
            input_formats=["text", "json"],
            output_formats=["text", "json"],
            max_input_size=50000,
            rate_limit=200,
            timeout=60
        )
        
        self.instructions = """
        You are a general purpose AI assistant powered by a large language model.
        Your capabilities include:
        1. Natural language understanding and generation
        2. Text summarization and analysis
        3. Question answering and conversation
        4. Content creation and editing
        5. Code explanation and documentation
        
        Always provide accurate, helpful, and ethical responses.
        Cite sources when appropriate and acknowledge limitations.
        Respect user privacy and maintain confidentiality.
        Follow enterprise governance and compliance requirements.
        """
        
        self.name = "LLMAgent"
        self.description = "General purpose LLM agent for natural language processing tasks"
        
        # Initialize services
        self.kernel: Optional[Kernel] = None
        self._agent: Optional[ChatCompletionAgent] = None
        self._initialized = False
        
        # LLM specific settings
        self.default_temperature = 0.7
        self.default_max_tokens = 4096
        
        # Performance metrics
        self._metrics = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "average_response_time": 0.0
        }
        
        self.logger = get_logger(f"agent.{self.name}")
        self._start_time = datetime.utcnow()
        
        self.logger.info(
            "LLM Agent initialized",
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
            self._agent = ChatCompletionAgent(
                kernel=self.kernel,
                name=self.name,
                instructions=self.instructions,
                description=self.description
            )
            
            self._initialized = True
            
            self.logger.info(
                "LLM Agent initialization complete",
                agent_name=self.name
            )
            
        except Exception as e:
            self.logger.error(f"LLM Agent initialization failed: {e}")
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
            self.logger.info("LLM Agent cleanup completed")
        except Exception as e:
            self.logger.error(f"LLM Agent cleanup failed: {e}")
    
    async def invoke(
        self,
        message: str,
        thread: Optional[ChatHistoryAgentThread] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AgentResponse:
        """Execute LLM generation"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Create enhanced prompt with parameters
            enhanced_prompt = self._create_enhanced_prompt(message, temperature, max_tokens)
            
            # Get response from the agent
            user_message = ChatMessageContent(role=AuthorRole.USER, content=enhanced_prompt)
            responses = await self._agent.invoke(user_message, thread)
            
            if responses:
                result = responses[-1].content
                
                # Update metrics
                self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
                
                # Create audit entry
                audit_entry = {
                    "timestamp": start_time.isoformat(),
                    "action": "llm_generation",
                    "user_id": user_id,
                    "session_id": session_id,
                    "message_hash": hash(message),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "agent_name": self.name,
                    "agent_id": self.agent_id
                }
                
                response = AgentResponse(
                    content=result,
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    tokens_used=len(message.split()) + len(result.split()),
                    metadata={
                        "thread_id": getattr(thread, 'id', None),
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "input_tokens": len(message.split()),
                        "output_tokens": len(result.split()),
                        **kwargs
                    },
                    audit_trail=[audit_entry]
                )
                
                self.logger.info(
                    "LLM generation completed",
                    input_tokens=response.metadata["input_tokens"],
                    output_tokens=response.metadata["output_tokens"],
                    response_time_ms=response.metadata["response_time_ms"]
                )
                
                return response
            else:
                return AgentResponse(
                    content="No response generated.",
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    success=False,
                    metadata={"warning": "No response generated"}
                )
                
        except Exception as e:
            # Update metrics
            self._update_metrics(False, (datetime.utcnow() - start_time).total_seconds())
            
            self.logger.error(f"LLM generation failed: {e}")
            
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
        thread: Optional[ChatHistoryAgentThread] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[AgentResponse]:
        """Execute streaming LLM generation"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Create enhanced prompt with parameters
            enhanced_prompt = self._create_enhanced_prompt(message, temperature, max_tokens)
            
            # Stream response
            user_message = ChatMessageContent(role=AuthorRole.USER, content=enhanced_prompt)
            
            async for response in self._agent.invoke_stream(user_message, thread):
                if hasattr(response, 'content') and response.content:
                    yield AgentResponse(
                        content=response.content,
                        agent_id=self.agent_id,
                        agent_name=self.name,
                        metadata={
                            "streaming": True,
                            "thread_id": getattr(thread, 'id', None),
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        }
                    )
            
            # Update metrics
            self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
            
        except Exception as e:
            self.logger.error(f"Streaming LLM generation failed: {e}")
            yield AgentResponse(
                content="",
                agent_id=self.agent_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                error_code=type(e).__name__
            )
    
    async def summarize(
        self,
        text: str,
        max_length: int = 200,
        style: str = "concise",
        user_id: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """Specialized summarization method"""
        try:
            prompt = f"""
            Please provide a {style} summary of the following text in approximately {max_length} words:

            {text}

            Summary:
            """
            
            response = await self.invoke(
                message=prompt,
                user_id=user_id,
                temperature=0.3,  # Lower temperature for more consistent summaries
                **kwargs
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Summarization failed: {e}")
            raise
    
    async def analyze_sentiment(self, text: str, user_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        try:
            prompt = f"""
            Analyze the sentiment of the following text and return a JSON response with:
            - sentiment: positive/negative/neutral
            - confidence: 0.0 to 1.0
            - emotions: list of detected emotions
            - reasoning: brief explanation

            Text: {text}
            """
            
            response = await self.invoke(
                message=prompt,
                user_id=user_id,
                temperature=0.1,  # Very low temperature for consistent analysis
                **kwargs
            )
            
            try:
                import json
                return json.loads(response.content)
            except:
                return {"error": "Failed to parse sentiment analysis", "raw_result": response.content}
                
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {e}")
            return {"error": f"Sentiment analysis failed: {str(e)}"}
    
    async def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """Translate text to another language"""
        try:
            if source_language:
                prompt = f"Please translate the following text from {source_language} to {target_language}:\n\n{text}\n\nProvide only the translation."
            else:
                prompt = f"Please translate the following text to {target_language}:\n\n{text}\n\nProvide only the translation."
            
            response = await self.invoke(
                message=prompt,
                user_id=user_id,
                temperature=0.2,  # Low temperature for consistent translations
                **kwargs
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Translation failed: {e}")
            raise
    
    async def explain_code(
        self,
        code: str,
        language: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """Explain code functionality"""
        try:
            if language:
                prompt = f"Please explain the following {language} code:\n\n```{language}\n{code}\n```\n\nProvide a clear explanation of what the code does, how it works, and any important details."
            else:
                prompt = f"Please explain the following code:\n\n```\n{code}\n```\n\nProvide a clear explanation of what the code does, how it works, and any important details."
            
            response = await self.invoke(
                message=prompt,
                user_id=user_id,
                temperature=0.3,  # Lower temperature for more accurate explanations
                **kwargs
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Code explanation failed: {e}")
            raise
    
    def _create_enhanced_prompt(self, message: str, temperature: float, max_tokens: int) -> str:
        """Create enhanced prompt with generation parameters"""
        prompt = f"""
        {message}
        
        Generation Parameters:
        - Temperature: {temperature} (creativity level)
        - Max Tokens: {max_tokens} (response length limit)
        
        Please provide a comprehensive and helpful response.
        """
        
        return prompt
    
    async def _validate_request(self, message: str, user_id: Optional[str]):
        """Validate request against governance policies"""
        # Input validation
        if not message or len(message.strip()) == 0:
            raise ValueError("Message cannot be empty")
        
        if len(message) > 50000:  # Max message length
            raise ValueError("Message too long")
        
        # Rate limiting check
        if user_id:
            await self._check_rate_limit(user_id)
        
        # Content filtering
        await self._filter_content(message)
    
    async def _check_rate_limit(self, user_id: str):
        """Check rate limiting for user"""
        # Implementation depends on rate limiting strategy
        # This could use Redis or in-memory store
        pass
    
    async def _filter_content(self, message: str):
        """Filter content for inappropriate content"""
        # Implement content filtering logic
        # Could use external services or internal rules
        pass
    
    def _update_metrics(self, success: bool, response_time: float):
        """Update performance metrics"""
        from datetime import datetime
        
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
        """Get agent performance metrics"""
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
        
        status = "healthy"
        if success_rate < 0.95:
            status = "degraded"
        if success_rate < 0.8:
            status = "unhealthy"
        
        return {
            "status": status,
            "success_rate": success_rate,
            "average_response_time": self._metrics["average_response_time"],
            "total_requests": self._metrics["requests_total"],
            "initialized": self._initialized
        }
