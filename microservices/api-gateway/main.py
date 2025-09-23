# ============================================================================
# microservices/api-gateway/main.py
# ============================================================================
"""
API Gateway Service

This service serves as the single entry point for all client requests,
handling routing, authentication, rate limiting, and load balancing.
"""

import asyncio
import sys
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import uvicorn
from datetime import datetime

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.config.settings import MicroserviceSettings, get_service_settings
from shared.config.validation import ConfigValidator
from shared.models.common import HealthCheck, HealthStatus, ErrorResponse
from shared.infrastructure.database import DatabaseManager, get_database_manager
from shared.infrastructure.redis import RedisManager, get_redis_manager
from shared.infrastructure.service_discovery import ServiceDiscoveryManager, get_service_discovery_manager
from shared.infrastructure.discovery_integration import (
    ServiceDiscoveryIntegration,
    create_service_discovery_config,
    set_global_integration
)
from shared.infrastructure.health import HealthChecker, get_health_checker
from shared.infrastructure.monitoring import MetricsCollector, get_metrics_collector

# Import API Gateway specific modules
from routers import chat, agents, documents, orchestration, health
from middleware import security, rate_limiting, logging_middleware
from services.routing_service import RoutingService
from services.load_balancer import LoadBalancer

# Initialize settings first with default values
import os
os.environ.setdefault("SECRET_KEY", "default-secret-key-for-development")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "api_gateway")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SERVICE_NAME", "api-gateway")
os.environ.setdefault("SERVICE_PORT", "8000")

settings = get_service_settings()

# Global instances
database_manager: DatabaseManager = None
redis_manager: RedisManager = None
service_discovery: ServiceDiscoveryManager = None
service_discovery_integration: ServiceDiscoveryIntegration = None
health_checker: HealthChecker = None
metrics_collector: MetricsCollector = None
routing_service: RoutingService = None
load_balancer: LoadBalancer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global settings, database_manager, redis_manager, service_discovery, service_discovery_integration, health_checker, metrics_collector, routing_service, load_balancer
    
    # Settings already initialized at module level
    
    # Validate configuration
    validator = ConfigValidator()
    validation_result = validator.validate_settings(settings)
    
    if not validation_result["valid"]:
        print(f"Configuration validation failed: {validation_result['errors']}")
        sys.exit(1)
    
    if validation_result["warnings"]:
        print(f"Configuration warnings: {validation_result['warnings']}")
    
    print(f"Starting API Gateway Service v{settings.service_version}")
    
    try:
        # Initialize infrastructure components (optional for development)
        try:
            database_manager = DatabaseManager(settings)
            await database_manager.initialize()
            print("Database connection initialized successfully")
        except Exception as e:
            print(f"Database connection failed (continuing without database): {e}")
            database_manager = None
        
        try:
            redis_manager = RedisManager(settings)
            await redis_manager.initialize()
            print("Redis connection initialized successfully")
        except Exception as e:
            print(f"Redis connection failed (continuing without Redis): {e}")
            redis_manager = None
        
        # Initialize service discovery integration
        service_discovery_config = create_service_discovery_config(
            service_name=settings.service_name,
            service_port=settings.service_port,
            health_endpoint="/api/v1/health",
            tags=["api-gateway", "gateway", "routing"],
            metadata={
                "version": settings.service_version,
                "environment": settings.environment.value,
                "capabilities": ["routing", "authentication", "rate_limiting", "load_balancing"]
            }
        )
        
        service_discovery_integration = ServiceDiscoveryIntegration(settings, service_discovery_config)
        await service_discovery_integration.initialize()
        
        # Set global integration for easy access
        set_global_integration(service_discovery_integration)
        
        # Get service discovery manager from integration
        service_discovery = service_discovery_integration.discovery_manager
        
        health_checker = HealthChecker(settings)
        await health_checker.initialize()
        
        metrics_collector = MetricsCollector(settings)
        await metrics_collector.initialize()
        
        # Initialize API Gateway specific services
        routing_service = RoutingService(service_discovery, settings)
        await routing_service.initialize()
        
        load_balancer = LoadBalancer()
        await load_balancer.initialize()
        
        print("API Gateway Service initialized successfully")
        
        yield
        
    except Exception as e:
        print(f"Failed to initialize API Gateway Service: {e}")
        raise
    finally:
        # Cleanup
        if service_discovery_integration:
            await service_discovery_integration.shutdown()
        
        if load_balancer:
            await load_balancer.close()
        
        if routing_service:
            await routing_service.close()
        
        if metrics_collector:
            await metrics_collector.close()
        
        if health_checker:
            await health_checker.close()
        
        if redis_manager:
            await redis_manager.close()
        
        if database_manager:
            await database_manager.close()
        
        print("API Gateway Service shutdown completed")

# Create FastAPI application
app = FastAPI(
    title="API Gateway Service",
    description="Single entry point for Enterprise Agentic AI System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else ["https://*.yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(logging_middleware.RequestLoggingMiddleware, settings=settings)
app.add_middleware(rate_limiting.RateLimitingMiddleware, redis_manager=redis_manager, settings=settings)
app.add_middleware(security.SecurityMiddleware, settings=settings)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(orchestration.router, prefix="/api/v1", tags=["Orchestration"])

# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=f"HTTP_{exc.status_code}",
            error_message=exc.detail,
            error_type="HTTPException",
            request_id=getattr(request.state, 'request_id', None)
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="INTERNAL_SERVER_ERROR",
            error_message="An internal server error occurred",
            error_type=type(exc).__name__,
            request_id=getattr(request.state, 'request_id', None),
            stack_trace=str(exc) if settings.debug else None
        ).dict()
    )

# Dependency injection
async def get_current_settings() -> MicroserviceSettings:
    """Get current service settings"""
    return settings

async def get_database() -> DatabaseManager:
    """Get database manager"""
    return database_manager

async def get_redis() -> RedisManager:
    """Get Redis manager"""
    return redis_manager

async def get_service_discovery() -> ServiceDiscoveryManager:
    """Get service discovery manager"""
    return service_discovery

async def get_health_checker() -> HealthChecker:
    """Get health checker"""
    return health_checker

async def get_metrics() -> MetricsCollector:
    """Get metrics collector"""
    return metrics_collector

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        log_level="info",
        reload=False,
        access_log=True
    )
