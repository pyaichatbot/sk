# ============================================================================
# microservices/api-gateway/routers/health.py
# ============================================================================
"""
Health check router for API Gateway service.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from shared.models.common import HealthCheck, HealthStatus, ServiceInfo
from shared.infrastructure.database import DatabaseManager
from shared.infrastructure.redis import RedisManager
from shared.infrastructure.service_discovery import ServiceDiscoveryManager
from shared.infrastructure.health import HealthChecker
from shared.infrastructure.monitoring import MetricsCollector
from shared.config.settings import MicroserviceSettings

router = APIRouter()

async def get_health_checker() -> HealthChecker:
    """Get health checker instance"""
    from main import health_checker
    return health_checker

async def get_database() -> Optional[DatabaseManager]:
    """Get database manager instance"""
    from main import database_manager
    return database_manager

async def get_redis() -> Optional[RedisManager]:
    """Get Redis manager instance"""
    from main import redis_manager
    return redis_manager

async def get_service_discovery() -> Optional[ServiceDiscoveryManager]:
    """Get service discovery manager instance"""
    from main import service_discovery
    return service_discovery

async def get_metrics() -> Optional[MetricsCollector]:
    """Get metrics collector instance"""
    from main import metrics_collector
    return metrics_collector

async def get_settings() -> MicroserviceSettings:
    """Get service settings instance"""
    from main import settings
    return settings

@router.get("/health", response_model=HealthCheck)
async def health_check(
    health_checker: HealthChecker = Depends(get_health_checker),
    database: Optional[DatabaseManager] = Depends(get_database),
    redis: Optional[RedisManager] = Depends(get_redis),
    service_discovery: Optional[ServiceDiscoveryManager] = Depends(get_service_discovery),
    metrics: Optional[MetricsCollector] = Depends(get_metrics),
    settings: MicroserviceSettings = Depends(get_settings)
):
    """
    Comprehensive health check for API Gateway service.
    
    Returns:
        HealthCheck: Service health status with dependencies
    """
    try:
        # Perform individual health checks
        checks = {}
        dependencies = {}
        
        # Database health check
        if database:
            db_health = await database.health_check()
            checks["database"] = db_health
            dependencies["database"] = HealthStatus.HEALTHY if db_health["status"] == "healthy" else HealthStatus.UNHEALTHY
        else:
            checks["database"] = {"status": "not_configured"}
            dependencies["database"] = HealthStatus.UNKNOWN
        
        # Redis health check
        if redis:
            redis_health = await redis.health_check()
            checks["redis"] = redis_health
            dependencies["redis"] = HealthStatus.HEALTHY if redis_health["status"] == "healthy" else HealthStatus.UNHEALTHY
        else:
            checks["redis"] = {"status": "not_configured"}
            dependencies["redis"] = HealthStatus.UNKNOWN
        
        # Service discovery health check
        if service_discovery:
            sd_health = await service_discovery.health_check()
            checks["service_discovery"] = sd_health
            dependencies["service_discovery"] = HealthStatus.HEALTHY if sd_health["status"] == "healthy" else HealthStatus.UNHEALTHY
        else:
            checks["service_discovery"] = {"status": "not_configured"}
            dependencies["service_discovery"] = HealthStatus.UNKNOWN
        
        # Metrics health check
        if metrics:
            metrics_health = await metrics.health_check()
            checks["metrics"] = metrics_health
            dependencies["metrics"] = HealthStatus.HEALTHY if metrics_health["status"] == "healthy" else HealthStatus.UNHEALTHY
        else:
            checks["metrics"] = {"status": "not_configured"}
            dependencies["metrics"] = HealthStatus.UNKNOWN
        
        # Determine overall health status
        overall_status = HealthStatus.HEALTHY
        if any(status == HealthStatus.UNHEALTHY for status in dependencies.values()):
            overall_status = HealthStatus.DEGRADED
        if any(status == HealthStatus.UNKNOWN for status in dependencies.values()):
            overall_status = HealthStatus.DEGRADED
        
        # Calculate uptime
        uptime = health_checker.get_uptime() if health_checker else 0.0
        
        return HealthCheck(
            service_name=settings.service_name,
            status=overall_status,
            version=settings.service_version,
            uptime=uptime,
            checks=checks,
            dependencies=dependencies,
            metadata={
                "environment": settings.environment.value,
                "debug_mode": settings.debug,
                "log_level": settings.log_level.value
            }
        )
        
    except Exception as e:
        return HealthCheck(
            service_name=settings.service_name,
            status=HealthStatus.UNHEALTHY,
            version=settings.service_version,
            uptime=0.0,
            checks={"error": {"status": "failed", "error": str(e)}},
            dependencies={},
            metadata={"error": str(e)}
        )

@router.get("/health/ready")
async def readiness_check(
    database: Optional[DatabaseManager] = Depends(get_database),
    redis: Optional[RedisManager] = Depends(get_redis),
    service_discovery: Optional[ServiceDiscoveryManager] = Depends(get_service_discovery)
):
    """
    Readiness check for Kubernetes.
    
    Returns:
        JSONResponse: 200 if ready, 503 if not ready
    """
    try:
        # Check critical dependencies
        ready = True
        issues = []
        
        # Database readiness
        if database:
            db_health = await database.health_check()
            if db_health["status"] != "healthy":
                ready = False
                issues.append("database_unhealthy")
        else:
            ready = False
            issues.append("database_not_configured")
        
        # Redis readiness
        if redis:
            redis_health = await redis.health_check()
            if redis_health["status"] != "healthy":
                ready = False
                issues.append("redis_unhealthy")
        else:
            ready = False
            issues.append("redis_not_configured")
        
        # Service discovery readiness
        if service_discovery:
            sd_health = await service_discovery.health_check()
            if sd_health["status"] != "healthy":
                ready = False
                issues.append("service_discovery_unhealthy")
        else:
            ready = False
            issues.append("service_discovery_not_configured")
        
        if ready:
            return JSONResponse(
                status_code=200,
                content={"status": "ready", "timestamp": datetime.utcnow().isoformat()}
            )
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "issues": issues,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@router.get("/health/live")
async def liveness_check():
    """
    Liveness check for Kubernetes.
    
    Returns:
        JSONResponse: Always returns 200 if service is running
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@router.get("/info", response_model=ServiceInfo)
async def service_info(settings: MicroserviceSettings = Depends(get_settings)):
    """
    Get service information.
    
    Returns:
        ServiceInfo: Service details and capabilities
    """
    return ServiceInfo(
        name=settings.service_name,
        version=settings.service_version,
        description="API Gateway service for Enterprise Agentic AI System",
        environment=settings.environment.value,
        host=settings.service_host,
        port=settings.service_port,
        status=HealthStatus.HEALTHY,
        capabilities=[
            "request_routing",
            "authentication",
            "rate_limiting",
            "load_balancing",
            "api_versioning",
            "request_transformation"
        ],
        endpoints=[
            "/api/v1/health",
            "/api/v1/chat",
            "/api/v1/chat/stream",
            "/api/v1/agents/*",
            "/api/v1/documents/*",
            "/api/v1/orchestration/*"
        ],
        metadata={
            "service_type": "api_gateway",
            "protocol": "http",
            "framework": "fastapi"
        }
    )
