"""
Service Discovery Client - Enterprise HTTP Client
===============================================

This module provides an enterprise-grade HTTP client that integrates with
the service discovery system for inter-service communication.

Features:
- Automatic service discovery and load balancing
- Circuit breaker pattern implementation
- Retry mechanisms with exponential backoff
- Request/response logging and metrics
- Timeout and connection pooling
- Enterprise-grade error handling
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum

import httpx
import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientError

from .service_discovery import (
    ServiceDiscoveryManager, LoadBalancingStrategy, 
    CircuitBreakerConfig, ServiceInstance
)
from shared.config.settings import MicroserviceSettings
import logging

logger = logging.getLogger(__name__)

class HTTPMethod(str, Enum):
    """HTTP methods"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

@dataclass
class RequestConfig:
    """Request configuration"""
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    max_retry_delay: float = 60.0
    headers: Optional[Dict[str, str]] = None
    verify_ssl: bool = True

@dataclass
class ServiceCallMetrics:
    """Service call metrics"""
    service_name: str
    method: str
    endpoint: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    success: bool = False
    retry_count: int = 0
    circuit_breaker_state: Optional[str] = None
    error_message: Optional[str] = None

class ServiceDiscoveryClient:
    """
    Enterprise HTTP client with service discovery integration
    
    Provides advanced features for inter-service communication:
    - Automatic service discovery and load balancing
    - Circuit breaker pattern with configurable thresholds
    - Retry mechanisms with exponential backoff
    - Comprehensive metrics and logging
    - Connection pooling and timeout management
    """
    
    def __init__(
        self,
        service_discovery_manager: ServiceDiscoveryManager,
        settings: MicroserviceSettings,
        default_config: Optional[RequestConfig] = None
    ):
        self.service_discovery = service_discovery_manager
        self.settings = settings
        self.default_config = default_config or RequestConfig()
        
        # HTTP client session
        self._session: Optional[ClientSession] = None
        
        # Metrics tracking
        self._metrics: List[ServiceCallMetrics] = []
        self._max_metrics_history = 1000
        
        logger.info("Service Discovery Client initialized")
    
    async def initialize(self):
        """Initialize HTTP client session"""
        try:
            # Create HTTP client session with connection pooling
            timeout = ClientTimeout(total=self.default_config.timeout)
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=30,  # Per-host connection limit
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                verify_ssl=self.default_config.verify_ssl
            )
            
            self._session = ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self.default_config.headers or {}
            )
            
            logger.info("Service Discovery Client HTTP session initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Service Discovery Client: {e}")
            raise
    
    async def close(self):
        """Close HTTP client session"""
        try:
            if self._session:
                await self._session.close()
                logger.info("Service Discovery Client HTTP session closed")
        except Exception as e:
            logger.error(f"Error closing Service Discovery Client: {e}")
    
    async def call_service(
        self,
        service_name: str,
        method: HTTPMethod,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        config: Optional[RequestConfig] = None,
        load_balancing_strategy: Optional[LoadBalancingStrategy] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP call to a service with service discovery
        
        Args:
            service_name: Name of the target service
            method: HTTP method
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            headers: Additional headers
            config: Request configuration
            load_balancing_strategy: Load balancing strategy
            
        Returns:
            Dict containing response data and metadata
        """
        request_config = config or self.default_config
        start_time = time.time()
        
        # Create metrics object
        metrics = ServiceCallMetrics(
            service_name=service_name,
            method=method.value,
            endpoint=endpoint,
            start_time=start_time
        )
        
        try:
            # Get service URL
            service_url = await self.service_discovery.get_service_url(
                service_name=service_name,
                path=endpoint,
                load_balancing_strategy=load_balancing_strategy
            )
            
            if not service_url:
                raise RuntimeError(f"Service {service_name} not available")
            
            # Prepare request data
            request_data = self._prepare_request_data(data)
            request_headers = self._prepare_headers(headers)
            
            # Make HTTP request with retries
            response_data = await self._make_request_with_retries(
                service_url=service_url,
                method=method,
                data=request_data,
                params=params,
                headers=request_headers,
                config=request_config,
                metrics=metrics
            )
            
            # Update metrics
            metrics.end_time = time.time()
            metrics.duration_ms = (metrics.end_time - metrics.start_time) * 1000
            metrics.success = True
            
            # Store metrics
            self._store_metrics(metrics)
            
            logger.info(
                f"Service call successful",
                service=service_name,
                method=method.value,
                endpoint=endpoint,
                duration_ms=metrics.duration_ms,
                retry_count=metrics.retry_count
            )
            
            return response_data
            
        except Exception as e:
            # Update metrics for failure
            metrics.end_time = time.time()
            metrics.duration_ms = (metrics.end_time - metrics.start_time) * 1000
            metrics.success = False
            metrics.error_message = str(e)
            
            # Store metrics
            self._store_metrics(metrics)
            
            logger.error(
                f"Service call failed",
                service=service_name,
                method=method.value,
                endpoint=endpoint,
                error=str(e),
                duration_ms=metrics.duration_ms,
                retry_count=metrics.retry_count
            )
            
            raise
    
    async def _make_request_with_retries(
        self,
        service_url: str,
        method: HTTPMethod,
        data: Optional[Union[Dict[str, Any], str]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        config: RequestConfig = None,
        metrics: ServiceCallMetrics = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        if not self._session:
            raise RuntimeError("Service Discovery Client not initialized")
        
        last_exception = None
        retry_delay = config.retry_delay
        
        for attempt in range(config.retry_count + 1):
            try:
                # Make HTTP request
                async with self._session.request(
                    method=method.value,
                    url=service_url,
                    data=data,
                    params=params,
                    headers=headers
                ) as response:
                    
                    # Check response status
                    if response.status >= 400:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}"
                        )
                    
                    # Parse response
                    try:
                        response_data = await response.json()
                    except json.JSONDecodeError:
                        response_data = await response.text()
                    
                    # Update metrics
                    if metrics:
                        metrics.status_code = response.status
                        metrics.retry_count = attempt
                    
                    return {
                        "data": response_data,
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "url": str(response.url)
                    }
                    
            except Exception as e:
                last_exception = e
                metrics.retry_count = attempt + 1
                
                # Check if we should retry
                if attempt < config.retry_count and self._should_retry(e):
                    logger.warning(
                        f"Request failed, retrying in {retry_delay}s",
                        attempt=attempt + 1,
                        max_attempts=config.retry_count + 1,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(
                        retry_delay * config.retry_backoff_factor,
                        config.max_retry_delay
                    )
                else:
                    break
        
        # All retries failed
        raise last_exception or RuntimeError("Request failed after all retries")
    
    def _should_retry(self, exception: Exception) -> bool:
        """Determine if request should be retried based on exception"""
        if isinstance(exception, aiohttp.ClientResponseError):
            # Retry on server errors (5xx) and some client errors (4xx)
            return exception.status >= 500 or exception.status in [408, 429]
        elif isinstance(exception, (aiohttp.ClientError, asyncio.TimeoutError)):
            # Retry on connection errors and timeouts
            return True
        else:
            # Don't retry on other exceptions
            return False
    
    def _prepare_request_data(self, data: Optional[Union[Dict[str, Any], str]]) -> Optional[Union[Dict[str, Any], str]]:
        """Prepare request data for HTTP request"""
        if data is None:
            return None
        
        if isinstance(data, dict):
            return json.dumps(data)
        
        return data
    
    def _prepare_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Prepare headers for HTTP request"""
        request_headers = {}
        
        # Add default headers
        if self.default_config.headers:
            request_headers.update(self.default_config.headers)
        
        # Add request-specific headers
        if headers:
            request_headers.update(headers)
        
        # Add content-type for JSON data
        if "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"
        
        return request_headers
    
    def _store_metrics(self, metrics: ServiceCallMetrics):
        """Store service call metrics"""
        self._metrics.append(metrics)
        
        # Keep only recent metrics to prevent memory leaks
        if len(self._metrics) > self._max_metrics_history:
            self._metrics = self._metrics[-self._max_metrics_history:]
    
    async def get_service_health(self, service_name: str) -> Dict[str, Any]:
        """Get health status of a service"""
        try:
            return await self.call_service(
                service_name=service_name,
                method=HTTPMethod.GET,
                endpoint="/health"
            )
        except Exception as e:
            logger.error(f"Failed to get health for service {service_name}: {e}")
            return {"error": str(e), "healthy": False}
    
    async def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """Get metrics of a service"""
        try:
            return await self.call_service(
                service_name=service_name,
                method=HTTPMethod.GET,
                endpoint="/metrics"
            )
        except Exception as e:
            logger.error(f"Failed to get metrics for service {service_name}: {e}")
            return {"error": str(e)}
    
    def get_client_metrics(self) -> Dict[str, Any]:
        """Get client metrics"""
        if not self._metrics:
            return {"total_calls": 0}
        
        total_calls = len(self._metrics)
        successful_calls = sum(1 for m in self._metrics if m.success)
        failed_calls = total_calls - successful_calls
        
        # Calculate average duration
        durations = [m.duration_ms for m in self._metrics if m.duration_ms is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Calculate success rate
        success_rate = (successful_calls / total_calls) * 100 if total_calls > 0 else 0
        
        # Group by service
        service_stats = {}
        for metrics in self._metrics:
            service_name = metrics.service_name
            if service_name not in service_stats:
                service_stats[service_name] = {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "avg_duration_ms": 0
                }
            
            service_stats[service_name]["total_calls"] += 1
            if metrics.success:
                service_stats[service_name]["successful_calls"] += 1
            else:
                service_stats[service_name]["failed_calls"] += 1
        
        # Calculate average duration per service
        for service_name, stats in service_stats.items():
            service_durations = [
                m.duration_ms for m in self._metrics 
                if m.service_name == service_name and m.duration_ms is not None
            ]
            stats["avg_duration_ms"] = sum(service_durations) / len(service_durations) if service_durations else 0
        
        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration,
            "service_stats": service_stats
        }
    
    def clear_metrics(self):
        """Clear stored metrics"""
        self._metrics.clear()
        logger.info("Service Discovery Client metrics cleared")

# Convenience functions for common HTTP methods
async def get_service(
    client: ServiceDiscoveryClient,
    service_name: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """GET request to a service"""
    return await client.call_service(
        service_name=service_name,
        method=HTTPMethod.GET,
        endpoint=endpoint,
        params=params,
        **kwargs
    )

async def post_service(
    client: ServiceDiscoveryClient,
    service_name: str,
    endpoint: str,
    data: Optional[Union[Dict[str, Any], str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """POST request to a service"""
    return await client.call_service(
        service_name=service_name,
        method=HTTPMethod.POST,
        endpoint=endpoint,
        data=data,
        **kwargs
    )

async def put_service(
    client: ServiceDiscoveryClient,
    service_name: str,
    endpoint: str,
    data: Optional[Union[Dict[str, Any], str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """PUT request to a service"""
    return await client.call_service(
        service_name=service_name,
        method=HTTPMethod.PUT,
        endpoint=endpoint,
        data=data,
        **kwargs
    )

async def delete_service(
    client: ServiceDiscoveryClient,
    service_name: str,
    endpoint: str,
    **kwargs
) -> Dict[str, Any]:
    """DELETE request to a service"""
    return await client.call_service(
        service_name=service_name,
        method=HTTPMethod.DELETE,
        endpoint=endpoint,
        **kwargs
    )
