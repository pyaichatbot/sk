# ============================================================================
# microservices/shared/infrastructure/monitoring.py
# ============================================================================
"""
Monitoring and metrics collection for microservices.
"""

import time
import asyncio
from typing import Dict, Any, Optional
import logging

from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Metrics collector for microservices"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.start_time = time.time()
        self._metrics: Dict[str, Any] = {}
        self._counters: Dict[str, int] = {}
        self._timers: Dict[str, list] = {}
    
    async def initialize(self) -> None:
        """Initialize metrics collector"""
        logger.info("Metrics collector initialized")
    
    async def close(self) -> None:
        """Close metrics collector"""
        logger.info("Metrics collector closed")
    
    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter metric"""
        self._counters[name] = self._counters.get(name, 0) + value
    
    def record_timer(self, name: str, duration: float) -> None:
        """Record a timer metric"""
        if name not in self._timers:
            self._timers[name] = []
        self._timers[name].append(duration)
        
        # Keep only last 1000 measurements
        if len(self._timers[name]) > 1000:
            self._timers[name] = self._timers[name][-1000:]
    
    def set_gauge(self, name: str, value: Any) -> None:
        """Set a gauge metric"""
        self._metrics[name] = value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics"""
        metrics = {
            "uptime": time.time() - self.start_time,
            "counters": self._counters.copy(),
            "gauges": self._metrics.copy(),
            "timers": {}
        }
        
        # Calculate timer statistics
        for name, values in self._timers.items():
            if values:
                metrics["timers"][name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "sum": sum(values)
                }
        
        return metrics
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            return {
                "status": "healthy",
                "uptime": time.time() - self.start_time,
                "metrics_count": len(self._metrics) + len(self._counters) + len(self._timers)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get the global metrics collector instance"""
    return _metrics_collector

def set_metrics_collector(collector: MetricsCollector) -> None:
    """Set the global metrics collector instance"""
    global _metrics_collector
    _metrics_collector = collector
