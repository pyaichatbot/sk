# ============================================================================
# microservices/shared/infrastructure/health.py
# ============================================================================
"""
Health checker for microservices.
"""

import time
import asyncio
from typing import Dict, Any, Optional
import logging

from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class HealthChecker:
    """Health checker for microservices"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.start_time = time.time()
        self._health_checks: Dict[str, callable] = {}
    
    async def initialize(self) -> None:
        """Initialize health checker"""
        logger.info("Health checker initialized")
    
    async def close(self) -> None:
        """Close health checker"""
        logger.info("Health checker closed")
    
    def get_uptime(self) -> float:
        """Get service uptime in seconds"""
        return time.time() - self.start_time
    
    def add_health_check(self, name: str, check_func: callable) -> None:
        """Add a custom health check"""
        self._health_checks[name] = check_func
    
    async def perform_health_checks(self) -> Dict[str, Any]:
        """Perform all registered health checks"""
        results = {}
        
        for name, check_func in self._health_checks.items():
            try:
                result = await check_func()
                results[name] = result
            except Exception as e:
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            uptime = self.get_uptime()
            custom_checks = await self.perform_health_checks()
            
            # Determine overall health
            overall_status = "healthy"
            for check_result in custom_checks.values():
                if isinstance(check_result, dict) and check_result.get("status") == "unhealthy":
                    overall_status = "degraded"
                    break
            
            return {
                "status": overall_status,
                "uptime": uptime,
                "start_time": self.start_time,
                "checks": custom_checks
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "uptime": self.get_uptime()
            }

# Global health checker instance
_health_checker: Optional[HealthChecker] = None

def get_health_checker() -> Optional[HealthChecker]:
    """Get the global health checker instance"""
    return _health_checker

def set_health_checker(checker: HealthChecker) -> None:
    """Set the global health checker instance"""
    global _health_checker
    _health_checker = checker
