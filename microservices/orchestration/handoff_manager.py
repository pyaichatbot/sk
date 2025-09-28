# ============================================================================
# microservices/orchestration/handoff_manager.py
# ============================================================================
"""
Enterprise Handoff Orchestration Manager

This module implements enterprise-grade handoff orchestration with rich context passing,
chain management, error handling, and monitoring capabilities.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncIterator
from enum import Enum

# Microsoft Semantic Kernel
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.contents import ChatMessageContent, AuthorRole

# Shared models and infrastructure
from shared.models.handoff import (
    HandoffContext, HandoffChain, HandoffResult, HandoffStatus, HandoffMetrics
)
from shared.models.orchestration import OrchestrationRequest, OrchestrationResponse, OrchestrationStep
from shared.models.agent import AgentRequest, AgentResponse
from shared.infrastructure.observability.logging import get_logger
from shared.config.settings import MicroserviceSettings

# Local imports
from agent_factory import AgentFactory
from intermediate_messaging_endpoints import emit_agent_call_event, track_agent_call
from shared.models.intermediate_messaging import AgentCallEventType, AgentCallStatus

logger = get_logger(__name__)

class EnterpriseHandoffManager:
    """
    Enterprise-grade handoff orchestration manager with rich context passing,
    chain management, error handling, and monitoring capabilities.
    """
    
    def __init__(
        self,
        agent_factory: AgentFactory,
        settings: MicroserviceSettings
    ):
        self.agent_factory = agent_factory
        self.settings = settings
        self.handoff_chains: Dict[str, HandoffChain] = {}
        self.active_handoffs: Dict[str, HandoffContext] = {}
        self.handoff_metrics: Dict[str, HandoffMetrics] = {}
        
        # Initialize default handoff chains
        self._initialize_default_chains()
        
        logger.info("Enterprise Handoff Manager initialized")
    
    def _initialize_default_chains(self):
        """Initialize default handoff chains"""
        try:
            # Search → RAG → LLM chain
            search_rag_llm_chain = HandoffChain(
                chain_id="search_rag_llm",
                name="Search-RAG-LLM Chain",
                description="Search for information, analyze with RAG, generate response with LLM",
                agents=["search-agent", "rag-agent", "llm-agent"],
                handoff_rules={
                    "search-agent": {
                        "next_agents": ["rag-agent"],
                        "context_passing": True,
                        "fallback_agents": ["llm-agent"]
                    },
                    "rag-agent": {
                        "next_agents": ["llm-agent"],
                        "context_passing": True,
                        "fallback_agents": []
                    },
                    "llm-agent": {
                        "next_agents": [],
                        "context_passing": False,
                        "fallback_agents": []
                    }
                },
                fallback_agents={
                    "search-agent": ["llm-agent"],
                    "rag-agent": [],
                    "llm-agent": []
                },
                priority=5,
                timeout=300,
                max_retries=3
            )
            
            # RAG → LLM chain
            rag_llm_chain = HandoffChain(
                chain_id="rag_llm",
                name="RAG-LLM Chain",
                description="Analyze documents with RAG, generate response with LLM",
                agents=["rag-agent", "llm-agent"],
                handoff_rules={
                    "rag-agent": {
                        "next_agents": ["llm-agent"],
                        "context_passing": True,
                        "fallback_agents": []
                    },
                    "llm-agent": {
                        "next_agents": [],
                        "context_passing": False,
                        "fallback_agents": []
                    }
                },
                fallback_agents={
                    "rag-agent": [],
                    "llm-agent": []
                },
                priority=7,
                timeout=180,
                max_retries=2
            )
            
            # Search → LLM chain
            search_llm_chain = HandoffChain(
                chain_id="search_llm",
                name="Search-LLM Chain",
                description="Search for information, generate response with LLM",
                agents=["search-agent", "llm-agent"],
                handoff_rules={
                    "search-agent": {
                        "next_agents": ["llm-agent"],
                        "context_passing": True,
                        "fallback_agents": []
                    },
                    "llm-agent": {
                        "next_agents": [],
                        "context_passing": False,
                        "fallback_agents": []
                    }
                },
                fallback_agents={
                    "search-agent": [],
                    "llm-agent": []
                },
                priority=6,
                timeout=120,
                max_retries=2
            )
            
            # Store chains
            self.handoff_chains["search_rag_llm"] = search_rag_llm_chain
            self.handoff_chains["rag_llm"] = rag_llm_chain
            self.handoff_chains["search_llm"] = search_llm_chain
            
            logger.info(f"Initialized {len(self.handoff_chains)} default handoff chains")
            
        except Exception as e:
            logger.error(f"Failed to initialize default handoff chains: {e}")
            raise
    
    async def execute_handoff_chain(
        self,
        request: OrchestrationRequest,
        chain_id: Optional[str] = None
    ) -> HandoffResult:
        """
        Execute handoff chain with context passing and error handling
        """
        start_time = datetime.utcnow()
        handoff_id = str(uuid.uuid4())
        
        try:
            # Determine chain to use
            if chain_id is None:
                chain_id = self._select_optimal_chain(request)
            
            if chain_id not in self.handoff_chains:
                raise ValueError(f"Handoff chain not found: {chain_id}")
            
            chain = self.handoff_chains[chain_id]
            
            # Create handoff context
            context = HandoffContext(
                chain_id=chain_id,
                current_agent=chain.agents[0],
                next_agents=chain.agents[1:],
                session_id=request.session_id,
                user_id=request.user_id,
                request_id=str(request.id),
                total_steps=len(chain.agents)
            )
            
            # Store active handoff
            self.active_handoffs[handoff_id] = context
            
            # Execute handoff chain
            result = await self._execute_chain(context, request)
            
            # Update metrics
            await self._update_handoff_metrics(chain_id, result)
            
            logger.info(
                "Handoff chain executed successfully",
                handoff_id=handoff_id,
                chain_id=chain_id,
                success=result.success,
                duration_ms=result.duration_ms
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Handoff chain execution failed: {e}")
            
            # Create failure result
            result = HandoffResult(
                chain_id=chain_id or "unknown",
                session_id=request.session_id,
                user_id=request.user_id,
                success=False,
                start_time=start_time,
                end_time=datetime.utcnow(),
                error=str(e)
            )
            
            return result
            
        finally:
            # Clean up active handoff
            if handoff_id in self.active_handoffs:
                del self.active_handoffs[handoff_id]
    
    async def _execute_chain(
        self,
        context: HandoffContext,
        request: OrchestrationRequest
    ) -> HandoffResult:
        """Execute handoff chain with context passing"""
        
        steps_completed = 0
        agents_used = []
        handoff_points = []
        
        try:
            # Execute each agent in the chain
            for step_number, agent_id in enumerate(context.chain_id.split('_'), 1):
                # Update context
                context.current_agent = agent_id
                context.step_number = step_number
                context.status = HandoffStatus.IN_PROGRESS
                
                # Execute agent
                agent_result = await self._execute_agent_with_context(
                    agent_id, context, request
                )
                
                if not agent_result.success:
                    # Handle agent failure
                    context = await self._handle_agent_failure(
                        agent_id, context, agent_result.error
                    )
                    
                    if context is None:
                        # No fallback available
                        break
                
                # Update context with agent result
                context.previous_output = agent_result
                context.previous_agent = agent_id
                context.status = HandoffStatus.COMPLETED
                
                steps_completed += 1
                agents_used.append(agent_id)
                handoff_points.append(agent_id)
                
                # Emit handoff event
                await emit_agent_call_event(
                    event_type=AgentCallEventType.ORCHESTRATION_STEP_END,
                    agent_name=agent_id,
                    session_id=context.session_id,
                    user_id=context.user_id,
                    correlation_id=context.request_id,
                    input_message=request.message,
                    output_message=agent_result.content if agent_result else "No output",
                    status=AgentCallStatus.COMPLETED,
                    metadata={
                        "handoff_step": step_number,
                        "context_passed": True,
                        "chain_id": context.chain_id
                    }
                )
            
            # Create result
            result = HandoffResult(
                chain_id=context.chain_id,
                session_id=context.session_id,
                user_id=context.user_id,
                success=steps_completed > 0,
                final_output=context.previous_output,
                steps_completed=steps_completed,
                total_steps=context.total_steps,
                start_time=context.created_at,
                end_time=datetime.utcnow(),
                context_passed=True,
                agents_used=agents_used,
                handoff_points=handoff_points,
                metadata={
                    "chain_config": self.handoff_chains[context.chain_id].dict(),
                    "context_data": context.context_data
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Chain execution failed: {e}")
            
            return HandoffResult(
                chain_id=context.chain_id,
                session_id=context.session_id,
                user_id=context.user_id,
                success=False,
                steps_completed=steps_completed,
                total_steps=context.total_steps,
                start_time=context.created_at,
                end_time=datetime.utcnow(),
                error=str(e),
                failed_agent=context.current_agent,
                agents_used=agents_used,
                handoff_points=handoff_points
            )
    
    async def _execute_agent_with_context(
        self,
        agent_id: str,
        context: HandoffContext,
        request: OrchestrationRequest
    ) -> AgentResponse:
        """Execute agent with rich context passing"""
        
        try:
            # Get agent
            agent = await self.agent_factory.get_agent(agent_id)
            if not agent:
                raise ValueError(f"Agent not found: {agent_id}")
            
            # Prepare context-rich request
            context_message = self._build_context_message(context, request)
            
            # Create agent request with context
            agent_request = AgentRequest(
                message=context_message,
                user_id=request.user_id,
                session_id=request.session_id,
                context=context.context_data,
                metadata={
                    "handoff_context": context.dict(),
                    "previous_agent": context.previous_agent,
                    "chain_id": context.chain_id,
                    "step_number": context.step_number
                }
            )
            
            # Execute agent
            agent_response = await agent.process_request(agent_request)
            
            # Update context with agent response
            context.context_data.update({
                f"{agent_id}_output": agent_response.dict(),
                f"{agent_id}_timestamp": datetime.utcnow().isoformat()
            })
            
            return agent_response
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise
    
    def _build_context_message(
        self,
        context: HandoffContext,
        request: OrchestrationRequest
    ) -> str:
        """Build context-rich message for agent"""
        
        base_message = request.message
        
        if context.previous_output:
            # Add previous agent output to context
            context_message = f"""
Previous agent ({context.previous_agent}) output:
{context.previous_output.content}

Current task:
{base_message}

Please continue the workflow using the previous agent's output as context.
"""
        else:
            # First agent in chain
            context_message = base_message
        
        return context_message.strip()
    
    async def _handle_agent_failure(
        self,
        failed_agent: str,
        context: HandoffContext,
        error: str
    ) -> Optional[HandoffContext]:
        """Handle agent failure with fallback logic"""
        
        try:
            chain = self.handoff_chains[context.chain_id]
            fallback_agents = chain.fallback_agents.get(failed_agent, [])
            
            if not fallback_agents:
                logger.warning(f"No fallback agents for failed agent: {failed_agent}")
                return None
            
            # Try fallback agents
            for fallback_agent in fallback_agents:
                try:
                    logger.info(f"Trying fallback agent: {fallback_agent}")
                    context.current_agent = fallback_agent
                    context.retry_count += 1
                    return context
                    
                except Exception as e:
                    logger.warning(f"Fallback agent {fallback_agent} also failed: {e}")
                    continue
            
            # All fallbacks failed
            logger.error(f"All fallback agents failed for: {failed_agent}")
            return None
            
        except Exception as e:
            logger.error(f"Error handling agent failure: {e}")
            return None
    
    def _select_optimal_chain(self, request: OrchestrationRequest) -> str:
        """Select optimal handoff chain based on request"""
        
        message_lower = request.message.lower()
        
        # Simple chain selection logic
        if "search" in message_lower and "analyze" in message_lower:
            return "search_rag_llm"
        elif "analyze" in message_lower or "rag" in message_lower:
            return "rag_llm"
        elif "search" in message_lower:
            return "search_llm"
        else:
            # Default to search-rag-llm chain
            return "search_rag_llm"
    
    async def _update_handoff_metrics(
        self,
        chain_id: str,
        result: HandoffResult
    ):
        """Update handoff metrics"""
        
        try:
            if chain_id not in self.handoff_metrics:
                self.handoff_metrics[chain_id] = HandoffMetrics(
                    chain_id=chain_id,
                    time_window="hourly"
                )
            
            metrics = self.handoff_metrics[chain_id]
            metrics.total_executions += 1
            
            if result.success:
                metrics.successful_executions += 1
            else:
                metrics.failed_executions += 1
            
            # Update performance metrics
            if result.duration_ms:
                if metrics.average_duration_ms == 0:
                    metrics.average_duration_ms = result.duration_ms
                else:
                    metrics.average_duration_ms = (
                        metrics.average_duration_ms + result.duration_ms
                    ) / 2
            
            # Update agent usage
            for agent in result.agents_used:
                if agent not in metrics.agent_usage:
                    metrics.agent_usage[agent] = 0
                metrics.agent_usage[agent] += 1
            
            # Update context passing metrics
            if result.context_passed:
                metrics.context_passing_rate = (
                    metrics.context_passing_rate + 1.0
                ) / 2
            
        except Exception as e:
            logger.error(f"Failed to update handoff metrics: {e}")
    
    async def get_handoff_metrics(self, chain_id: str) -> Optional[HandoffMetrics]:
        """Get handoff metrics for a chain"""
        return self.handoff_metrics.get(chain_id)
    
    async def get_active_handoffs(self) -> List[HandoffContext]:
        """Get active handoff contexts"""
        return list(self.active_handoffs.values())
    
    async def cancel_handoff(self, handoff_id: str) -> bool:
        """Cancel an active handoff"""
        if handoff_id in self.active_handoffs:
            context = self.active_handoffs[handoff_id]
            context.status = HandoffStatus.CANCELLED
            del self.active_handoffs[handoff_id]
            return True
        return False
