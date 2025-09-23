# ============================================================================
# microservices/api-gateway/services/load_balancer.py
# ============================================================================
"""
Load balancer service for API Gateway.
Handles load balancing across service instances.
"""

import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    IP_HASH = "ip_hash"

class ServiceInstance:
    """Represents a service instance"""
    
    def __init__(self, url: str, weight: int = 1, health_check_url: Optional[str] = None):
        self.url = url
        self.weight = weight
        self.health_check_url = health_check_url or f"{url}/health"
        self.active_connections = 0
        self.last_health_check = 0
        self.is_healthy = True
        self.response_time = 0.0
        self.error_count = 0
        self.success_count = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 1.0
    
    @property
    def effective_weight(self) -> int:
        """Calculate effective weight based on health and performance"""
        if not self.is_healthy:
            return 0
        
        # Reduce weight based on error rate
        error_rate = 1.0 - self.success_rate
        if error_rate > 0.1:  # More than 10% error rate
            return max(1, int(self.weight * (1.0 - error_rate)))
        
        return self.weight

class LoadBalancer:
    """Load balancer for distributing requests across service instances"""
    
    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN):
        self.strategy = strategy
        self.instances: Dict[str, List[ServiceInstance]] = {}
        self.round_robin_counters: Dict[str, int] = {}
        self.health_check_interval = 30  # seconds
        self.health_check_timeout = 5  # seconds
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def add_service_instances(self, service_name: str, urls: List[str]) -> None:
        """
        Add service instances for a service.
        
        Args:
            service_name: Name of the service
            urls: List of service URLs
        """
        async with self._lock:
            if service_name not in self.instances:
                self.instances[service_name] = []
                self.round_robin_counters[service_name] = 0
            
            # Add new instances
            existing_urls = {instance.url for instance in self.instances[service_name]}
            for url in urls:
                if url not in existing_urls:
                    instance = ServiceInstance(url)
                    self.instances[service_name].append(instance)
                    logger.info(f"Added instance {url} for service {service_name}")
            
            # Remove instances that are no longer in the list
            current_urls = set(urls)
            self.instances[service_name] = [
                instance for instance in self.instances[service_name]
                if instance.url in current_urls
            ]
            
            # Start health checking if not already running
            if service_name not in self._health_check_tasks:
                self._health_check_tasks[service_name] = asyncio.create_task(
                    self._health_check_loop(service_name)
                )
    
    async def select_instance(self, service_name: str, fallback_url: Optional[str] = None) -> str:
        """
        Select an instance for a service.
        
        Args:
            service_name: Name of the service
            fallback_url: Fallback URL if no instances are available
            
        Returns:
            str: Selected instance URL
        """
        async with self._lock:
            instances = self.instances.get(service_name, [])
            
            if not instances:
                if fallback_url:
                    logger.warning(f"No instances available for {service_name}, using fallback: {fallback_url}")
                    return fallback_url
                raise RuntimeError(f"No instances available for service {service_name}")
            
            # Filter healthy instances
            healthy_instances = [instance for instance in instances if instance.is_healthy]
            
            if not healthy_instances:
                logger.warning(f"No healthy instances available for {service_name}")
                # Use fallback or first instance
                if fallback_url:
                    return fallback_url
                return instances[0].url
            
            # Select instance based on strategy
            if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                return await self._round_robin_selection(service_name, healthy_instances)
            elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                return await self._least_connections_selection(healthy_instances)
            elif self.strategy == LoadBalancingStrategy.RANDOM:
                return await self._random_selection(healthy_instances)
            elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
                return await self._weighted_round_robin_selection(service_name, healthy_instances)
            elif self.strategy == LoadBalancingStrategy.IP_HASH:
                return await self._ip_hash_selection(healthy_instances)
            else:
                # Default to round robin
                return await self._round_robin_selection(service_name, healthy_instances)
    
    async def _round_robin_selection(self, service_name: str, instances: List[ServiceInstance]) -> str:
        """Round robin selection"""
        counter = self.round_robin_counters[service_name]
        selected_instance = instances[counter % len(instances)]
        self.round_robin_counters[service_name] = (counter + 1) % len(instances)
        return selected_instance.url
    
    async def _least_connections_selection(self, instances: List[ServiceInstance]) -> str:
        """Least connections selection"""
        selected_instance = min(instances, key=lambda x: x.active_connections)
        return selected_instance.url
    
    async def _random_selection(self, instances: List[ServiceInstance]) -> str:
        """Random selection"""
        selected_instance = random.choice(instances)
        return selected_instance.url
    
    async def _weighted_round_robin_selection(self, service_name: str, instances: List[ServiceInstance]) -> str:
        """Weighted round robin selection"""
        # Calculate total effective weight
        total_weight = sum(instance.effective_weight for instance in instances)
        if total_weight == 0:
            return instances[0].url
        
        # Use round robin counter to select instance
        counter = self.round_robin_counters[service_name]
        current_weight = 0
        
        for instance in instances:
            current_weight += instance.effective_weight
            if counter < current_weight:
                self.round_robin_counters[service_name] = (counter + 1) % total_weight
                return instance.url
        
        # Fallback to first instance
        return instances[0].url
    
    async def _ip_hash_selection(self, instances: List[ServiceInstance]) -> str:
        """IP hash selection (simplified - uses random for now)"""
        # TODO: Implement actual IP hash based on client IP
        return await self._random_selection(instances)
    
    async def record_request_start(self, service_name: str, instance_url: str) -> None:
        """Record the start of a request"""
        async with self._lock:
            instances = self.instances.get(service_name, [])
            for instance in instances:
                if instance.url == instance_url:
                    instance.active_connections += 1
                    break
    
    async def record_request_end(
        self, 
        service_name: str, 
        instance_url: str, 
        success: bool, 
        response_time: float
    ) -> None:
        """Record the end of a request"""
        async with self._lock:
            instances = self.instances.get(service_name, [])
            for instance in instances:
                if instance.url == instance_url:
                    instance.active_connections = max(0, instance.active_connections - 1)
                    instance.response_time = response_time
                    
                    if success:
                        instance.success_count += 1
                    else:
                        instance.error_count += 1
                    break
    
    async def _health_check_loop(self, service_name: str) -> None:
        """Health check loop for a service"""
        while True:
            try:
                await self._perform_health_checks(service_name)
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health check loop error for {service_name}: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _perform_health_checks(self, service_name: str) -> None:
        """Perform health checks for all instances of a service"""
        instances = self.instances.get(service_name, [])
        if not instances:
            return
        
        # Perform health checks concurrently
        tasks = []
        for instance in instances:
            task = asyncio.create_task(self._check_instance_health(instance))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_instance_health(self, instance: ServiceInstance) -> None:
        """Check health of a single instance"""
        try:
            start_time = time.time()
            
            # TODO: Implement actual health check using aiohttp
            # For now, just mark as healthy
            instance.is_healthy = True
            instance.last_health_check = time.time()
            instance.response_time = time.time() - start_time
            
        except Exception as e:
            logger.warning(f"Health check failed for {instance.url}: {e}")
            instance.is_healthy = False
            instance.error_count += 1
    
    async def get_service_stats(self, service_name: str) -> Dict[str, Any]:
        """Get statistics for a service"""
        instances = self.instances.get(service_name, [])
        if not instances:
            return {"error": f"No instances found for service {service_name}"}
        
        total_connections = sum(instance.active_connections for instance in instances)
        healthy_instances = sum(1 for instance in instances if instance.is_healthy)
        total_requests = sum(instance.success_count + instance.error_count for instance in instances)
        total_errors = sum(instance.error_count for instance in instances)
        
        return {
            "service_name": service_name,
            "total_instances": len(instances),
            "healthy_instances": healthy_instances,
            "total_connections": total_connections,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / total_requests if total_requests > 0 else 0,
            "instances": [
                {
                    "url": instance.url,
                    "is_healthy": instance.is_healthy,
                    "active_connections": instance.active_connections,
                    "success_rate": instance.success_rate,
                    "response_time": instance.response_time,
                    "weight": instance.weight,
                    "effective_weight": instance.effective_weight
                }
                for instance in instances
            ]
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for load balancer"""
        try:
            total_services = len(self.instances)
            total_instances = sum(len(instances) for instances in self.instances.values())
            healthy_instances = sum(
                sum(1 for instance in instances if instance.is_healthy)
                for instances in self.instances.values()
            )
            
            return {
                "status": "healthy",
                "strategy": self.strategy.value,
                "total_services": total_services,
                "total_instances": total_instances,
                "healthy_instances": healthy_instances,
                "services": list(self.instances.keys())
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def close(self) -> None:
        """Close the load balancer and cleanup resources"""
        # Cancel health check tasks
        for task in self._health_check_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._health_check_tasks:
            await asyncio.gather(*self._health_check_tasks.values(), return_exceptions=True)
        
        self._health_check_tasks.clear()
        logger.info("Load balancer closed")
