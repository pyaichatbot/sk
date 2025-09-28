"""
Agent Factory - Microsoft Semantic Kernel Agent Creation
======================================================

This module provides a factory for creating Microsoft Semantic Kernel
ChatCompletionAgent instances for use in orchestration patterns.

Features:
- Microsoft SK ChatCompletionAgent creation
- Agent configuration management
- Service discovery integration
- Enterprise-grade error handling
"""

from typing import Dict, List, Any, Optional
import asyncio

from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

from shared.config.settings import MicroserviceSettings
from shared.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

class AgentConfig:
    """Agent configuration model"""
    
    def __init__(
        self,
        name: str,
        description: str,
        instructions: str,
        model_id: str,
        api_key: str,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        capabilities: List[str] = None
    ):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.model_id = model_id
        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.capabilities = capabilities or []

class AgentFactory:
    """
    Factory for creating Microsoft Semantic Kernel ChatCompletionAgent instances
    for orchestration patterns.
    """
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.agent_configs: Dict[str, AgentConfig] = {}
        self.created_agents: Dict[str, ChatCompletionAgent] = {}
        
        logger.info("Agent Factory initialized")
    
    async def initialize(self):
        """Initialize agent configurations"""
        try:
            # Initialize agent configurations
            await self._load_agent_configs()
            
            logger.info(f"Agent Factory initialized with {len(self.agent_configs)} agent configs")
            
        except Exception as e:
            logger.error(f"Failed to initialize Agent Factory: {str(e)}")
            raise
    
    async def _load_agent_configs(self):
        """Load agent configurations"""
        try:
            # RAG Agent Configuration
            self.agent_configs["rag"] = AgentConfig(
                name="RAG Agent",
                description="Document-based question answering agent",
                instructions="""
                You are a RAG (Retrieval-Augmented Generation) agent specialized in answering questions 
                based on document content. Your capabilities include:
                
                - Processing and understanding document content
                - Retrieving relevant information from document collections
                - Providing accurate answers with source citations
                - Handling complex queries that require document analysis
                
                Always provide accurate, well-sourced answers based on the available documents.
                When you cannot find relevant information, clearly state this limitation.
                """,
                model_id=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                api_base=self.settings.openai_api_base,
                temperature=0.3,  # Lower temperature for more factual responses
                max_tokens=2048,
                capabilities=["document_qa", "source_citation", "context_retrieval"]
            )
            
            # Search Agent Configuration
            self.agent_configs["search"] = AgentConfig(
                name="Search Agent",
                description="Web search and information retrieval agent",
                instructions="""
                You are a Search agent specialized in finding and retrieving information from the web.
                Your capabilities include:
                
                - Performing web searches using various search engines
                - Extracting and summarizing web content
                - Validating and filtering search results
                - Providing current, up-to-date information
                
                Always provide accurate, current information with proper source attribution.
                Be critical of information quality and reliability.
                """,
                model_id=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                api_base=self.settings.openai_api_base,
                temperature=0.5,
                max_tokens=2048,
                capabilities=["web_search", "content_extraction", "result_validation"]
            )
            
            # JIRA Agent Configuration
            self.agent_configs["jira"] = AgentConfig(
                name="JIRA Agent",
                description="JIRA project management and issue tracking agent",
                instructions="""
                You are a JIRA agent specialized in project management and issue tracking.
                Your capabilities include:
                
                - Creating, updating, and managing JIRA issues
                - Searching and filtering issues using JQL
                - Managing project workflows and transitions
                - Providing project status and reporting
                
                Always follow proper JIRA workflows and maintain data integrity.
                Ensure proper authorization and audit trails for all operations.
                """,
                model_id=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                api_base=self.settings.openai_api_base,
                temperature=0.4,
                max_tokens=2048,
                capabilities=["jira_integration", "issue_management", "project_tracking", "reporting"],
            )
            
            # LLM Agent Configuration
            self.agent_configs["llm"] = AgentConfig(
                name="LLM Agent",
                description="General-purpose language model agent",
                instructions="""
                You are a general-purpose LLM agent capable of various natural language tasks.
                Your capabilities include:
                
                - Text generation and completion
                - Language translation and transformation
                - Content summarization and analysis
                - Creative writing and problem-solving
                
                Provide helpful, accurate, and contextually appropriate responses.
                Be creative when appropriate while maintaining factual accuracy.
                """,
                model_id=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                api_base=self.settings.openai_api_base,
                temperature=0.7,
                max_tokens=4096,
                capabilities=["text_generation", "translation", "summarization", "analysis"]
            )
            
            # Orchestrator Agent Configuration
            self.agent_configs["orchestrator"] = AgentConfig(
                name="Orchestrator Agent",
                description="Multi-agent coordination and workflow management agent",
                instructions="""
                You are an Orchestrator agent responsible for coordinating multiple specialized agents.
                Your capabilities include:
                
                - Analyzing complex tasks and determining optimal agent sequences
                - Coordinating multi-agent workflows
                - Synthesizing results from multiple agents
                - Managing conversation context and session state
                
                Always consider the strengths and capabilities of each agent when making decisions.
                Provide clear, actionable coordination instructions.
                """,
                model_id=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                api_base=self.settings.openai_api_base,
                temperature=0.6,
                max_tokens=4096,
                capabilities=["workflow_coordination", "agent_management", "result_synthesis"]
            )
            
            logger.info(f"Loaded {len(self.agent_configs)} agent configurations")
            
        except Exception as e:
            logger.error(f"Failed to load agent configurations: {str(e)}")
            raise
    
    async def create_agent(self, agent_name: str, config: AgentConfig) -> ChatCompletionAgent:
        """Create a Microsoft SK ChatCompletionAgent instance"""
        try:
            if agent_name in self.created_agents:
                return self.created_agents[agent_name]
            
            logger.info(f"Creating agent: {agent_name}")
            
            # Create kernel
            kernel = Kernel()
            
            # Create chat completion service
            chat_service = OpenAIChatCompletion(
                model_id=config.model_id,
                api_key=config.api_key,
                api_base=config.api_base,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            
            # Add service to kernel
            kernel.add_service(chat_service)
            
            # Create ChatCompletionAgent
            agent = ChatCompletionAgent(
                kernel=kernel,
                name=config.name,
                description=config.description,
                instructions=config.instructions
            )
            
            # Store created agent
            self.created_agents[agent_name] = agent
            
            logger.info(f"Successfully created agent: {agent_name}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name}: {str(e)}")
            raise
    
    async def get_agent_configs(self) -> Dict[str, AgentConfig]:
        """Get all agent configurations"""
        return self.agent_configs.copy()
    
    async def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get specific agent configuration"""
        return self.agent_configs.get(agent_name)
    
    async def create_all_agents(self) -> Dict[str, ChatCompletionAgent]:
        """Create all configured agents"""
        try:
            agents = {}
            
            for agent_name, config in self.agent_configs.items():
                agent = await self.create_agent(agent_name, config)
                agents[agent_name] = agent
            
            logger.info(f"Created {len(agents)} agents")
            return agents
            
        except Exception as e:
            logger.error(f"Failed to create all agents: {str(e)}")
            raise
    
    async def get_agent_info(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get agent information"""
        config = self.agent_configs.get(agent_name)
        if not config:
            return None
        
        return {
            "name": config.name,
            "description": config.description,
            "capabilities": config.capabilities,
            "model_id": config.model_id,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "status": "active" if agent_name in self.created_agents else "inactive"
        }
    
    async def get_all_agents_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information for all agents"""
        agents_info = {}
        
        for agent_name in self.agent_configs.keys():
            info = await self.get_agent_info(agent_name)
            if info:
                agents_info[agent_name] = info
        
        return agents_info
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on agent factory"""
        try:
            health_status = {
                "status": "healthy",
                "total_configs": len(self.agent_configs),
                "created_agents": len(self.created_agents),
                "agents": {}
            }
            
            # Check each agent
            for agent_name, config in self.agent_configs.items():
                agent_status = {
                    "name": config.name,
                    "status": "active" if agent_name in self.created_agents else "inactive",
                    "capabilities": config.capabilities
                }
                health_status["agents"][agent_name] = agent_status
            
            return health_status
            
        except Exception as e:
            logger.error(f"Agent factory health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup agent factory resources"""
        try:
            # Clear created agents
            self.created_agents.clear()
            
            logger.info("Agent Factory cleanup completed")
            
        except Exception as e:
            logger.error(f"Failed to cleanup Agent Factory: {str(e)}")
