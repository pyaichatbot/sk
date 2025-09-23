"""
Service Discovery Integration - Enterprise Setup
==============================================

This module provides enterprise-grade integration utilities for setting up
service discovery across microservices with minimal configuration.

Features:
- Automatic service registration on startup
- Graceful service deregistration on shutdown
- Health check integration
- Configuration management
- FastAPI integration helpers
- Context managers for lifecycle management
"""

import asyncio
import signal
import sys
from typing import Dict, Any, Optional, List, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .service_discovery import ServiceDiscoveryManager, CircuitBreakerConfig
from .service_client import ServiceDiscoveryClient, RequestConfig
from shared.config.settings import MicroserviceSettings
import logging

logger = logging.getLogger(__name__)

@dataclass
class ServiceDiscoveryConfig:
    """Service discovery configuration"""
    service_name: str
    service_port: int
    health_endpoint: str = "/health"
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    request_config: Optional[RequestConfig] = None
    auto_register: bool = True
    auto_deregister: bool = True

class ServiceDiscoveryIntegration:
    """
    Enterprise Service Discovery Integration
    
    Provides comprehensive integration for service discovery across microservices
    with automatic lifecycle management and enterprise-grade features.
    """
    
    def __init__(
        self,
        settings: MicroserviceSettings,
        config: ServiceDiscoveryConfig
    ):
        self.settings = settings
        self.config = config
        
        # Service discovery components
        self.service_discovery_manager: Optional[ServiceDiscoveryManager] = None
        self._service_client: Optional[ServiceDiscoveryClient] = None
        
        # Lifecycle management
        self._is_initialized = False
        self._shutdown_handlers: List[Callable] = []
        
        logger.info(f"Service Discovery Integration initialized for {config.service_name}")
    
    async def initialize(self) -> None:
        """Initialize service discovery components"""
        try:
            # Initialize service discovery manager
            self.service_discovery_manager = ServiceDiscoveryManager(self.settings)
            await self.service_discovery_manager.initialize()
            
            # Initialize service client
            self.service_client = ServiceDiscoveryClient(
                service_discovery_manager=self.service_discovery_manager,
                settings=self.settings,
                default_config=self.config.request_config
            )
            await self.service_client.initialize()
            
            # Auto-register service if enabled
            if self.config.auto_register:
                await self._register_service()
            
            # Setup shutdown handlers
            if self.config.auto_deregister:
                self._setup_shutdown_handlers()
            
            self._is_initialized = True
            
            logger.info(f"Service Discovery Integration initialized successfully for {self.config.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Service Discovery Integration: {e}")
            raise
    
    async def _register_service(self) -> None:
        """Register service with Consul"""
        try:
            success = await self.service_discovery_manager.register_service_auto(
                service_name=self.config.service_name,
                service_port=self.config.service_port,
                health_endpoint=self.config.health_endpoint,
                tags=self.config.tags,
                metadata=self.config.metadata
            )
            
            if success:
                logger.info(f"Service {self.config.service_name} registered successfully")
            else:
                logger.error(f"Failed to register service {self.config.service_name}")
                
        except Exception as e:
            logger.error(f"Error registering service {self.config.service_name}: {e}")
    
    async def _deregister_service(self) -> None:
        """Deregister service from Consul"""
        try:
            if self.service_discovery_manager:
                success = await self.service_discovery_manager.deregister_service(self.config.service_name)
                if success:
                    logger.info(f"Service {self.config.service_name} deregistered successfully")
                else:
                    logger.warning(f"Failed to deregister service {self.config.service_name}")
        except Exception as e:
            logger.error(f"Error deregistering service {self.config.service_name}: {e}")
    
    def _setup_shutdown_handlers(self) -> None:
        """Setup graceful shutdown handlers"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self.shutdown())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Add shutdown handler
        self._shutdown_handlers.append(self._deregister_service)
    
    async def shutdown(self) -> None:
        """Graceful shutdown of service discovery components"""
        try:
            logger.info(f"Shutting down Service Discovery Integration for {self.config.service_name}")
            
            # Execute shutdown handlers
            for handler in self._shutdown_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                except Exception as e:
                    logger.error(f"Error in shutdown handler: {e}")
            
            # Close service client
            if self.service_client:
                await self.service_client.close()
            
            # Close service discovery manager
            if self.service_discovery_manager:
                await self.service_discovery_manager.close()
            
            self._is_initialized = False
            
            logger.info(f"Service Discovery Integration shutdown completed for {self.config.service_name}")
            
        except Exception as e:
            logger.error(f"Error during Service Discovery Integration shutdown: {e}")
    
    def add_shutdown_handler(self, handler: Callable) -> None:
        """Add custom shutdown handler"""
        self._shutdown_handlers.append(handler)
    
    @property
    def is_initialized(self) -> bool:
        """Check if integration is initialized"""
        return self._is_initialized
    
    @property
    def discovery_manager(self) -> Optional[ServiceDiscoveryManager]:
        """Get service discovery manager"""
        return self.service_discovery_manager
    
    @property
    def service_client(self) -> Optional[ServiceDiscoveryClient]:
        """Get service client"""
        return self._service_client
    
    @service_client.setter
    def service_client(self, value: Optional[ServiceDiscoveryClient]) -> None:
        """Set service client"""
        self._service_client = value

@asynccontextmanager
async def service_discovery_lifecycle(
    settings: MicroserviceSettings,
    config: ServiceDiscoveryConfig
):
    """
    Context manager for service discovery lifecycle management
    
    Usage:
        async with service_discovery_lifecycle(settings, config) as integration:
            # Use integration.service_client for service calls
            pass
    """
    integration = ServiceDiscoveryIntegration(settings, config)
    
    try:
        await integration.initialize()
        yield integration
    finally:
        await integration.shutdown()

def create_fastapi_with_discovery(
    app: FastAPI,
    settings: MicroserviceSettings,
    config: ServiceDiscoveryConfig,
    add_cors: bool = True,
    cors_origins: Optional[List[str]] = None
) -> ServiceDiscoveryIntegration:
    """
    Create FastAPI app with service discovery integration
    
    Args:
        app: FastAPI application instance
        settings: Microservice settings
        config: Service discovery configuration
        add_cors: Whether to add CORS middleware
        cors_origins: CORS allowed origins
        
    Returns:
        ServiceDiscoveryIntegration instance
    """
    # Add CORS middleware if requested
    if add_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins or ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Create service discovery integration
    integration = ServiceDiscoveryIntegration(settings, config)
    
    # Add startup event
    @app.on_event("startup")
    async def startup_event():
        await integration.initialize()
    
    # Add shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        await integration.shutdown()
    
    # Add health check endpoint
    @app.get(config.health_endpoint)
    async def health_check():
        if integration.discovery_manager:
            return await integration.discovery_manager.health_check()
        return {"status": "unhealthy", "error": "Service discovery not initialized"}
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        if integration.discovery_manager:
            return await integration.discovery_manager.get_metrics()
        return {"error": "Service discovery not initialized"}
    
    # Add service discovery info endpoint
    @app.get("/service-info")
    async def service_info():
        return {
            "service_name": config.service_name,
            "service_port": config.service_port,
            "version": settings.service_version,
            "environment": settings.environment.value,
            "tags": config.tags or [],
            "metadata": config.metadata or {},
            "is_initialized": integration.is_initialized
        }
    
    return integration

def create_service_discovery_config(
    service_name: str,
    service_port: int,
    health_endpoint: str = "/health",
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    circuit_breaker_failure_threshold: int = 5,
    circuit_breaker_recovery_timeout: int = 60,
    request_timeout: int = 30,
    request_retry_count: int = 3
) -> ServiceDiscoveryConfig:
    """
    Create service discovery configuration with sensible defaults
    
    Args:
        service_name: Name of the service
        service_port: Port the service runs on
        health_endpoint: Health check endpoint
        tags: Service tags
        metadata: Service metadata
        circuit_breaker_failure_threshold: Circuit breaker failure threshold
        circuit_breaker_recovery_timeout: Circuit breaker recovery timeout
        request_timeout: Request timeout in seconds
        request_retry_count: Number of retries for failed requests
        
    Returns:
        ServiceDiscoveryConfig instance
    """
    circuit_breaker_config = CircuitBreakerConfig(
        failure_threshold=circuit_breaker_failure_threshold,
        recovery_timeout=circuit_breaker_recovery_timeout
    )
    
    request_config = RequestConfig(
        timeout=request_timeout,
        retry_count=request_retry_count
    )
    
    return ServiceDiscoveryConfig(
        service_name=service_name,
        service_port=service_port,
        health_endpoint=health_endpoint,
        tags=tags,
        metadata=metadata,
        circuit_breaker_config=circuit_breaker_config,
        request_config=request_config
    )

# Global integration instance for easy access
_global_integration: Optional[ServiceDiscoveryIntegration] = None

def get_global_integration() -> Optional[ServiceDiscoveryIntegration]:
    """Get global service discovery integration instance"""
    return _global_integration

def set_global_integration(integration: ServiceDiscoveryIntegration) -> None:
    """Set global service discovery integration instance"""
    global _global_integration
    _global_integration = integration

async def get_service_client() -> Optional[ServiceDiscoveryClient]:
    """Get service client from global integration"""
    integration = get_global_integration()
    return integration.service_client if integration else None

async def call_service(
    service_name: str,
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function for service calls using global integration"""
    client = await get_service_client()
    if not client:
        raise RuntimeError("Service discovery integration not available")
    
    from .service_client import HTTPMethod
    return await client.call_service(
        service_name=service_name,
        method=HTTPMethod(method.upper()),
        endpoint=endpoint,
        data=data,
        **kwargs
    )
