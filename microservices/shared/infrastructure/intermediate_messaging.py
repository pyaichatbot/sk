# ============================================================================
# microservices/shared/infrastructure/intermediate_messaging.py
# ============================================================================
"""
Enterprise Intermediate Messaging Service
========================================

This module implements the core intermediate messaging service for real-time
agent call visibility in the Semantic Kernel orchestration system.

Key Features:
- Real-time agent call event streaming via WebSocket
- Event-driven architecture for agent execution visibility
- Enterprise-grade error handling and circuit breaker patterns
- Configurable event filtering and rate limiting
- Comprehensive metrics and monitoring
- Production-ready scalability and reliability
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncIterator, Set, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
import weakref

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from shared.models.intermediate_messaging import (
    AgentCallEvent, AgentCallEventType, AgentCallStatus, AgentCallStream,
    WebSocketConnection, IntermediateMessagingConfig, AgentCallMetrics,
    AgentCallEventFilter
)
import logging
from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class CircuitBreakerState(str, Enum):
    """Circuit breaker states for error handling"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service has recovered

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3

@dataclass
class CircuitBreaker:
    """Circuit breaker implementation for error handling"""
    config: CircuitBreakerConfig
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    
    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        return False
    
    def record_success(self):
        """Record successful execution"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN

class EventSubscription:
    """Event subscription for WebSocket connections"""
    
    def __init__(
        self,
        connection_id: str,
        websocket: WebSocket,
        filter_criteria: Optional[AgentCallEventFilter] = None
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.filter_criteria = filter_criteria or AgentCallEventFilter()
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.message_count = 0
        self.error_count = 0
        self.is_active = True

class IntermediateMessagingService:
    """
    Enterprise-grade intermediate messaging service for real-time agent call visibility
    
    This service provides real-time streaming of agent call events to consumers/UI,
    enabling visibility into the orchestration process as it happens.
    """
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.config = IntermediateMessagingConfig()
        
        # Event storage and management
        self.event_store: Dict[str, AgentCallEvent] = {}
        self.event_streams: Dict[str, List[AgentCallEvent]] = {}
        
        # WebSocket connection management
        self.active_connections: Dict[str, EventSubscription] = {}
        self.connection_metrics: Dict[str, Dict[str, Any]] = {}
        
        # Circuit breaker for error handling
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        
        # Metrics and monitoring
        self.metrics = AgentCallMetrics()
        self.start_time = datetime.utcnow()
        
        # Event handlers
        self.event_handlers: Dict[AgentCallEventType, List[Callable]] = {}
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
        
        logger.info("Intermediate Messaging Service initialized")
    
    async def initialize(self):
        """Initialize the intermediate messaging service"""
        try:
            logger.info("Initializing Intermediate Messaging Service")
            
            # Start background tasks
            self.cleanup_task = asyncio.create_task(self._cleanup_old_events())
            self.metrics_task = asyncio.create_task(self._update_metrics())
            
            logger.info("Intermediate Messaging Service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Intermediate Messaging Service", error=e)
            raise
    
    async def cleanup(self):
        """Cleanup the intermediate messaging service"""
        try:
            logger.info("Cleaning up Intermediate Messaging Service")
            
            # Cancel background tasks
            if self.cleanup_task:
                self.cleanup_task.cancel()
            if self.metrics_task:
                self.metrics_task.cancel()
            
            # Close all WebSocket connections
            for connection_id, subscription in list(self.active_connections.items()):
                await self._close_connection(connection_id)
            
            logger.info("Intermediate Messaging Service cleanup completed")
            
        except Exception as e:
            logger.error("Failed to cleanup Intermediate Messaging Service", error=e)
    
    async def emit_event(self, event: AgentCallEvent) -> bool:
        """
        Emit an agent call event to all subscribed connections
        
        Args:
            event: The agent call event to emit
            
        Returns:
            bool: True if event was successfully emitted, False otherwise
        """
        try:
            if not self.circuit_breaker.can_execute():
                logger.warning("Circuit breaker is open, dropping event", event_id=event.id)
                return False
            
            # Store event
            self.event_store[event.id] = event
            
            # Add to stream
            if event.session_id not in self.event_streams:
                self.event_streams[event.session_id] = []
            self.event_streams[event.session_id].append(event)
            
            # Update metrics
            self.metrics.total_events += 1
            self.metrics.events_by_type[event.event_type.value] = \
                self.metrics.events_by_type.get(event.event_type.value, 0) + 1
            self.metrics.events_by_agent[event.agent_name] = \
                self.metrics.events_by_agent.get(event.agent_name, 0) + 1
            self.metrics.events_by_status[event.status.value] = \
                self.metrics.events_by_status.get(event.status.value, 0) + 1
            
            # Broadcast to subscribers
            await self._broadcast_event(event)
            
            # Record success
            self.circuit_breaker.record_success()
            
            logger.debug(
                "Event emitted successfully",
                event_id=event.id,
                event_type=event.event_type,
                agent_name=event.agent_name
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to emit event", error=e, event_id=event.id)
            self.circuit_breaker.record_failure()
            return False
    
    async def subscribe_to_events(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        filter_criteria: Optional[AgentCallEventFilter] = None
    ) -> str:
        """
        Subscribe to agent call events via WebSocket
        
        Args:
            websocket: WebSocket connection
            session_id: Session identifier
            user_id: User identifier
            filter_criteria: Optional event filter criteria
            
        Returns:
            str: Connection ID for the subscription
        """
        try:
            connection_id = str(uuid.uuid4())
            
            # Create subscription
            subscription = EventSubscription(
                connection_id=connection_id,
                websocket=websocket,
                filter_criteria=filter_criteria
            )
            
            # Store connection
            self.active_connections[connection_id] = subscription
            
            # Update metrics
            self.metrics.active_connections += 1
            self.metrics.total_connections += 1
            
            logger.info(
                "WebSocket subscription created",
                connection_id=connection_id,
                session_id=session_id,
                user_id=user_id
            )
            
            return connection_id
            
        except Exception as e:
            logger.error("Failed to create WebSocket subscription", error=e)
            raise
    
    async def unsubscribe_from_events(self, connection_id: str):
        """
        Unsubscribe from agent call events
        
        Args:
            connection_id: Connection ID to unsubscribe
        """
        try:
            await self._close_connection(connection_id)
            
            logger.info("WebSocket subscription closed", connection_id=connection_id)
            
        except Exception as e:
            logger.error("Failed to close WebSocket subscription", error=e, connection_id=connection_id)
    
    async def get_events(
        self,
        session_id: str,
        filter_criteria: Optional[AgentCallEventFilter] = None,
        limit: int = 100
    ) -> List[AgentCallEvent]:
        """
        Get historical events for a session
        
        Args:
            session_id: Session identifier
            filter_criteria: Optional event filter criteria
            limit: Maximum number of events to return
            
        Returns:
            List[AgentCallEvent]: List of matching events
        """
        try:
            events = self.event_streams.get(session_id, [])
            
            if filter_criteria:
                events = [event for event in events if filter_criteria.matches(event)]
            
            # Sort by timestamp (most recent first)
            events.sort(key=lambda x: x.created_at, reverse=True)
            
            return events[:limit]
            
        except Exception as e:
            logger.error("Failed to get events", error=e, session_id=session_id)
            return []
    
    async def get_metrics(self) -> AgentCallMetrics:
        """Get current metrics for the intermediate messaging service"""
        return self.metrics
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the intermediate messaging service"""
        try:
            status = "healthy"
            issues = []
            
            # Check circuit breaker
            if self.circuit_breaker.state == CircuitBreakerState.OPEN:
                status = "degraded"
                issues.append("Circuit breaker is open")
            
            # Check connection count
            if self.metrics.active_connections > self.config.max_connections_per_session * 10:
                status = "degraded"
                issues.append("High connection count")
            
            # Check error rate
            if self.metrics.error_rate > 0.1:  # 10% error rate threshold
                status = "degraded"
                issues.append("High error rate")
            
            return {
                "status": status,
                "uptime": (datetime.utcnow() - self.start_time).total_seconds(),
                "active_connections": self.metrics.active_connections,
                "total_events": self.metrics.total_events,
                "error_rate": self.metrics.error_rate,
                "circuit_breaker_state": self.circuit_breaker.state.value,
                "issues": issues
            }
            
        except Exception as e:
            logger.error("Failed to get health status", error=e)
            return {
                "status": "unhealthy",
                "uptime": 0,
                "error": str(e)
            }
    
    async def _broadcast_event(self, event: AgentCallEvent):
        """Broadcast event to all subscribed connections"""
        try:
            # Prepare event data
            event_data = event.dict()
            
            # Filter and send to connections
            connections_to_remove = []
            
            for connection_id, subscription in self.active_connections.items():
                try:
                    # Check if event matches filter criteria
                    if not subscription.filter_criteria.matches(event):
                        continue
                    
                    # Send event
                    await subscription.websocket.send_text(json.dumps(event_data))
                    
                    # Update subscription metrics
                    subscription.message_count += 1
                    subscription.last_activity = datetime.utcnow()
                    
                    # Update global metrics
                    self.metrics.messages_sent_per_second += 1
                    
                except WebSocketDisconnect:
                    connections_to_remove.append(connection_id)
                except Exception as e:
                    logger.warning(
                        "Failed to send event to connection",
                        error=e,
                        connection_id=connection_id,
                        event_id=event.id
                    )
                    subscription.error_count += 1
                    self.metrics.connection_errors += 1
            
            # Remove disconnected connections
            for connection_id in connections_to_remove:
                await self._close_connection(connection_id)
                
        except Exception as e:
            logger.error("Failed to broadcast event", error=e, event_id=event.id)
    
    async def _close_connection(self, connection_id: str):
        """Close a WebSocket connection and cleanup resources"""
        try:
            if connection_id in self.active_connections:
                subscription = self.active_connections[connection_id]
                
                # Close WebSocket if still open
                if subscription.websocket.client_state.name == "CONNECTED":
                    await subscription.websocket.close()
                
                # Remove from active connections
                del self.active_connections[connection_id]
                
                # Update metrics
                self.metrics.active_connections = max(0, self.metrics.active_connections - 1)
                
        except Exception as e:
            logger.error("Failed to close connection", error=e, connection_id=connection_id)
    
    async def _cleanup_old_events(self):
        """Background task to cleanup old events"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                cutoff_time = datetime.utcnow() - timedelta(hours=self.config.event_retention_hours)
                
                # Cleanup event store
                events_to_remove = []
                for event_id, event in self.event_store.items():
                    if event.created_at < cutoff_time:
                        events_to_remove.append(event_id)
                
                for event_id in events_to_remove:
                    del self.event_store[event_id]
                
                # Cleanup event streams
                for session_id, events in self.event_streams.items():
                    self.event_streams[session_id] = [
                        event for event in events if event.created_at >= cutoff_time
                    ]
                
                if events_to_remove:
                    logger.info(
                        "Cleaned up old events",
                        removed_count=len(events_to_remove)
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup task", error=e)
    
    async def _update_metrics(self):
        """Background task to update metrics"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                # Calculate rates
                uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
                if uptime_seconds > 0:
                    self.metrics.events_per_second = self.metrics.total_events / uptime_seconds
                    self.metrics.messages_sent_per_second = self.metrics.messages_sent_per_second / 60
                
                # Calculate error rate
                if self.metrics.total_events > 0:
                    error_events = self.metrics.events_by_status.get(AgentCallStatus.FAILED.value, 0)
                    self.metrics.error_rate = error_events / self.metrics.total_events
                
                # Update last updated timestamp
                self.metrics.last_updated = datetime.utcnow()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in metrics update task", error=e)

# Global service instance
_intermediate_messaging_service: Optional[IntermediateMessagingService] = None

def get_intermediate_messaging_service() -> Optional[IntermediateMessagingService]:
    """Get the global intermediate messaging service instance"""
    return _intermediate_messaging_service

def set_intermediate_messaging_service(service: IntermediateMessagingService) -> None:
    """Set the global intermediate messaging service instance"""
    global _intermediate_messaging_service
    _intermediate_messaging_service = service
