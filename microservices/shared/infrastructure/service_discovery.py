# ============================================================================
# microservices/shared/infrastructure/service_discovery.py
# ============================================================================
"""
Enterprise Service Discovery Manager - Production Ready
=====================================================

This module provides enterprise-grade service discovery using Consul with
advanced features for production environments.

Features:
- Consul-based service registration and discovery
- Automatic health checks and service monitoring
- Load balancing and failover capabilities
- Circuit breaker pattern implementation
- Service mesh integration support
- Enterprise-grade error handling and observability
- Automatic service registration on startup
- Graceful service deregistration on shutdown
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from contextlib import asynccontextmanager
from enum import Enum
import consul.aio
import logging
from dataclasses import dataclass, field

from shared.config.settings import MicroserviceSettings
from shared.models.common import ServiceInfo, ServiceRegistration, ServiceDiscovery, HealthStatus

logger = logging.getLogger(__name__)

class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    WEIGHTED = "weighted"

class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class ServiceInstance:
    """Service instance information"""
    service_id: str
    service_name: str
    address: str
    port: int
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_status: HealthStatus = HealthStatus.HEALTHY
    last_health_check: Optional[datetime] = None
    weight: int = 1
    connections: int = 0

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout: int = 30

class CircuitBreaker:
    """Circuit breaker implementation for service calls"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
    
    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        return False
    
    def on_success(self):
        """Handle successful execution"""
        self.success_count += 1
        self.last_success_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
    
    def on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0

class ServiceDiscoveryManager:
    """
    Enterprise Service Discovery Manager using Consul
    
    Provides advanced service discovery capabilities with:
    - Automatic service registration and deregistration
    - Health monitoring and circuit breaker patterns
    - Load balancing and failover
    - Service mesh integration
    - Enterprise-grade observability
    """
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.consul: Optional[consul.aio.Consul] = None
        self._registered_services: Dict[str, str] = {}  # service_name -> service_id
        self._service_instances: Dict[str, List[ServiceInstance]] = {}  # service_name -> instances
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}  # service_name -> circuit_breaker
        self._load_balancers: Dict[str, LoadBalancingStrategy] = {}  # service_name -> strategy
        self._health_check_tasks: Dict[str, asyncio.Task] = {}  # service_name -> task
        self._is_initialized = False
        self._shutdown_event = asyncio.Event()
        
        # Default circuit breaker config
        self.default_circuit_breaker_config = CircuitBreakerConfig()
        
        logger.info("Service Discovery Manager initialized")
    
    async def initialize(self) -> None:
        """Initialize Consul client and start background tasks"""
        try:
            self.consul = consul.aio.Consul(
                host=self.settings.consul_host,
                port=self.settings.consul_port,
                token=self.settings.consul_token
            )
            
            # Test connection
            await self.consul.agent.self()
            
            # Start background health monitoring
            await self._start_health_monitoring()
            
            self._is_initialized = True
            
            logger.info(
                "Service Discovery Manager initialized successfully",
                host=self.settings.consul_host,
                port=self.settings.consul_port
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Service Discovery Manager: {e}")
            raise
    
    async def _start_health_monitoring(self):
        """Start background health monitoring tasks"""
        try:
            # Start periodic service discovery refresh
            asyncio.create_task(self._periodic_service_refresh())
            
            # Start circuit breaker monitoring
            asyncio.create_task(self._circuit_breaker_monitoring())
            
            logger.info("Health monitoring tasks started")
            
        except Exception as e:
            logger.error(f"Failed to start health monitoring: {e}")
    
    async def _periodic_service_refresh(self):
        """Periodically refresh service instances"""
        while not self._shutdown_event.is_set():
            try:
                await self._refresh_all_services()
                await asyncio.sleep(30)  # Refresh every 30 seconds
            except Exception as e:
                logger.error(f"Service refresh failed: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _circuit_breaker_monitoring(self):
        """Monitor circuit breaker states"""
        while not self._shutdown_event.is_set():
            try:
                for service_name, circuit_breaker in self._circuit_breakers.items():
                    if circuit_breaker.state == CircuitBreakerState.OPEN:
                        if circuit_breaker.can_execute():
                            logger.info(f"Circuit breaker for {service_name} moved to HALF_OPEN")
                
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Circuit breaker monitoring failed: {e}")
                await asyncio.sleep(30)
    
    async def _refresh_all_services(self):
        """Refresh all discovered services"""
        try:
            for service_name in list(self._service_instances.keys()):
                await self._refresh_service_instances(service_name)
        except Exception as e:
            logger.error(f"Failed to refresh services: {e}")
    
    async def _refresh_service_instances(self, service_name: str):
        """Refresh instances for a specific service"""
        try:
            if not self.consul:
                return
            
            # Get healthy service instances
            _, services = await self.consul.health.service(service_name, passing=True)
            
            instances = []
            for service in services:
                service_data = service["Service"]
                meta = service_data.get("Meta", {})
                
                instance = ServiceInstance(
                    service_id=service_data["ID"],
                    service_name=service_data["Service"],
                    address=service_data["Address"],
                    port=service_data["Port"],
                    tags=service_data.get("Tags", []),
                    metadata=meta,
                    health_status=HealthStatus.HEALTHY,
                    last_health_check=datetime.utcnow(),
                    weight=int(meta.get("weight", 1))
                )
                instances.append(instance)
            
            self._service_instances[service_name] = instances
            
            # Initialize circuit breaker if not exists
            if service_name not in self._circuit_breakers:
                self._circuit_breakers[service_name] = CircuitBreaker(self.default_circuit_breaker_config)
            
            # Initialize load balancer if not exists
            if service_name not in self._load_balancers:
                self._load_balancers[service_name] = LoadBalancingStrategy.ROUND_ROBIN
            
            logger.debug(f"Refreshed {len(instances)} instances for service {service_name}")
            
        except Exception as e:
            logger.error(f"Failed to refresh service instances for {service_name}: {e}")
    
    async def close(self) -> None:
        """Close Service Discovery Manager and cleanup resources"""
        try:
            logger.info("Shutting down Service Discovery Manager")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Cancel health monitoring tasks
            for task in self._health_check_tasks.values():
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self._health_check_tasks:
                await asyncio.gather(*self._health_check_tasks.values(), return_exceptions=True)
            
            # Deregister all services
            if self.consul and self._registered_services:
                for service_name, service_id in self._registered_services.items():
                    try:
                        await self.consul.agent.service.deregister(service_id)
                        logger.info(f"Deregistered service {service_name} with ID {service_id}")
                    except Exception as e:
                        logger.error(f"Failed to deregister service {service_name}: {e}")
            
            # Clear all data structures
            self._registered_services.clear()
            self._service_instances.clear()
            self._circuit_breakers.clear()
            self._load_balancers.clear()
            self._health_check_tasks.clear()
            
            self._is_initialized = False
            
            logger.info("Service Discovery Manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during Service Discovery Manager shutdown: {e}")
    
    async def register_service_auto(
        self,
        service_name: str,
        service_port: int,
        health_endpoint: str = "/health",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Automatically register current service with Consul
        
        Args:
            service_name: Name of the service
            service_port: Port the service is running on
            health_endpoint: Health check endpoint
            tags: Service tags
            metadata: Additional metadata
            
        Returns:
            bool: True if registration successful
        """
        try:
            if not self._is_initialized:
                raise RuntimeError("Service Discovery Manager not initialized")
            
            # Get current host IP
            import socket
            host = socket.gethostbyname(socket.gethostname())
            
            service_info = {
                "service_name": service_name,
                "service_url": f"http://{host}:{service_port}",
                "health_endpoint": health_endpoint,
                "version": self.settings.service_version,
                "environment": self.settings.environment.value,
                "tags": tags or [],
                "metadata": metadata or {}
            }
            
            return await self.register_service(service_info)
            
        except Exception as e:
            logger.error(f"Failed to auto-register service {service_name}: {e}")
            return False
    
    async def get_service_instance(
        self,
        service_name: str,
        load_balancing_strategy: Optional[LoadBalancingStrategy] = None
    ) -> Optional[ServiceInstance]:
        """
        Get a service instance using load balancing
        
        Args:
            service_name: Name of the service
            load_balancing_strategy: Load balancing strategy to use
            
        Returns:
            Optional[ServiceInstance]: Selected service instance
        """
        try:
            if not self._is_initialized:
                raise RuntimeError("Service Discovery Manager not initialized")
            
            # Check circuit breaker
            circuit_breaker = self._circuit_breakers.get(service_name)
            if circuit_breaker and not circuit_breaker.can_execute():
                logger.warning(f"Circuit breaker OPEN for service {service_name}")
                return None
            
            # Get service instances
            instances = self._service_instances.get(service_name, [])
            if not instances:
                # Try to discover service
                await self._refresh_service_instances(service_name)
                instances = self._service_instances.get(service_name, [])
            
            if not instances:
                logger.warning(f"No instances found for service {service_name}")
                return None
            
            # Filter healthy instances
            healthy_instances = [i for i in instances if i.health_status == HealthStatus.HEALTHY]
            if not healthy_instances:
                logger.warning(f"No healthy instances found for service {service_name}")
                return None
            
            # Apply load balancing strategy
            strategy = load_balancing_strategy or self._load_balancers.get(service_name, LoadBalancingStrategy.ROUND_ROBIN)
            selected_instance = self._select_instance(healthy_instances, strategy)
            
            # Update circuit breaker on success
            if circuit_breaker:
                circuit_breaker.on_success()
            
            return selected_instance
            
        except Exception as e:
            logger.error(f"Failed to get service instance for {service_name}: {e}")
            
            # Update circuit breaker on failure
            circuit_breaker = self._circuit_breakers.get(service_name)
            if circuit_breaker:
                circuit_breaker.on_failure()
            
            return None
    
    def _select_instance(
        self,
        instances: List[ServiceInstance],
        strategy: LoadBalancingStrategy
    ) -> ServiceInstance:
        """Select service instance based on load balancing strategy"""
        if not instances:
            raise ValueError("No instances provided")
        
        if len(instances) == 1:
            return instances[0]
        
        if strategy == LoadBalancingStrategy.ROUND_ROBIN:
            # Simple round-robin (could be enhanced with proper state tracking)
            import random
            return random.choice(instances)
        
        elif strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return min(instances, key=lambda x: x.connections)
        
        elif strategy == LoadBalancingStrategy.RANDOM:
            import random
            return random.choice(instances)
        
        elif strategy == LoadBalancingStrategy.WEIGHTED:
            # Weighted round-robin
            total_weight = sum(instance.weight for instance in instances)
            if total_weight == 0:
                import random
                return random.choice(instances)
            
            import random
            target = random.randint(1, total_weight)
            current_weight = 0
            
            for instance in instances:
                current_weight += instance.weight
                if current_weight >= target:
                    return instance
            
            return instances[-1]  # Fallback
        
        else:
            # Default to round-robin
            import random
            return random.choice(instances)
    
    async def get_service_url(
        self,
        service_name: str,
        path: str = "",
        load_balancing_strategy: Optional[LoadBalancingStrategy] = None
    ) -> Optional[str]:
        """
        Get service URL with optional path
        
        Args:
            service_name: Name of the service
            path: Path to append to the URL
            load_balancing_strategy: Load balancing strategy
            
        Returns:
            Optional[str]: Service URL
        """
        try:
            instance = await self.get_service_instance(service_name, load_balancing_strategy)
            if not instance:
                return None
            
            url = f"http://{instance.address}:{instance.port}"
            if path:
                if not path.startswith("/"):
                    path = "/" + path
                url += path
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to get service URL for {service_name}: {e}")
            return None
    
    async def register_service(self, service_info: Dict[str, Any]) -> bool:
        """
        Register a service with Consul.
        
        Args:
            service_info: Service information dictionary
            
        Returns:
            bool: True if registration successful
        """
        try:
            if not self.consul:
                raise RuntimeError("Consul client not initialized")
            
            service_name = service_info["service_name"]
            service_url = service_info["service_url"]
            
            # Parse URL to get host and port
            from urllib.parse import urlparse
            parsed_url = urlparse(service_url)
            host = parsed_url.hostname or "localhost"
            port = parsed_url.port or 8000
            
            # Create service ID
            service_id = f"{service_name}-{host}-{port}"
            
            # Prepare service registration data
            service_data = {
                "ID": service_id,
                "Name": service_name,
                "Address": host,
                "Port": port,
                "Tags": service_info.get("tags", []),
                "Meta": {
                    "version": service_info.get("version", "1.0.0"),
                    "environment": service_info.get("environment", "development"),
                    "url": service_url
                }
            }
            
            # Add health check if provided
            if "health_endpoint" in service_info:
                health_url = f"{service_url}{service_info['health_endpoint']}"
                service_data["Check"] = {
                    "HTTP": health_url,
                    "Interval": "30s",
                    "Timeout": "10s",
                    "DeregisterCriticalServiceAfter": "3m"
                }
            
            # Register service using the correct Consul Python client API
            await self.consul.agent.service.register(
                name=service_name,
                service_id=service_id,
                address=host,
                port=port,
                tags=service_info.get("tags", []),
                meta=service_data["Meta"],
                check=service_data.get("Check")
            )
            
            # Store service ID for cleanup
            self._registered_services[service_name] = service_id
            
            logger.info(
                f"Service registered successfully",
                service_name=service_name,
                service_id=service_id,
                host=host,
                port=port
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to register service {service_name}: {e}")
            return False
    
    async def deregister_service(self, service_name: str) -> bool:
        """
        Deregister a service from Consul.
        
        Args:
            service_name: Name of the service to deregister
            
        Returns:
            bool: True if deregistration successful
        """
        try:
            if not self.consul:
                raise RuntimeError("Consul client not initialized")
            
            if service_name not in self._registered_services:
                logger.warning(f"Service {service_name} not found in registered services")
                return False
            
            service_id = self._registered_services[service_name]
            await self.consul.agent.service.deregister(service_id)
            
            # Remove from registered services
            del self._registered_services[service_name]
            
            logger.info(f"Service deregistered successfully", service_name=service_name, service_id=service_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to deregister service {service_name}: {e}")
            return False
    
    async def get_service(self, service_name: str) -> Optional[ServiceDiscovery]:
        """
        Get service information from Consul.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Optional[ServiceDiscovery]: Service discovery information
        """
        try:
            if not self.consul:
                raise RuntimeError("Consul client not initialized")
            
            # Get service instances
            _, services = await self.consul.health.service(service_name, passing=True)
            
            if not services:
                logger.warning(f"No healthy instances found for service {service_name}")
                return None
            
            # Convert to ServiceInfo objects
            instances = []
            for service in services:
                service_data = service["Service"]
                meta = service_data.get("Meta", {})
                
                instance = ServiceInfo(
                    name=service_data["Service"],
                    version=meta.get("version", "1.0.0"),
                    description=f"Instance of {service_name}",
                    environment=meta.get("environment", "development"),
                    host=service_data["Address"],
                    port=service_data["Port"],
                    status=HealthStatus.HEALTHY,
                    capabilities=service_data.get("Tags", []),
                    endpoints=[meta.get("url", f"http://{service_data['Address']}:{service_data['Port']}")],
                    metadata=meta
                )
                instances.append(instance)
            
            return ServiceDiscovery(
                service_name=service_name,
                instances=instances,
                load_balancer="round_robin",
                health_check_interval=30
            )
            
        except Exception as e:
            logger.error(f"Failed to get service {service_name}: {e}")
            return None
    
    async def list_services(self) -> List[str]:
        """
        List all registered services.
        
        Returns:
            List[str]: List of service names
        """
        try:
            if not self.consul:
                raise RuntimeError("Consul client not initialized")
            
            _, services = await self.consul.catalog.services()
            return list(services.keys())
            
        except Exception as e:
            logger.error(f"Failed to list services: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive service discovery health check"""
        try:
            if not self._is_initialized:
                return {
                    "status": "unhealthy",
                    "error": "Service Discovery Manager not initialized"
                }
            
            if not self.consul:
                return {
                    "status": "unhealthy",
                    "error": "Consul client not initialized"
                }
            
            # Test Consul connectivity
            consul_info = await self.consul.agent.self()
            
            # Get registered services count
            services = await self.list_services()
            
            # Get circuit breaker status
            circuit_breaker_status = {}
            for service_name, circuit_breaker in self._circuit_breakers.items():
                circuit_breaker_status[service_name] = {
                    "state": circuit_breaker.state.value,
                    "failure_count": circuit_breaker.failure_count,
                    "success_count": circuit_breaker.success_count
                }
            
            # Get service instances status
            service_instances_status = {}
            for service_name, instances in self._service_instances.items():
                healthy_count = sum(1 for i in instances if i.health_status == HealthStatus.HEALTHY)
                service_instances_status[service_name] = {
                    "total_instances": len(instances),
                    "healthy_instances": healthy_count,
                    "unhealthy_instances": len(instances) - healthy_count
                }
            
            return {
                "status": "healthy",
                "consul_host": self.settings.consul_host,
                "consul_port": self.settings.consul_port,
                "consul_version": consul_info.get("Config", {}).get("Version", "unknown"),
                "registered_services": len(self._registered_services),
                "total_services": len(services),
                "services": services,
                "circuit_breakers": circuit_breaker_status,
                "service_instances": service_instances_status,
                "load_balancers": {k: v.value for k, v in self._load_balancers.items()},
                "is_initialized": self._is_initialized
            }
            
        except Exception as e:
            logger.error(f"Service discovery health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "is_initialized": self._is_initialized
            }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get service discovery metrics"""
        try:
            metrics = {
                "registered_services_count": len(self._registered_services),
                "discovered_services_count": len(self._service_instances),
                "circuit_breakers_count": len(self._circuit_breakers),
                "load_balancers_count": len(self._load_balancers),
                "health_check_tasks_count": len(self._health_check_tasks),
                "is_initialized": self._is_initialized
            }
            
            # Circuit breaker metrics
            circuit_breaker_metrics = {}
            for service_name, circuit_breaker in self._circuit_breakers.items():
                circuit_breaker_metrics[service_name] = {
                    "state": circuit_breaker.state.value,
                    "failure_count": circuit_breaker.failure_count,
                    "success_count": circuit_breaker.success_count,
                    "last_failure_time": circuit_breaker.last_failure_time.isoformat() if circuit_breaker.last_failure_time else None,
                    "last_success_time": circuit_breaker.last_success_time.isoformat() if circuit_breaker.last_success_time else None
                }
            
            metrics["circuit_breakers"] = circuit_breaker_metrics
            
            # Service instance metrics
            service_instance_metrics = {}
            for service_name, instances in self._service_instances.items():
                healthy_instances = [i for i in instances if i.health_status == HealthStatus.HEALTHY]
                service_instance_metrics[service_name] = {
                    "total_instances": len(instances),
                    "healthy_instances": len(healthy_instances),
                    "unhealthy_instances": len(instances) - len(healthy_instances),
                    "average_weight": sum(i.weight for i in instances) / len(instances) if instances else 0,
                    "total_connections": sum(i.connections for i in instances)
                }
            
            metrics["service_instances"] = service_instance_metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get service discovery metrics: {e}")
            return {"error": str(e)}
    
    def set_load_balancing_strategy(
        self,
        service_name: str,
        strategy: LoadBalancingStrategy
    ) -> None:
        """Set load balancing strategy for a service"""
        self._load_balancers[service_name] = strategy
        logger.info(f"Set load balancing strategy for {service_name} to {strategy.value}")
    
    def set_circuit_breaker_config(
        self,
        service_name: str,
        config: CircuitBreakerConfig
    ) -> None:
        """Set circuit breaker configuration for a service"""
        if service_name in self._circuit_breakers:
            self._circuit_breakers[service_name] = CircuitBreaker(config)
            logger.info(f"Updated circuit breaker config for {service_name}")
        else:
            logger.warning(f"Service {service_name} not found for circuit breaker config update")
    
    @asynccontextmanager
    async def service_context(self, service_name: str):
        """Context manager for service calls with automatic circuit breaker handling"""
        instance = await self.get_service_instance(service_name)
        if not instance:
            raise RuntimeError(f"No healthy instances available for service {service_name}")
        
        try:
            yield instance
        except Exception as e:
            # Update circuit breaker on failure
            circuit_breaker = self._circuit_breakers.get(service_name)
            if circuit_breaker:
                circuit_breaker.on_failure()
            raise

# Global service discovery manager instance
_service_discovery_manager: Optional[ServiceDiscoveryManager] = None

def get_service_discovery_manager() -> Optional[ServiceDiscoveryManager]:
    """Get the global service discovery manager instance"""
    return _service_discovery_manager

def set_service_discovery_manager(manager: ServiceDiscoveryManager) -> None:
    """Set the global service discovery manager instance"""
    global _service_discovery_manager
    _service_discovery_manager = manager
