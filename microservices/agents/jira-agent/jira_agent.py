# ============================================================================
# microservices/agents/jira-agent/jira_agent.py
# ============================================================================
"""
JIRA Agent implementation for microservice
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

class JiraAgent:
    """JIRA integration agent for project management"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.agent_id = "jira-agent-001"
        self.capabilities = AgentCapabilities(
            agent_name="JiraAgent",
            capabilities=["jira_integration", "issue_management", "project_tracking", "reporting"],
            input_formats=["text", "json"],
            output_formats=["text", "json"],
            max_input_size=10000,
            rate_limit=50,
            timeout=30
        )
        
        self.instructions = """
        You are a specialized JIRA agent responsible for project management and issue tracking.
        Your capabilities include:
        1. Creating, updating, and managing JIRA issues
        2. Searching and filtering issues across projects
        3. Managing project workflows and transitions
        4. Generating reports and analytics
        5. Managing user permissions and project access
        
        Always ensure proper authorization before accessing or modifying issues.
        Maintain detailed audit trails for all JIRA operations.
        Respect project permissions and access controls.
        """
        
        self.name = "JiraAgent"
        self.description = "Specialized agent for JIRA project management and issue tracking"
        
        # Initialize services
        self.kernel: Optional[Kernel] = None
        self._agent: Optional[ChatCompletionAgent] = None
        self._initialized = False
        
        # JIRA specific settings
        self.jira_url = None  # Will be configured via environment or settings
        self.username = None
        self.api_token = None
        
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
            "JIRA Agent initialized",
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
            
            # Initialize JIRA connection (in a real implementation, this would connect to JIRA)
            await self._initialize_jira_connection()
            
            self._initialized = True
            
            self.logger.info(
                "JIRA Agent initialization complete",
                agent_name=self.name
            )
            
        except Exception as e:
            self.logger.error(f"JIRA Agent initialization failed: {e}")
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
            self.logger.info("JIRA Agent cleanup completed")
        except Exception as e:
            self.logger.error(f"JIRA Agent cleanup failed: {e}")
    
    async def invoke(
        self,
        message: str,
        thread: Optional[ChatHistoryAgentThread] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """Execute JIRA operation"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Create enhanced JIRA operation prompt
            jira_prompt = self._create_jira_prompt(message, user_id)
            
            # Get response from the agent
            user_message = ChatMessageContent(role=AuthorRole.USER, content=jira_prompt)
            responses = await self._agent.invoke(user_message, thread)
            
            if responses:
                result = responses[-1].content
                
                # Update metrics
                self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
                
                # Create audit entry
                audit_entry = {
                    "timestamp": start_time.isoformat(),
                    "action": "jira_operation",
                    "user_id": user_id,
                    "session_id": session_id,
                    "operation_hash": hash(message),
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
                        **kwargs
                    },
                    audit_trail=[audit_entry]
                )
                
                self.logger.info(
                    "JIRA operation completed",
                    result_length=len(result),
                    response_time_ms=response.metadata["response_time_ms"]
                )
                
                return response
            else:
                return AgentResponse(
                    content="JIRA operation completed with no results.",
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    success=False,
                    metadata={"warning": "JIRA operation completed with no results"}
                )
                
        except Exception as e:
            # Update metrics
            self._update_metrics(False, (datetime.utcnow() - start_time).total_seconds())
            
            self.logger.error(f"JIRA operation failed: {e}")
            
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
        """Execute streaming JIRA operation"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Create enhanced JIRA operation prompt
            jira_prompt = self._create_jira_prompt(message, user_id)
            
            # Stream response
            user_message = ChatMessageContent(role=AuthorRole.USER, content=jira_prompt)
            
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
            self.logger.error(f"Streaming JIRA operation failed: {e}")
            yield AgentResponse(
                content="",
                agent_id=self.agent_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                error_code=type(e).__name__
            )
    
    async def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[list] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new JIRA issue"""
        try:
            # In a real implementation, this would make actual JIRA API calls
            # For now, we'll simulate the operation
            
            issue_data = {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": description or "",
                "assignee": {"name": assignee} if assignee else None,
                "priority": {"name": priority} if priority else None,
                "labels": labels or []
            }
            
            # Simulate issue creation
            issue_key = f"{project_key}-{hash(summary) % 10000}"
            
            self.logger.info(
                "JIRA issue created",
                issue_key=issue_key,
                project_key=project_key,
                issue_type=issue_type,
                user_id=user_id
            )
            
            return {
                "issue_key": issue_key,
                "status": "success",
                "message": f"Issue {issue_key} created successfully",
                "data": issue_data
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create JIRA issue: {e}")
            raise
    
    async def update_issue(
        self,
        issue_key: str,
        fields: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing JIRA issue"""
        try:
            # In a real implementation, this would make actual JIRA API calls
            # For now, we'll simulate the operation
            
            self.logger.info(
                "JIRA issue updated",
                issue_key=issue_key,
                fields=fields,
                user_id=user_id
            )
            
            return {
                "issue_key": issue_key,
                "status": "success",
                "message": f"Issue {issue_key} updated successfully",
                "updated_fields": fields
            }
            
        except Exception as e:
            self.logger.error(f"Failed to update JIRA issue: {e}, issue_key={issue_key}")
            raise
    
    async def search_issues(
        self,
        jql: Optional[str] = None,
        project_key: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        max_results: int = 50,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for JIRA issues"""
        try:
            # In a real implementation, this would make actual JIRA API calls
            # For now, we'll simulate the operation
            
            # Build JQL query
            if not jql:
                jql_parts = []
                if project_key:
                    jql_parts.append(f"project = {project_key}")
                if assignee:
                    jql_parts.append(f"assignee = {assignee}")
                if status:
                    jql_parts.append(f"status = {status}")
                jql = " AND ".join(jql_parts) if jql_parts else "ORDER BY created DESC"
            
            self.logger.info(
                "JIRA issues searched",
                jql=jql,
                max_results=max_results,
                user_id=user_id
            )
            
            # Simulate search results
            issues = []
            for i in range(min(5, max_results)):  # Simulate 5 results
                issues.append({
                    "key": f"PROJ-{1000 + i}",
                    "summary": f"Sample issue {i + 1}",
                    "status": "To Do",
                    "assignee": "user@example.com",
                    "priority": "Medium",
                    "created": "2024-01-01T00:00:00.000Z"
                })
            
            return {
                "jql": jql,
                "total": len(issues),
                "issues": issues,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to search JIRA issues: {e}")
            raise
    
    async def get_issue(self, issue_key: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get details of a specific JIRA issue"""
        try:
            # In a real implementation, this would make actual JIRA API calls
            # For now, we'll simulate the operation
            
            self.logger.info("JIRA issue retrieved", issue_key=issue_key, user_id=user_id)
            
            # Simulate issue details
            issue_details = {
                "key": issue_key,
                "summary": f"Sample issue: {issue_key}",
                "description": "This is a sample issue description",
                "status": "In Progress",
                "assignee": "user@example.com",
                "reporter": "admin@example.com",
                "priority": "High",
                "labels": ["bug", "urgent"],
                "created": "2024-01-01T00:00:00.000Z",
                "updated": "2024-01-02T00:00:00.000Z"
            }
            
            return {
                "issue": issue_details,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get JIRA issue: {e}, issue_key={issue_key}")
            raise
    
    async def _initialize_jira_connection(self):
        """Initialize JIRA connection"""
        # In a real implementation, this would:
        # 1. Load JIRA credentials from environment variables or config
        # 2. Test the connection
        # 3. Cache connection details
        
        self.jira_url = "https://your-jira-instance.atlassian.net"
        self.username = "your-username"
        self.api_token = "your-api-token"
        
        self.logger.info("JIRA connection initialized", jira_url=self.jira_url)
    
    def _create_jira_prompt(self, message: str, user_id: Optional[str]) -> str:
        """Create enhanced JIRA operation prompt"""
        prompt = f"""
        You are a JIRA integration agent. Please process the following request:
        
        Request: {message}
        
        User ID: {user_id or 'Anonymous'}
        
        Guidelines:
        1. Ensure proper authorization for all operations
        2. Maintain detailed audit trails
        3. Respect project permissions and access controls
        4. Provide clear, actionable responses
        5. Include relevant issue keys, project information, and status updates
        
        Process the request and provide a comprehensive response.
        """
        
        return prompt
    
    async def _validate_request(self, message: str, user_id: Optional[str]):
        """Validate request against governance policies"""
        # Input validation
        if not message or len(message.strip()) == 0:
            raise ValueError("JIRA operation cannot be empty")
        
        if len(message) > 2000:  # Max message length
            raise ValueError("JIRA operation too long")
        
        # Authorization check
        if user_id:
            await self._check_authorization(user_id)
        
        # Content filtering
        await self._filter_content(message)
    
    async def _check_authorization(self, user_id: str):
        """Check user authorization for JIRA operations"""
        # Implementation depends on authorization strategy
        # This could check against user roles, project permissions, etc.
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
