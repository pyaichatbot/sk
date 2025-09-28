# ============================================================================
# microservices/orchestration/group_chat_manager.py
# ============================================================================
"""
Enterprise Group Chat Orchestration Manager

This module implements enterprise-grade group chat orchestration with multi-agent
collaboration, consensus building, intelligent moderation, and real-time discussion.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncIterator
from enum import Enum

# Microsoft Semantic Kernel
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.contents import ChatMessageContent, AuthorRole

# Shared models and infrastructure
from shared.models.group_chat import (
    GroupChatSession, ChatMessage, ConsensusResult, ModerationResult,
    ChatMessageRole, ChatMessageType, ConsensusStatus, GroupChatMetrics
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

class EnterpriseGroupChatManager:
    """
    Enterprise-grade group chat orchestration manager with multi-agent collaboration,
    consensus building, intelligent moderation, and real-time discussion capabilities.
    """
    
    def __init__(
        self,
        agent_factory: AgentFactory,
        settings: MicroserviceSettings
    ):
        self.agent_factory = agent_factory
        self.settings = settings
        self.active_sessions: Dict[str, GroupChatSession] = {}
        self.session_metrics: Dict[str, GroupChatMetrics] = {}
        
        # Moderation settings
        self.moderation_enabled = True
        self.auto_moderation = True
        self.consensus_timeout_minutes = 30
        
        logger.info("Enterprise Group Chat Manager initialized")
    
    async def start_collaboration(
        self,
        request: OrchestrationRequest,
        participants: List[str],
        moderator: Optional[str] = None,
        discussion_goals: Optional[List[str]] = None
    ) -> GroupChatSession:
        """
        Start group chat collaboration session
        """
        try:
            session_id = f"group_chat_{uuid.uuid4().hex[:8]}"
            
            # Create group chat session
            session = GroupChatSession(
                session_id=session_id,
                user_id=request.user_id,
                request_id=str(request.id),
                participants=participants,
                moderator=moderator,
                discussion_goals=discussion_goals or [],
                current_topic=request.message,
                is_active=True,
                is_moderated=moderator is not None
            )
            
            # Store active session
            self.active_sessions[session_id] = session
            
            # Emit session start event
            await emit_agent_call_event(
                event_type=AgentCallEventType.ORCHESTRATION_STEP_START,
                agent_name="group_chat_manager",
                session_id=session_id,
                user_id=request.user_id,
                correlation_id=str(request.id),
                input_message=request.message,
                output_message=f"Started group chat with {len(participants)} participants",
                status=AgentCallStatus.RUNNING,
                metadata={
                    "participants": participants,
                    "moderator": moderator,
                    "goals": discussion_goals
                }
            )
            
            logger.info(
                "Group chat session started",
                session_id=session_id,
                participants=participants,
                moderator=moderator
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to start group chat session: {e}")
            raise
    
    async def facilitate_discussion(
        self,
        session: GroupChatSession,
        message: str,
        sender_id: Optional[str] = None
    ) -> List[ChatMessage]:
        """
        Facilitate multi-agent discussion in group chat
        """
        try:
            messages = []
            
            # Determine discussion flow
            if session.is_moderated and session.moderator:
                # Moderated discussion
                messages = await self._facilitate_moderated_discussion(
                    session, message, sender_id
                )
            else:
                # Open discussion
                messages = await self._facilitate_open_discussion(
                    session, message, sender_id
                )
            
            # Update session
            session.conversation_history.extend(messages)
            session.updated_at = datetime.utcnow()
            
            # Check for consensus
            if len(messages) > 0:
                await self._check_consensus(session)
            
            # Emit discussion event
            await emit_agent_call_event(
                event_type=AgentCallEventType.ORCHESTRATION_STEP_END,
                agent_name="group_chat_manager",
                session_id=session.session_id,
                user_id=session.user_id,
                correlation_id=session.request_id,
                input_message=message,
                output_message=f"Facilitated discussion with {len(messages)} messages",
                status=AgentCallStatus.COMPLETED,
                metadata={
                    "message_count": len(messages),
                    "participants": session.participants,
                    "consensus_reached": session.consensus_reached
                }
            )
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to facilitate discussion: {e}")
            raise
    
    async def _facilitate_moderated_discussion(
        self,
        session: GroupChatSession,
        message: str,
        sender_id: Optional[str] = None
    ) -> List[ChatMessage]:
        """Facilitate moderated discussion"""
        
        messages = []
        
        # Moderator introduces topic
        if not session.current_speaker:
            moderator_message = ChatMessage(
                content=f"Let's discuss: {message}",
                role=ChatMessageRole.MODERATOR,
                message_type=ChatMessageType.MODERATION,
                sender_id=session.moderator,
                sender_name="Moderator",
                session_id=session.session_id,
                context={"topic": message, "moderation": True}
            )
            messages.append(moderator_message)
            session.current_speaker = session.moderator
        
        # Participants respond
        for participant in session.participants:
            if participant == session.moderator:
                continue
            
            try:
                # Get participant agent
                agent = await self.agent_factory.get_agent(participant)
                if not agent:
                    continue
                
                # Create discussion context
                discussion_context = self._build_discussion_context(session, message)
                
                # Create agent request
                agent_request = AgentRequest(
                    message=discussion_context,
                    user_id=session.user_id,
                    session_id=session.session_id,
                    context={
                        "group_chat": True,
                        "session_id": session.session_id,
                        "participants": session.participants,
                        "moderator": session.moderator,
                        "discussion_goals": session.discussion_goals,
                        "conversation_history": [msg.dict() for msg in session.conversation_history[-5:]]
                    }
                )
                
                # Execute agent
                agent_response = await agent.process_request(agent_request)
                
                # Create chat message
                chat_message = ChatMessage(
                    content=agent_response.content,
                    role=ChatMessageRole.AGENT,
                    message_type=ChatMessageType.MESSAGE,
                    sender_id=participant,
                    sender_name=participant.replace('-', ' ').title(),
                    session_id=session.session_id,
                    context={"agent_response": agent_response.dict()}
                )
                
                messages.append(chat_message)
                
            except Exception as e:
                logger.warning(f"Participant {participant} failed to respond: {e}")
                continue
        
        return messages
    
    async def _facilitate_open_discussion(
        self,
        session: GroupChatSession,
        message: str,
        sender_id: Optional[str] = None
    ) -> List[ChatMessage]:
        """Facilitate open discussion"""
        
        messages = []
        
        # All participants respond
        for participant in session.participants:
            try:
                # Get participant agent
                agent = await self.agent_factory.get_agent(participant)
                if not agent:
                    continue
                
                # Create discussion context
                discussion_context = self._build_discussion_context(session, message)
                
                # Create agent request
                agent_request = AgentRequest(
                    message=discussion_context,
                    user_id=session.user_id,
                    session_id=session.session_id,
                    context={
                        "group_chat": True,
                        "session_id": session.session_id,
                        "participants": session.participants,
                        "discussion_goals": session.discussion_goals,
                        "conversation_history": [msg.dict() for msg in session.conversation_history[-5:]]
                    }
                )
                
                # Execute agent
                agent_response = await agent.process_request(agent_request)
                
                # Create chat message
                chat_message = ChatMessage(
                    content=agent_response.content,
                    role=ChatMessageRole.AGENT,
                    message_type=ChatMessageType.MESSAGE,
                    sender_id=participant,
                    sender_name=participant.replace('-', ' ').title(),
                    session_id=session.session_id,
                    context={"agent_response": agent_response.dict()}
                )
                
                messages.append(chat_message)
                
            except Exception as e:
                logger.warning(f"Participant {participant} failed to respond: {e}")
                continue
        
        return messages
    
    def _build_discussion_context(
        self,
        session: GroupChatSession,
        message: str
    ) -> str:
        """Build discussion context for agents"""
        
        context_parts = [
            f"Group Chat Discussion",
            f"Topic: {message}",
            f"Participants: {', '.join(session.participants)}",
            f"Goals: {', '.join(session.discussion_goals)}"
        ]
        
        if session.conversation_history:
            context_parts.append("\nRecent conversation:")
            for msg in session.conversation_history[-3:]:
                context_parts.append(f"{msg.sender_name}: {msg.content}")
        
        context_parts.append(f"\nPlease contribute to this discussion about: {message}")
        
        return "\n".join(context_parts)
    
    async def _check_consensus(self, session: GroupChatSession):
        """Check if consensus has been reached"""
        
        try:
            # Simple consensus logic based on message patterns
            recent_messages = session.conversation_history[-10:]
            
            # Look for consensus indicators
            consensus_indicators = [
                "agree", "consensus", "unanimous", "all agree",
                "decision", "conclusion", "final answer"
            ]
            
            consensus_count = 0
            for message in recent_messages:
                content_lower = message.content.lower()
                if any(indicator in content_lower for indicator in consensus_indicators):
                    consensus_count += 1
            
            # Check if consensus reached
            if consensus_count >= len(session.participants) // 2:
                session.consensus_reached = True
                session.consensus_status = ConsensusStatus.REACHED
                
                # Create consensus result
                consensus_result = ConsensusResult(
                    session_id=session.session_id,
                    topic=session.current_topic or "Discussion",
                    status=ConsensusStatus.REACHED,
                    consensus_reached=True,
                    consensus_content="Consensus reached through discussion",
                    consensus_confidence=consensus_count / len(session.participants),
                    total_votes=len(session.participants),
                    votes_for=consensus_count,
                    participants=session.participants,
                    discussion_duration_minutes=(
                        datetime.utcnow() - session.created_at
                    ).total_seconds() / 60,
                    message_count=len(session.conversation_history)
                )
                
                session.metadata["consensus_result"] = consensus_result.dict()
                
                logger.info(
                    "Consensus reached in group chat",
                    session_id=session.session_id,
                    consensus_confidence=consensus_result.consensus_confidence
                )
        
        except Exception as e:
            logger.error(f"Failed to check consensus: {e}")
    
    async def reach_consensus(
        self,
        session: GroupChatSession,
        topic: str,
        options: Optional[List[str]] = None
    ) -> ConsensusResult:
        """
        Reach consensus on a specific topic
        """
        try:
            # Start voting process
            session.voting_active = True
            session.current_topic = topic
            
            # Create voting message
            voting_message = ChatMessage(
                content=f"Let's vote on: {topic}",
                role=ChatMessageRole.MODERATOR,
                message_type=ChatMessageType.VOTE,
                sender_id=session.moderator or "system",
                sender_name="Moderator",
                session_id=session.session_id,
                context={"voting": True, "topic": topic, "options": options}
            )
            
            session.conversation_history.append(voting_message)
            
            # Collect votes from participants
            votes = {}
            for participant in session.participants:
                try:
                    # Get participant agent
                    agent = await self.agent_factory.get_agent(participant)
                    if not agent:
                        continue
                    
                    # Create voting request
                    voting_context = f"""
Vote on: {topic}
Options: {', '.join(options) if options else 'Yes/No'}
Please provide your vote and reasoning.
"""
                    
                    agent_request = AgentRequest(
                        message=voting_context,
                        user_id=session.user_id,
                        session_id=session.session_id,
                        context={"voting": True, "topic": topic, "options": options}
                    )
                    
                    # Execute agent
                    agent_response = await agent.process_request(agent_request)
                    
                    # Parse vote (simple implementation)
                    vote_content = agent_response.content.lower()
                    if "yes" in vote_content or "agree" in vote_content:
                        votes[participant] = "yes"
                    elif "no" in vote_content or "disagree" in vote_content:
                        votes[participant] = "no"
                    else:
                        votes[participant] = "abstain"
                    
                    # Create vote message
                    vote_message = ChatMessage(
                        content=agent_response.content,
                        role=ChatMessageRole.AGENT,
                        message_type=ChatMessageType.VOTE,
                        sender_id=participant,
                        sender_name=participant.replace('-', ' ').title(),
                        session_id=session.session_id,
                        context={"vote": votes[participant]}
                    )
                    
                    session.conversation_history.append(vote_message)
                    
                except Exception as e:
                    logger.warning(f"Participant {participant} failed to vote: {e}")
                    votes[participant] = "abstain"
            
            # Calculate consensus
            total_votes = len(votes)
            votes_for = sum(1 for v in votes.values() if v == "yes")
            votes_against = sum(1 for v in votes.values() if v == "no")
            abstentions = sum(1 for v in votes.values() if v == "abstain")
            
            consensus_reached = votes_for > votes_against
            consensus_confidence = votes_for / total_votes if total_votes > 0 else 0
            
            # Create consensus result
            consensus_result = ConsensusResult(
                session_id=session.session_id,
                topic=topic,
                status=ConsensusStatus.REACHED if consensus_reached else ConsensusStatus.FAILED,
                consensus_reached=consensus_reached,
                consensus_content=f"Consensus: {votes_for} for, {votes_against} against",
                consensus_confidence=consensus_confidence,
                total_votes=total_votes,
                votes_for=votes_for,
                votes_against=votes_against,
                abstentions=abstentions,
                participants=session.participants,
                consensus_supporters=[p for p, v in votes.items() if v == "yes"],
                consensus_opponents=[p for p, v in votes.items() if v == "no"],
                discussion_duration_minutes=(
                    datetime.utcnow() - session.created_at
                ).total_seconds() / 60,
                message_count=len(session.conversation_history)
            )
            
            # Update session
            session.consensus_reached = consensus_reached
            session.consensus_status = consensus_result.status
            session.voting_results = consensus_result.dict()
            session.voting_active = False
            
            logger.info(
                "Consensus reached",
                session_id=session.session_id,
                consensus_reached=consensus_reached,
                confidence=consensus_confidence
            )
            
            return consensus_result
            
        except Exception as e:
            logger.error(f"Failed to reach consensus: {e}")
            raise
    
    async def moderate_discussion(
        self,
        session: GroupChatSession,
        moderation_type: str = "content"
    ) -> ModerationResult:
        """
        Moderate group chat discussion
        """
        try:
            if not session.is_moderated or not session.moderator:
                raise ValueError("Session is not moderated")
            
            # Analyze recent messages for moderation
            recent_messages = session.conversation_history[-10:]
            moderation_actions = []
            
            for message in recent_messages:
                # Simple moderation logic
                if self._needs_moderation(message):
                    action = await self._apply_moderation(session, message)
                    moderation_actions.append(action)
            
            # Create moderation result
            moderation_result = ModerationResult(
                session_id=session.session_id,
                moderator_id=session.moderator,
                moderation_type=moderation_type,
                action_taken=f"Applied {len(moderation_actions)} moderation actions",
                reason="Content moderation based on discussion analysis",
                severity="low" if len(moderation_actions) < 3 else "medium",
                auto_moderation=True,
                metadata={"actions": moderation_actions}
            )
            
            logger.info(
                "Discussion moderated",
                session_id=session.session_id,
                actions=len(moderation_actions)
            )
            
            return moderation_result
            
        except Exception as e:
            logger.error(f"Failed to moderate discussion: {e}")
            raise
    
    def _needs_moderation(self, message: ChatMessage) -> bool:
        """Check if message needs moderation"""
        
        # Simple moderation logic
        content_lower = message.content.lower()
        
        # Check for inappropriate content
        inappropriate_indicators = [
            "spam", "offensive", "inappropriate", "harassment"
        ]
        
        return any(indicator in content_lower for indicator in inappropriate_indicators)
    
    async def _apply_moderation(
        self,
        session: GroupChatSession,
        message: ChatMessage
    ) -> Dict[str, Any]:
        """Apply moderation action to message"""
        
        # Simple moderation action
        action = {
            "message_id": str(message.id),
            "action": "flagged",
            "reason": "Content flagged for review",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return action
    
    async def get_session_metrics(self, session_id: str) -> Optional[GroupChatMetrics]:
        """Get group chat metrics for a session"""
        return self.session_metrics.get(session_id)
    
    async def get_active_sessions(self) -> List[GroupChatSession]:
        """Get active group chat sessions"""
        return list(self.active_sessions.values())
    
    async def end_session(self, session_id: str) -> bool:
        """End a group chat session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.is_active = False
            session.updated_at = datetime.utcnow()
            del self.active_sessions[session_id]
            return True
        return False
