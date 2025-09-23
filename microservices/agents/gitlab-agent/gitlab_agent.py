"""
GitLab Agent for Semantic Kernel
Based on Microsoft Semantic Kernel agent template approach
"""

import os
import yaml
from typing import AsyncIterator, List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from semantic_kernel.contents import ChatMessageContent, AuthorRole
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel import Kernel
from semantic_kernel.functions import KernelArguments
from semantic_kernel.prompt_template import PromptTemplateConfig

from shared.models import AgentCapabilities, AgentResponse
from shared.infrastructure.observability.logging import get_logger
from shared.infrastructure.ai_services.service_factory import AIServiceFactory
from shared.config.settings import MicroserviceSettings
from gitlab_plugin import GitLabPlugin, GitLabSettings


logger = get_logger(__name__)


class GitLabAgent:
    """GitLab agent with project management and issue tracking capabilities"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        
        # Load YAML template configuration
        self._load_yaml_template()
        
        # GitLab settings
        self.gitlab_settings = GitLabSettings(
            gitlab_url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            access_token=os.getenv("GITLAB_ACCESS_TOKEN", ""),
            api_version="v4"
        )
        
        self.agent_id = "gitlab-agent-001"
        self.capabilities = AgentCapabilities(
            agent_name="GitLabAgent",
            capabilities=["gitlab_integration", "project_management", "issue_tracking", "merge_request_management", "repository_operations"],
            input_formats=["text", "json"],
            output_formats=["text", "json"],
            max_input_size=10000,
            rate_limit=50,
            timeout=30
        )
        self._initialized = False
        self.kernel: Optional[Kernel] = None
        self._agent: Optional[ChatCompletionAgent] = None
        self.logger = get_logger(f"agent.{self.name}")
        self._start_time = datetime.utcnow()
        
        self.logger.info(
            "GitLab Agent initialized",
            agent_name=self.name,
            agent_id=self.agent_id,
            capabilities=self.capabilities.capabilities
        )
    
    def _load_yaml_template(self):
        """Load YAML template configuration"""
        try:
            # Get the directory of the current file
            current_dir = Path(__file__).parent
            yaml_path = current_dir / "GitLabAgent.yaml"
            
            # Read the YAML file
            with open(yaml_path, "r", encoding="utf-8") as file:
                yaml_content = file.read()
            
            # Parse the YAML content
            data = yaml.safe_load(yaml_content)
            
            # Create PromptTemplateConfig from YAML data
            self.prompt_template_config = PromptTemplateConfig(**data)
            
            # Extract name and description from template config
            self.name = self.prompt_template_config.name
            self.description = self.prompt_template_config.description
            
            self.logger.info(f"Loaded YAML template for {self.name}")
            
        except Exception as e:
            self.logger.error(f"Failed to load YAML template: {e}")
            # Fallback to default values
            self.name = "GitLabAgent"
            self.description = "A GitLab agent for project management, issue tracking, and repository operations"
            self.prompt_template_config = None
    
    async def initialize(self):
        """Initialize the agent with kernel and services"""
        if self._initialized:
            return
        
        try:
            # Create kernel
            self.kernel = await AIServiceFactory.create_kernel()
            
            # Add GitLab plugin to kernel
            gitlab_plugin = GitLabPlugin(self.gitlab_settings)
            self.kernel.add_plugin(gitlab_plugin, "GitLabPlugin")
            
            # Create ChatCompletion agent with YAML template configuration
            if self.prompt_template_config:
                self._agent = ChatCompletionAgent(
                    kernel=self.kernel,
                    prompt_template_config=self.prompt_template_config
                )
            else:
                # Fallback to manual configuration if YAML loading failed
                self._agent = ChatCompletionAgent(
                    kernel=self.kernel,
                    name=self.name,
                    instructions="You are a GitLab agent for project management and issue tracking.",
                    description=self.description
                )
            
            self._initialized = True
            
            self.logger.info(
                "GitLab Agent initialization complete",
                agent_name=self.name
            )
            
        except Exception as e:
            self.logger.error(f"GitLab Agent initialization failed: {e}")
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
            self.logger.info("GitLab Agent cleanup completed")
        except Exception as e:
            self.logger.error(f"GitLab Agent cleanup failed: {e}")
    
    async def invoke(
        self,
        message: str,
        thread: Optional[ChatHistoryAgentThread] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs
    ) -> AgentResponse | AsyncIterator[AgentResponse]:
        """
        Invokes the GitLab agent to process a message.
        """
        self.logger.info(
            "Invoking GitLab Agent",
            message=message,
            user_id=user_id,
            session_id=session_id,
            stream=stream
        )
        
        if not self._initialized or not self._agent:
            self.logger.error("GitLab Agent not initialized")
            raise Exception("GitLab Agent not initialized")
        
        start_time = datetime.utcnow()
        
        try:
            # Create kernel arguments with current time and GitLab URL
            kernel_arguments = KernelArguments(
                now=datetime.utcnow().isoformat(),
                gitlab_url=self.gitlab_settings.gitlab_url
            )
            
            # Add any additional arguments from kwargs
            for key, value in kwargs.items():
                kernel_arguments[key] = value
            
            # Create message content
            message_content = ChatMessageContent(
                role=AuthorRole.USER,
                content=message
            )
            
            if stream:
                # Stream response
                async def response_generator():
                    async for response in self._agent.invoke(
                        message_content,
                        thread=thread,
                        arguments=kernel_arguments
                    ):
                        yield AgentResponse(
                            content=response.content,
                            agent_id=self.agent_id,
                            agent_name=self.name,
                            processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                            tokens_used=len(message.split()) + len(response.content.split()),
                            metadata={
                                "gitlab_response": True,
                                "streaming": True,
                                "thread_id": str(thread.id) if thread else None
                            }
                        )
                
                return response_generator()
            else:
                # Single response
                response = await self._agent.get_response(
                    message_content,
                    thread=thread,
                    arguments=kernel_arguments
                )
                
                return AgentResponse(
                    content=response.content,
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    tokens_used=len(message.split()) + len(response.content.split()),
                    metadata={
                        "gitlab_response": True,
                        "thread_id": str(thread.id) if thread else None
                    }
                )
                
        except Exception as e:
            self.logger.error(f"GitLab Agent invocation failed: {e}")
            raise
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get agent health status"""
        return {
            "status": "healthy",
            "agent_name": self.name,
            "agent_id": self.agent_id,
            "uptime": (datetime.utcnow() - self._start_time).total_seconds(),
            "gitlab_url": self.gitlab_settings.gitlab_url,
            "initialized": self._initialized
        }
    
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current GitLab user information"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            user = await plugin.get_current_user()
            return {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "web_url": user.web_url
            }
        except Exception as e:
            self.logger.error(f"Failed to get current user: {e}")
            raise
    
    async def get_project_info(self, project_id: str) -> Dict[str, Any]:
        """Get project information"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            project = await plugin.get_project(project_id)
            return {
                "id": project.id,
                "name": project.name,
                "path": project.path,
                "description": project.description,
                "web_url": project.web_url,
                "created_at": project.created_at,
                "last_activity_at": project.last_activity_at
            }
        except Exception as e:
            self.logger.error(f"Failed to get project info: {e}")
            raise
    
    async def get_project_issues(
        self, 
        project_id: str, 
        state: str = "opened",
        labels: Optional[str] = None,
        assignee_id: Optional[int] = None,
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """Get project issues"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            issues = await plugin.get_project_issues(
                project_id, state, labels, assignee_id, per_page
            )
            return [
                {
                    "id": issue.id,
                    "title": issue.title,
                    "description": issue.description,
                    "state": issue.state,
                    "author": issue.author,
                    "assignee": issue.assignee,
                    "created_at": issue.created_at,
                    "updated_at": issue.updated_at,
                    "web_url": issue.web_url,
                    "labels": issue.labels
                }
                for issue in issues
            ]
        except Exception as e:
            self.logger.error(f"Failed to get project issues: {e}")
            raise
    
    async def get_project_merge_requests(
        self,
        project_id: str,
        state: str = "opened",
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """Get project merge requests"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            merge_requests = await plugin.get_project_merge_requests(
                project_id, state, per_page
            )
            return [
                {
                    "id": mr.id,
                    "title": mr.title,
                    "description": mr.description,
                    "state": mr.state,
                    "author": mr.author,
                    "assignee": mr.assignee,
                    "created_at": mr.created_at,
                    "updated_at": mr.updated_at,
                    "web_url": mr.web_url,
                    "source_branch": mr.source_branch,
                    "target_branch": mr.target_branch
                }
                for mr in merge_requests
            ]
        except Exception as e:
            self.logger.error(f"Failed to get project merge requests: {e}")
            raise
    
    async def get_project_commits(
        self,
        project_id: str,
        ref_name: str = "main",
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """Get project commits"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            commits = await plugin.get_project_commits(project_id, ref_name, per_page)
            return [
                {
                    "id": commit.id,
                    "short_id": commit.short_id,
                    "title": commit.title,
                    "message": commit.message,
                    "author_name": commit.author_name,
                    "author_email": commit.author_email,
                    "authored_date": commit.authored_date,
                    "committer_name": commit.committer_name,
                    "committer_email": commit.committer_email,
                    "committed_date": commit.committed_date,
                    "created_at": commit.created_at,
                    "web_url": commit.web_url
                }
                for commit in commits
            ]
        except Exception as e:
            self.logger.error(f"Failed to get project commits: {e}")
            raise
    
    async def get_project_branches(
        self,
        project_id: str,
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """Get project branches"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            branches = await plugin.get_project_branches(project_id, per_page)
            return [
                {
                    "name": branch.name,
                    "merged": branch.merged,
                    "protected": branch.protected,
                    "default": branch.default,
                    "developers_can_push": branch.developers_can_push,
                    "developers_can_merge": branch.developers_can_merge,
                    "can_push": branch.can_push,
                    "web_url": branch.web_url,
                    "commit": branch.commit
                }
                for branch in branches
            ]
        except Exception as e:
            self.logger.error(f"Failed to get project branches: {e}")
            raise
    
    async def get_project_tags(
        self,
        project_id: str,
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """Get project tags"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            tags = await plugin.get_project_tags(project_id, per_page)
            return [
                {
                    "name": tag.name,
                    "message": tag.message,
                    "commit": tag.commit,
                    "release": tag.release,
                    "web_url": tag.web_url
                }
                for tag in tags
            ]
        except Exception as e:
            self.logger.error(f"Failed to get project tags: {e}")
            raise
    
    async def get_project_pipelines(
        self,
        project_id: str,
        ref: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """Get project pipelines"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            pipelines = await plugin.get_project_pipelines(project_id, ref, status, per_page)
            return [
                {
                    "id": pipeline.id,
                    "status": pipeline.status,
                    "ref": pipeline.ref,
                    "sha": pipeline.sha,
                    "web_url": pipeline.web_url,
                    "created_at": pipeline.created_at,
                    "updated_at": pipeline.updated_at,
                    "started_at": pipeline.started_at,
                    "finished_at": pipeline.finished_at,
                    "duration": pipeline.duration
                }
                for pipeline in pipelines
            ]
        except Exception as e:
            self.logger.error(f"Failed to get project pipelines: {e}")
            raise
    
    async def get_pipeline(
        self,
        project_id: str,
        pipeline_id: int
    ) -> Dict[str, Any]:
        """Get specific pipeline details"""
        try:
            plugin = GitLabPlugin(self.gitlab_settings)
            pipeline = await plugin.get_pipeline(project_id, pipeline_id)
            return {
                "id": pipeline.id,
                "status": pipeline.status,
                "ref": pipeline.ref,
                "sha": pipeline.sha,
                "web_url": pipeline.web_url,
                "created_at": pipeline.created_at,
                "updated_at": pipeline.updated_at,
                "started_at": pipeline.started_at,
                "finished_at": pipeline.finished_at,
                "duration": pipeline.duration
            }
        except Exception as e:
            self.logger.error(f"Failed to get pipeline: {e}")
            raise