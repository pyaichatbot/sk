# ============================================================================
# microservices/orchestration/tests/test_intermediate_messaging.py
# ============================================================================
"""
Comprehensive Test Suite for Intermediate Messaging System
=========================================================

This module provides comprehensive unit and integration tests for the
intermediate messaging system, ensuring enterprise-grade reliability
and functionality.

Test Coverage:
- Agent call event models and validation
- WebSocket connection management
- Event streaming and filtering
- Error handling and circuit breaker patterns
- Performance and scalability
- Security and authentication
"""

import asyncio
import json
import pytest
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import WebSocket
import websockets

from shared.models.intermediate_messaging import (
    AgentCallEvent, AgentCallEventType, AgentCallStatus, AgentCallStream,
    WebSocketConnection, IntermediateMessagingConfig, AgentCallMetrics,
    AgentCallEventFilter
)
from shared.infrastructure.intermediate_messaging import (
    IntermediateMessagingService, CircuitBreaker, CircuitBreakerState
)
from shared.config.observability_settings import (
    ObservabilitySettings, ObservabilityLevel, create_development_settings
)
from intermediate_messaging_endpoints import (
    emit_agent_call_event, track_agent_call, WebSocketConnectionManager
)

# Test fixtures
@pytest.fixture
def test_settings():
    """Create test settings"""
    return create_development_settings()

@pytest.fixture
def messaging_service(test_settings):
    """Create test messaging service"""
    return IntermediateMessagingService(test_settings)

@pytest.fixture
def sample_event():
    """Create sample agent call event"""
    return AgentCallEvent(
        event_type=AgentCallEventType.FUNCTION_CALL_START,
        correlation_id=str(uuid.uuid4()),
        session_id="test-session-123",
        user_id="test-user-456",
        agent_name="test_agent",
        function_name="test_function",
        input_message="Test input message",
        status=AgentCallStatus.RUNNING,
        start_time=datetime.utcnow()
    )

@pytest.fixture
def sample_websocket():
    """Create mock WebSocket"""
    websocket = AsyncMock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.receive_text = AsyncMock()
    websocket.close = AsyncMock()
    websocket.client_state = MagicMock()
    websocket.client_state.name = "CONNECTED"
    return websocket

# ============================================================================
# UNIT TESTS - Agent Call Event Models
# ============================================================================

class TestAgentCallEvent:
    """Test AgentCallEvent model"""
    
    def test_event_creation(self):
        """Test basic event creation"""
        event = AgentCallEvent(
            event_type=AgentCallEventType.FUNCTION_CALL_START,
            correlation_id="test-correlation-123",
            session_id="test-session-456",
            user_id="test-user-789",
            agent_name="test_agent"
        )
        
        assert event.event_type == AgentCallEventType.FUNCTION_CALL_START
        assert event.correlation_id == "test-correlation-123"
        assert event.session_id == "test-session-456"
        assert event.user_id == "test-user-789"
        assert event.agent_name == "test_agent"
        assert event.status == AgentCallStatus.PENDING
    
    def test_correlation_id_generation(self):
        """Test automatic correlation ID generation"""
        event = AgentCallEvent(
            event_type=AgentCallEventType.FUNCTION_CALL_START,
            session_id="test-session",
            user_id="test-user",
            agent_name="test_agent"
        )
        
        assert event.correlation_id is not None
        assert len(event.correlation_id) > 0
    
    def test_duration_calculation(self):
        """Test duration calculation from start and end times"""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=5)
        
        event = AgentCallEvent(
            event_type=AgentCallEventType.FUNCTION_CALL_END,
            correlation_id="test-correlation",
            session_id="test-session",
            user_id="test-user",
            agent_name="test_agent",
            start_time=start_time,
            end_time=end_time
        )
        
        assert event.duration_ms == 5000.0  # 5 seconds in milliseconds
    
    def test_event_serialization(self):
        """Test event serialization to dict"""
        event = AgentCallEvent(
            event_type=AgentCallEventType.FUNCTION_CALL_START,
            correlation_id="test-correlation",
            session_id="test-session",
            user_id="test-user",
            agent_name="test_agent"
        )
        
        event_dict = event.dict()
        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == "function_call_start"
        assert event_dict["correlation_id"] == "test-correlation"
        assert event_dict["session_id"] == "test-session"
        assert event_dict["user_id"] == "test-user"
        assert event_dict["agent_name"] == "test_agent"

class TestAgentCallEventFilter:
    """Test AgentCallEventFilter model"""
    
    def test_filter_creation(self):
        """Test filter creation"""
        filter_criteria = AgentCallEventFilter(
            event_types=[AgentCallEventType.FUNCTION_CALL_START],
            agent_names=["test_agent"],
            statuses=[AgentCallStatus.RUNNING]
        )
        
        assert AgentCallEventType.FUNCTION_CALL_START in filter_criteria.event_types
        assert "test_agent" in filter_criteria.agent_names
        assert AgentCallStatus.RUNNING in filter_criteria.statuses
    
    def test_filter_matching(self, sample_event):
        """Test filter matching logic"""
        # Test event type matching
        filter_criteria = AgentCallEventFilter(
            event_types=[AgentCallEventType.FUNCTION_CALL_START]
        )
        assert filter_criteria.matches(sample_event)
        
        # Test agent name matching
        filter_criteria = AgentCallEventFilter(
            agent_names=["test_agent"]
        )
        assert filter_criteria.matches(sample_event)
        
        # Test exclusion
        filter_criteria = AgentCallEventFilter(
            exclude_agent_names=["test_agent"]
        )
        assert not filter_criteria.matches(sample_event)
    
    def test_filter_metadata_matching(self, sample_event):
        """Test metadata filtering"""
        sample_event.metadata = {"key1": "value1", "key2": "value2"}
        
        filter_criteria = AgentCallEventFilter(
            metadata_filters={"key1": "value1"}
        )
        assert filter_criteria.matches(sample_event)
        
        filter_criteria = AgentCallEventFilter(
            metadata_filters={"key1": "wrong_value"}
        )
        assert not filter_criteria.matches(sample_event)

# ============================================================================
# UNIT TESTS - Circuit Breaker
# ============================================================================

class TestCircuitBreaker:
    """Test CircuitBreaker implementation"""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initial state"""
        circuit_breaker = CircuitBreaker()
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.can_execute() is True
    
    def test_circuit_breaker_failure_tracking(self):
        """Test circuit breaker failure tracking"""
        circuit_breaker = CircuitBreaker()
        
        # Record failures
        for _ in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.can_execute() is False
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery"""
        circuit_breaker = CircuitBreaker()
        
        # Open the circuit
        for _ in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout (mock time)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime.utcnow() + timedelta(seconds=61)
            assert circuit_breaker.can_execute() is True
            assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    def test_circuit_breaker_success_recovery(self):
        """Test circuit breaker success recovery"""
        circuit_breaker = CircuitBreaker()
        
        # Open the circuit
        for _ in range(5):
            circuit_breaker.record_failure()
        
        # Move to half-open state
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime.utcnow() + timedelta(seconds=61)
            circuit_breaker.can_execute()  # This moves to half-open
        
        # Record successes
        for _ in range(3):
            circuit_breaker.record_success()
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.can_execute() is True

# ============================================================================
# UNIT TESTS - Intermediate Messaging Service
# ============================================================================

class TestIntermediateMessagingService:
    """Test IntermediateMessagingService"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, messaging_service):
        """Test service initialization"""
        await messaging_service.initialize()
        assert messaging_service.start_time is not None
        assert messaging_service.cleanup_task is not None
        assert messaging_service.metrics_task is not None
    
    @pytest.mark.asyncio
    async def test_event_emission(self, messaging_service, sample_event):
        """Test event emission"""
        await messaging_service.initialize()
        
        success = await messaging_service.emit_event(sample_event)
        assert success is True
        
        # Check event was stored
        assert sample_event.id in messaging_service.event_store
        assert sample_event.session_id in messaging_service.event_streams
    
    @pytest.mark.asyncio
    async def test_websocket_subscription(self, messaging_service, sample_websocket):
        """Test WebSocket subscription"""
        await messaging_service.initialize()
        
        connection_id = await messaging_service.subscribe_to_events(
            websocket=sample_websocket,
            session_id="test-session",
            user_id="test-user"
        )
        
        assert connection_id is not None
        assert connection_id in messaging_service.active_connections
        assert messaging_service.metrics.active_connections == 1
    
    @pytest.mark.asyncio
    async def test_event_broadcasting(self, messaging_service, sample_event, sample_websocket):
        """Test event broadcasting to subscribers"""
        await messaging_service.initialize()
        
        # Subscribe to events
        connection_id = await messaging_service.subscribe_to_events(
            websocket=sample_websocket,
            session_id=sample_event.session_id,
            user_id=sample_event.user_id
        )
        
        # Emit event
        await messaging_service.emit_event(sample_event)
        
        # Check that message was sent to WebSocket
        sample_websocket.send_text.assert_called_once()
        call_args = sample_websocket.send_text.call_args[0][0]
        event_data = json.loads(call_args)
        assert event_data["event_type"] == "function_call_start"
        assert event_data["agent_name"] == "test_agent"
    
    @pytest.mark.asyncio
    async def test_event_filtering(self, messaging_service, sample_websocket):
        """Test event filtering"""
        await messaging_service.initialize()
        
        # Create filter that only accepts FUNCTION_CALL_START events
        filter_criteria = AgentCallEventFilter(
            event_types=[AgentCallEventType.FUNCTION_CALL_START]
        )
        
        # Subscribe with filter
        connection_id = await messaging_service.subscribe_to_events(
            websocket=sample_websocket,
            session_id="test-session",
            user_id="test-user",
            filter_criteria=filter_criteria
        )
        
        # Emit different event types
        start_event = AgentCallEvent(
            event_type=AgentCallEventType.FUNCTION_CALL_START,
            correlation_id="test-1",
            session_id="test-session",
            user_id="test-user",
            agent_name="test_agent"
        )
        
        end_event = AgentCallEvent(
            event_type=AgentCallEventType.FUNCTION_CALL_END,
            correlation_id="test-2",
            session_id="test-session",
            user_id="test-user",
            agent_name="test_agent"
        )
        
        await messaging_service.emit_event(start_event)
        await messaging_service.emit_event(end_event)
        
        # Only start event should be sent
        assert sample_websocket.send_text.call_count == 1
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, messaging_service, sample_event):
        """Test metrics collection"""
        await messaging_service.initialize()
        
        # Emit multiple events
        for i in range(5):
            event = AgentCallEvent(
                event_type=AgentCallEventType.FUNCTION_CALL_START,
                correlation_id=f"test-{i}",
                session_id="test-session",
                user_id="test-user",
                agent_name="test_agent"
            )
            await messaging_service.emit_event(event)
        
        metrics = await messaging_service.get_metrics()
        assert metrics.total_events == 5
        assert metrics.events_by_type["function_call_start"] == 5
        assert metrics.events_by_agent["test_agent"] == 5
    
    @pytest.mark.asyncio
    async def test_health_status(self, messaging_service):
        """Test health status reporting"""
        await messaging_service.initialize()
        
        health_status = await messaging_service.get_health_status()
        assert "status" in health_status
        assert "uptime" in health_status
        assert "active_connections" in health_status
        assert "total_events" in health_status
        assert health_status["status"] in ["healthy", "degraded", "unhealthy"]
    
    @pytest.mark.asyncio
    async def test_cleanup(self, messaging_service):
        """Test service cleanup"""
        await messaging_service.initialize()
        
        # Verify background tasks are running
        assert messaging_service.cleanup_task is not None
        assert messaging_service.metrics_task is not None
        
        # Cleanup
        await messaging_service.cleanup()
        
        # Verify tasks are cancelled
        assert messaging_service.cleanup_task.cancelled()
        assert messaging_service.metrics_task.cancelled()

# ============================================================================
# INTEGRATION TESTS - WebSocket Endpoints
# ============================================================================

class TestWebSocketEndpoints:
    """Test WebSocket endpoints integration"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, sample_websocket):
        """Test WebSocket connection establishment"""
        connection_manager = WebSocketConnectionManager()
        connection_id = "test-connection-123"
        metadata = {"session_id": "test-session", "user_id": "test-user"}
        
        await connection_manager.connect(sample_websocket, connection_id, metadata)
        
        assert connection_id in connection_manager.active_connections
        assert connection_manager.get_connection_count() == 1
        
        # Test message sending
        await connection_manager.send_message(connection_id, "test message")
        sample_websocket.send_text.assert_called_once_with("test message")
        
        # Test disconnection
        connection_manager.disconnect(connection_id)
        assert connection_id not in connection_manager.active_connections
        assert connection_manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_websocket_broadcast(self, sample_websocket):
        """Test WebSocket broadcast functionality"""
        connection_manager = WebSocketConnectionManager()
        
        # Create multiple connections
        connection_ids = []
        for i in range(3):
            websocket = AsyncMock(spec=WebSocket)
            websocket.send_text = AsyncMock()
            websocket.client_state = MagicMock()
            websocket.client_state.name = "CONNECTED"
            
            connection_id = f"test-connection-{i}"
            await connection_manager.connect(websocket, connection_id, {})
            connection_ids.append(connection_id)
        
        # Broadcast message
        await connection_manager.broadcast("broadcast message")
        
        # Check all connections received the message
        for connection_id in connection_ids:
            websocket = connection_manager.active_connections[connection_id]
            websocket.send_text.assert_called_once_with("broadcast message")

# ============================================================================
# INTEGRATION TESTS - Event Emission Utilities
# ============================================================================

class TestEventEmissionUtilities:
    """Test event emission utility functions"""
    
    @pytest.mark.asyncio
    async def test_emit_agent_call_event(self):
        """Test emit_agent_call_event utility function"""
        with patch('intermediate_messaging_endpoints.get_intermediate_messaging_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.emit_event.return_value = True
            mock_get_service.return_value = mock_service
            
            success = await emit_agent_call_event(
                event_type=AgentCallEventType.FUNCTION_CALL_START,
                agent_name="test_agent",
                session_id="test-session",
                user_id="test-user"
            )
            
            assert success is True
            mock_service.emit_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_track_agent_call_context_manager(self):
        """Test track_agent_call context manager"""
        with patch('intermediate_messaging_endpoints.emit_agent_call_event') as mock_emit:
            mock_emit.return_value = True
            
            async with track_agent_call(
                event_type=AgentCallEventType.FUNCTION_CALL_START,
                agent_name="test_agent",
                session_id="test-session",
                user_id="test-user"
            ) as tracker:
                tracker.set_output("test output")
                tracker.add_metadata("key", "value")
            
            # Should emit start and end events
            assert mock_emit.call_count == 2
            
            # Check start event
            start_call = mock_emit.call_args_list[0]
            assert start_call[1]["event_type"] == AgentCallEventType.FUNCTION_CALL_START
            assert start_call[1]["status"] == AgentCallStatus.RUNNING
            
            # Check end event
            end_call = mock_emit.call_args_list[1]
            assert end_call[1]["event_type"] == AgentCallEventType.FUNCTION_CALL_END
            assert end_call[1]["status"] == AgentCallStatus.COMPLETED
            assert end_call[1]["output_message"] == "test output"
    
    @pytest.mark.asyncio
    async def test_track_agent_call_error_handling(self):
        """Test track_agent_call error handling"""
        with patch('intermediate_messaging_endpoints.emit_agent_call_event') as mock_emit:
            mock_emit.return_value = True
            
            with pytest.raises(ValueError, match="test error"):
                async with track_agent_call(
                    event_type=AgentCallEventType.FUNCTION_CALL_START,
                    agent_name="test_agent",
                    session_id="test-session",
                    user_id="test-user"
                ) as tracker:
                    raise ValueError("test error")
            
            # Should emit start and error events
            assert mock_emit.call_count == 2
            
            # Check error event
            error_call = mock_emit.call_args_list[1]
            assert error_call[1]["event_type"] == AgentCallEventType.FUNCTION_CALL_ERROR
            assert error_call[1]["status"] == AgentCallStatus.FAILED
            assert error_call[1]["error_message"] == "test error"

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_high_volume_event_emission(self, messaging_service):
        """Test high volume event emission"""
        await messaging_service.initialize()
        
        # Emit 1000 events
        start_time = datetime.utcnow()
        
        for i in range(1000):
            event = AgentCallEvent(
                event_type=AgentCallEventType.FUNCTION_CALL_START,
                correlation_id=f"perf-test-{i}",
                session_id="perf-session",
                user_id="perf-user",
                agent_name="perf_agent"
            )
            await messaging_service.emit_event(event)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert duration < 10.0  # 10 seconds for 1000 events
        
        # Verify all events were stored
        metrics = await messaging_service.get_metrics()
        assert metrics.total_events == 1000
    
    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(self, messaging_service):
        """Test concurrent WebSocket connections"""
        await messaging_service.initialize()
        
        # Create 50 concurrent connections
        websockets = []
        connection_ids = []
        
        for i in range(50):
            websocket = AsyncMock(spec=WebSocket)
            websocket.send_text = AsyncMock()
            websocket.client_state = MagicMock()
            websocket.client_state.name = "CONNECTED"
            websockets.append(websocket)
            
            connection_id = await messaging_service.subscribe_to_events(
                websocket=websocket,
                session_id=f"concurrent-session-{i}",
                user_id=f"concurrent-user-{i}"
            )
            connection_ids.append(connection_id)
        
        # Verify all connections are active
        assert messaging_service.metrics.active_connections == 50
        
        # Emit event and verify all connections receive it
        event = AgentCallEvent(
            event_type=AgentCallEventType.FUNCTION_CALL_START,
            correlation_id="concurrent-test",
            session_id="concurrent-session-0",
            user_id="concurrent-user-0",
            agent_name="concurrent_agent"
        )
        
        await messaging_service.emit_event(event)
        
        # All connections should receive the event
        for websocket in websockets:
            websocket.send_text.assert_called()

# ============================================================================
# SECURITY TESTS
# ============================================================================

class TestSecurity:
    """Test security features"""
    
    @pytest.mark.asyncio
    async def test_websocket_authentication(self, messaging_service):
        """Test WebSocket authentication"""
        await messaging_service.initialize()
        
        # Test with valid authentication (mock)
        with patch('intermediate_messaging_endpoints.authenticate_websocket') as mock_auth:
            mock_auth.return_value = True
            
            websocket = AsyncMock(spec=WebSocket)
            websocket.send_text = AsyncMock()
            websocket.client_state = MagicMock()
            websocket.client_state.name = "CONNECTED"
            
            connection_id = await messaging_service.subscribe_to_events(
                websocket=websocket,
                session_id="auth-session",
                user_id="auth-user"
            )
            
            assert connection_id is not None
    
    def test_event_data_validation(self):
        """Test event data validation"""
        # Test with invalid event type
        with pytest.raises(ValueError):
            AgentCallEvent(
                event_type="invalid_event_type",  # Invalid enum value
                correlation_id="test",
                session_id="test-session",
                user_id="test-user",
                agent_name="test_agent"
            )
        
        # Test with missing required fields
        with pytest.raises(ValueError):
            AgentCallEvent(
                event_type=AgentCallEventType.FUNCTION_CALL_START,
                # Missing required fields
            )

# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

class TestConfiguration:
    """Test configuration management"""
    
    def test_development_settings(self):
        """Test development settings creation"""
        settings = create_development_settings()
        
        assert settings.environment == "development"
        assert settings.observability_level == ObservabilityLevel.BASIC
        assert settings.intermediate_messaging_enabled is True
        assert settings.opentelemetry_enabled is False
        assert settings.sk_telemetry_enabled is False
        assert settings.prometheus_enabled is False
        assert settings.grafana_enabled is False
        assert settings.apm_enabled is False
    
    def test_production_settings(self):
        """Test production settings creation"""
        from shared.config.observability_settings import create_production_settings
        settings = create_production_settings()
        
        assert settings.environment == "production"
        assert settings.observability_level == ObservabilityLevel.FULL
        assert settings.intermediate_messaging_enabled is True
        assert settings.opentelemetry_enabled is True
        assert settings.sk_telemetry_enabled is True
        assert settings.prometheus_enabled is True
        assert settings.grafana_enabled is True
        assert settings.apm_enabled is True
    
    def test_feature_configuration(self):
        """Test feature configuration retrieval"""
        settings = create_development_settings()
        
        # Test intermediate messaging config
        config = settings.get_feature_config("intermediate_messaging")
        assert config["enabled"] is True
        assert "websocket_max_connections" in config
        
        # Test OpenTelemetry config
        config = settings.get_feature_config("opentelemetry")
        assert config["enabled"] is False
    
    def test_environment_variables_conversion(self):
        """Test conversion to environment variables"""
        settings = create_development_settings()
        env_vars = settings.to_environment_variables()
        
        assert "OBSERVABILITY_INTERMEDIATE_MESSAGING_ENABLED" in env_vars
        assert "OBSERVABILITY_OPENTELEMETRY_ENABLED" in env_vars
        assert "OBSERVABILITY_ENVIRONMENT" in env_vars
        assert env_vars["OBSERVABILITY_ENVIRONMENT"] == "development"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
