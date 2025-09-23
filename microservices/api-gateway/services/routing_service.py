# ============================================================================
# microservices/api-gateway/services/routing_service.py
# ============================================================================
"""
Routing service for API Gateway.
Handles request routing to appropriate microservices.
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urljoin
from contextlib import asynccontextmanager
import logging

from shared.infrastructure.service_discovery import ServiceDiscoveryManager
from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class RoutingService:
    """Service for routing requests to microservices"""
    
    def __init__(self, service_discovery: ServiceDiscoveryManager, settings: MicroserviceSettings):
        self.service_discovery = service_discovery
        self.settings = settings
        self.session: Optional[aiohttp.ClientSession] = None
        self._service_cache: Dict[str, List[str]] = {}
        self._cache_ttl = 30  # seconds
        self._last_cache_update: Dict[str, float] = {}
    
    async def initialize(self) -> None:
        """Initialize the routing service"""
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
        )
        logger.info("Routing service initialized")
    
    async def close(self) -> None:
        """Close the routing service"""
        if self.session:
            await self.session.close()
        logger.info("Routing service closed")
    
    async def get_service_url(self, service_name: str) -> Optional[str]:
        """
        Get the URL for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Optional[str]: Service URL or None if not found
        """
        try:
            # Check cache first
            if self._is_cache_valid(service_name):
                cached_urls = self._service_cache.get(service_name, [])
                if cached_urls:
                    return cached_urls[0]  # Return first available URL
            
            # Get service from service discovery
            service_info = await self.service_discovery.get_service(service_name)
            if not service_info:
                logger.warning(f"Service {service_name} not found in service discovery")
                return None
            
            # Extract URLs from service instances
            urls = []
            for instance in service_info.instances:
                url = f"http://{instance.host}:{instance.port}"
                urls.append(url)
            
            if not urls:
                logger.warning(f"No instances found for service {service_name}")
                return None
            
            # Update cache
            self._service_cache[service_name] = urls
            self._last_cache_update[service_name] = asyncio.get_event_loop().time()
            
            return urls[0]
            
        except Exception as e:
            logger.error(f"Error getting service URL for {service_name}: {e}")
            return None
    
    async def get_service_instances(self, service_name: str) -> List[str]:
        """
        Get all instances of a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            List[str]: List of service URLs
        """
        try:
            # Check cache first
            if self._is_cache_valid(service_name):
                return self._service_cache.get(service_name, [])
            
            # Get service from service discovery
            service_info = await self.service_discovery.get_service(service_name)
            if not service_info:
                return []
            
            # Extract URLs from service instances
            urls = []
            for instance in service_info.instances:
                url = f"http://{instance.host}:{instance.port}"
                urls.append(url)
            
            # Update cache
            self._service_cache[service_name] = urls
            self._last_cache_update[service_name] = asyncio.get_event_loop().time()
            
            return urls
            
        except Exception as e:
            logger.error(f"Error getting service instances for {service_name}: {e}")
            return []
    
    async def forward_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> aiohttp.ClientResponse:
        """
        Forward a request to a service.
        
        Args:
            method: HTTP method
            url: Target URL
            data: Request data
            params: Query parameters
            headers: Request headers
            timeout: Request timeout
            
        Returns:
            aiohttp.ClientResponse: Response from the service
        """
        if not self.session:
            raise RuntimeError("Routing service not initialized")
        
        try:
            # Prepare request data
            json_data = None
            if data:
                json_data = json.dumps(data)
            
            # Prepare headers
            request_headers = {
                "Content-Type": "application/json",
                "User-Agent": f"{self.settings.service_name}/{self.settings.service_version}"
            }
            if headers:
                request_headers.update(headers)
            
            # Make request
            async with self.session.request(
                method=method,
                url=url,
                data=json_data,
                params=params,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=timeout or 30)
            ) as response:
                # Read response content
                response_text = await response.text()
                
                # Create a mock response object with the same interface
                class MockResponse:
                    def __init__(self, status_code: int, text: str, headers: Dict[str, str]):
                        self.status_code = status_code
                        self.text = text
                        self.headers = headers
                        self.json_data = None
                    
                    def json(self) -> Dict[str, Any]:
                        if self.json_data is None:
                            try:
                                self.json_data = json.loads(self.text)
                            except json.JSONDecodeError:
                                self.json_data = {}
                        return self.json_data
                
                return MockResponse(response.status, response_text, dict(response.headers))
                
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for {method} {url}")
            raise
        except Exception as e:
            logger.error(f"Error forwarding request to {method} {url}: {e}")
            raise
    
    @asynccontextmanager
    async def stream_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ):
        """
        Stream a request to a service.
        
        Args:
            method: HTTP method
            url: Target URL
            data: Request data
            headers: Request headers
            timeout: Request timeout
            
        Yields:
            aiohttp.ClientResponse: Streaming response
        """
        if not self.session:
            raise RuntimeError("Routing service not initialized")
        
        try:
            # Prepare request data
            json_data = None
            if data:
                json_data = json.dumps(data)
            
            # Prepare headers
            request_headers = {
                "Content-Type": "application/json",
                "User-Agent": f"{self.settings.service_name}/{self.settings.service_version}"
            }
            if headers:
                request_headers.update(headers)
            
            # Make streaming request
            async with self.session.request(
                method=method,
                url=url,
                data=json_data,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=timeout or 30)
            ) as response:
                yield response
                
        except Exception as e:
            logger.error(f"Error streaming request to {method} {url}: {e}")
            raise
    
    def _is_cache_valid(self, service_name: str) -> bool:
        """Check if service cache is valid"""
        if service_name not in self._last_cache_update:
            return False
        
        current_time = asyncio.get_event_loop().time()
        return (current_time - self._last_cache_update[service_name]) < self._cache_ttl
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for routing service"""
        try:
            # Check if session is available
            if not self.session:
                return {
                    "status": "unhealthy",
                    "error": "Session not initialized"
                }
            
            # Check service discovery connectivity
            if not self.service_discovery:
                return {
                    "status": "unhealthy",
                    "error": "Service discovery not available"
                }
            
            # Test service discovery
            try:
                await self.service_discovery.get_service("test")
            except Exception as e:
                logger.warning(f"Service discovery test failed: {e}")
            
            return {
                "status": "healthy",
                "cache_size": len(self._service_cache),
                "cached_services": list(self._service_cache.keys())
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
