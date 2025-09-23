# ============================================================================
# microservices/agents/search-agent/search_agent.py
# ============================================================================
"""
Search Agent implementation for microservice
Adapted from monolithic structure with microservice-specific modifications
"""

import aiohttp
import json
from typing import List, Dict, Any, AsyncIterator, Optional
from urllib.parse import quote
from pathlib import Path

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

class SearchAgent:
    """Internet search agent with web scraping capabilities"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.agent_id = "search-agent-001"
        self.capabilities = AgentCapabilities(
            agent_name="SearchAgent",
            capabilities=["web_search", "content_extraction", "url_validation"],
            input_formats=["text", "url"],
            output_formats=["text", "json"],
            max_input_size=10000,
            rate_limit=100,
            timeout=30
        )
        
        self.instructions = """
        You are a specialized search agent responsible for finding information on the internet.
        Your capabilities include:
        1. Performing web searches using search engines
        2. Extracting relevant content from web pages
        3. Validating and filtering search results
        4. Providing source citations and reliability scores
        
        Always prioritize recent and authoritative sources.
        Ensure all searches comply with robots.txt and rate limiting.
        Filter out inappropriate or unreliable content.
        """
        
        self.name = "SearchAgent"
        self.description = "Specialized agent for internet search and information retrieval"
        
        # Initialize services
        self.kernel: Optional[Kernel] = None
        self._agent: Optional[ChatCompletionAgent] = None
        self._initialized = False
        
        # Search specific settings
        self.max_results = 10
        self.timeout = 30
        self.user_agent = "SearchAgent/1.0 (Enterprise AI System)"
        
        # Performance metrics
        self._metrics = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "average_response_time": 0.0
        }
        
        self.logger = get_logger(f"agent.{self.name}")
        
        self.logger.info(
            "Search Agent initialized",
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
                "Search Agent initialization complete",
                agent_name=self.name
            )
            
        except Exception as e:
            self.logger.error(f"Search Agent initialization failed: {e}")
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
            self.logger.info("Search Agent cleanup completed")
        except Exception as e:
            self.logger.error(f"Search Agent cleanup failed: {e}")
    
    async def invoke(
        self,
        message: str,
        thread: Optional[ChatHistoryAgentThread] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        max_results: int = 5,
        include_snippets: bool = True,
        **kwargs
    ) -> AgentResponse:
        """Execute search operation"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Create enhanced search prompt
            search_prompt = self._create_search_prompt(message, max_results, include_snippets)
            
            # Get response from the agent
            user_message = ChatMessageContent(role=AuthorRole.USER, content=search_prompt)
            responses = await self._agent.invoke(user_message, thread)
            
            if responses:
                result = responses[-1].content
                
                # Update metrics
                self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
                
                # Create audit entry
                audit_entry = {
                    "timestamp": start_time.isoformat(),
                    "action": "web_search",
                    "user_id": user_id,
                    "session_id": session_id,
                    "query_hash": hash(message),
                    "max_results": max_results,
                    "agent_name": self.name,
                    "agent_id": self.agent_id
                }
                
                response = AgentResponse(
                    content=result,
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    metadata={
                        "thread_id": getattr(thread, 'id', None),
                        "max_results": max_results,
                        "include_snippets": include_snippets,
                        **kwargs
                    },
                    audit_trail=[audit_entry]
                )
                
                self.logger.info(
                    "Search completed successfully",
                    result_length=len(result),
                    response_time_ms=response.metadata["response_time_ms"]
                )
                
                return response
            else:
                return AgentResponse(
                    content="No search results found.",
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    success=False,
                    metadata={"warning": "No search results found"}
                )
                
        except Exception as e:
            # Update metrics
            self._update_metrics(False, (datetime.utcnow() - start_time).total_seconds())
            
            self.logger.error(f"Search execution failed: {e}")
            
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
        **kwargs
    ) -> AsyncIterator[AgentResponse]:
        """Execute streaming search"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Create enhanced search prompt
            search_prompt = self._create_search_prompt(message, self.max_results, True)
            
            # Stream response
            user_message = ChatMessageContent(role=AuthorRole.USER, content=search_prompt)
            
            async for response in self._agent.invoke_stream(user_message, thread):
                if hasattr(response, 'content') and response.content:
                    yield AgentResponse(
                        content=response.content,
                        agent_id=self.agent_id,
                        agent_name=self.name,
                        metadata={
                            "streaming": True,
                            "thread_id": getattr(thread, 'id', None)
                        }
                    )
            
            # Update metrics
            self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
            
        except Exception as e:
            self.logger.error(f"Streaming search failed: {e}")
            yield AgentResponse(
                content="",
                agent_id=self.agent_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                error_code=type(e).__name__
            )
    
    async def scrape_url(self, url: str, extract_options: Dict[str, bool] = None) -> Dict[str, Any]:
        """Scrape content from a URL"""
        if extract_options is None:
            extract_options = {
                "text": True,
                "links": False,
                "images": False
            }
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": self.user_agent}
            ) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Basic content extraction (in a real implementation, you'd use BeautifulSoup)
                        scraped_data = {
                            "url": url,
                            "status": "success",
                            "content_type": response.headers.get("content-type", ""),
                            "content_length": len(content)
                        }
                        
                        if extract_options.get("text", False):
                            # Extract text content (simplified)
                            scraped_data["text_content"] = content[:5000]  # Limit for demo
                        
                        if extract_options.get("links", False):
                            # Extract links (simplified)
                            import re
                            links = re.findall(r'href="([^"]*)"', content)
                            scraped_data["links"] = links[:20]  # Limit for demo
                        
                        if extract_options.get("images", False):
                            # Extract image URLs (simplified)
                            import re
                            images = re.findall(r'src="([^"]*\.(?:jpg|jpeg|png|gif|webp))"', content, re.IGNORECASE)
                            scraped_data["images"] = images[:10]  # Limit for demo
                        
                        return scraped_data
                    else:
                        return {
                            "url": url,
                            "status": "error",
                            "error": f"HTTP {response.status}",
                            "message": "Failed to fetch URL"
                        }
        
        except Exception as e:
            self.logger.error(f"URL scraping failed: {e}, url={url}")
            return {
                "url": url,
                "status": "error",
                "error": str(e),
                "message": "Failed to scrape URL"
            }
    
    async def validate_url(self, url: str) -> Dict[str, Any]:
        """Validate URL accessibility and safety"""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"User-Agent": self.user_agent}
            ) as session:
                async with session.head(url) as response:
                    return {
                        "url": url,
                        "accessible": response.status == 200,
                        "status_code": response.status,
                        "content_type": response.headers.get("content-type", ""),
                        "content_length": response.headers.get("content-length", ""),
                        "last_modified": response.headers.get("last-modified", ""),
                        "safe": response.status < 400
                    }
        
        except Exception as e:
            return {
                "url": url,
                "accessible": False,
                "error": str(e),
                "safe": False
            }
    
    def _create_search_prompt(self, query: str, max_results: int, include_snippets: bool) -> str:
        """Create enhanced search prompt"""
        prompt = f"""
        Please perform a comprehensive web search for the following query:
        
        Query: {query}
        
        Requirements:
        - Find up to {max_results} relevant results
        - Prioritize recent and authoritative sources
        - Include source citations and URLs
        - Provide relevance scores for each result
        """
        
        if include_snippets:
            prompt += "\n- Include brief snippets or summaries for each result"
        
        prompt += """
        
        Format your response as a structured list with:
        1. Title
        2. URL
        3. Brief description/snippet
        4. Relevance score (0.0-1.0)
        5. Source credibility assessment
        
        Ensure all information is accurate and properly cited.
        """
        
        return prompt
    
    async def _validate_request(self, message: str, user_id: Optional[str]):
        """Validate request against governance policies"""
        # Input validation
        if not message or len(message.strip()) == 0:
            raise ValueError("Search query cannot be empty")
        
        if len(message) > 500:  # Max query length
            raise ValueError("Search query too long")
        
        # Content filtering
        await self._filter_content(message)
        
        # Rate limiting check
        if user_id:
            await self._check_rate_limit(user_id)
    
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
            "uptime": (datetime.utcnow() - self.metadata.created_at).total_seconds()
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
