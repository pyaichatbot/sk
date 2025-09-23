# ============================================================================
# microservices/shared/infrastructure/__init__.py
# ============================================================================
"""
Shared infrastructure components for microservices.

This module provides common infrastructure utilities including:
- Database connection management
- Redis client management
- Message queue integration
- Service discovery
- Health checks
- Monitoring and observability
"""

from .database import DatabaseManager, get_database_manager
from .database_per_service import ServiceDatabaseManager, get_service_database_manager
from .redis import RedisManager, get_redis_manager
from .messaging import MessageQueueManager, get_message_queue_manager
from .service_discovery import (
    ServiceDiscoveryManager, 
    get_service_discovery_manager,
    LoadBalancingStrategy,
    CircuitBreakerConfig,
    ServiceInstance
)
from .service_client import (
    ServiceDiscoveryClient,
    HTTPMethod,
    RequestConfig,
    ServiceCallMetrics,
    get_service,
    post_service,
    put_service,
    delete_service
)
from .discovery_integration import (
    ServiceDiscoveryIntegration,
    ServiceDiscoveryConfig,
    service_discovery_lifecycle,
    create_fastapi_with_discovery,
    create_service_discovery_config,
    get_global_integration,
    set_global_integration,
    get_service_client,
    call_service
)
from .health import HealthChecker, get_health_checker
from .monitoring import MetricsCollector, get_metrics_collector
from .intermediate_messaging import (
    IntermediateMessagingService, 
    get_intermediate_messaging_service,
    set_intermediate_messaging_service
)

__all__ = [
    # Database
    "DatabaseManager",
    "get_database_manager",
    "ServiceDatabaseManager",
    "get_service_database_manager",
    
    # Redis
    "RedisManager", 
    "get_redis_manager",
    
    # Messaging
    "MessageQueueManager",
    "get_message_queue_manager",
    
    # Service Discovery
    "ServiceDiscoveryManager",
    "get_service_discovery_manager",
    "LoadBalancingStrategy",
    "CircuitBreakerConfig",
    "ServiceInstance",
    
    # Service Client
    "ServiceDiscoveryClient",
    "HTTPMethod",
    "RequestConfig",
    "ServiceCallMetrics",
    "get_service",
    "post_service",
    "put_service",
    "delete_service",
    
    # Discovery Integration
    "ServiceDiscoveryIntegration",
    "ServiceDiscoveryConfig",
    "service_discovery_lifecycle",
    "create_fastapi_with_discovery",
    "create_service_discovery_config",
    "get_global_integration",
    "set_global_integration",
    "get_service_client",
    "call_service",
    
    # Health
    "HealthChecker",
    "get_health_checker",
    
    # Monitoring
    "MetricsCollector",
    "get_metrics_collector",
    
    # Intermediate Messaging (MANDATORY)
    "IntermediateMessagingService",
    "get_intermediate_messaging_service",
    "set_intermediate_messaging_service"
]
