# ============================================================================
# microservices/shared/config/__init__.py
# ============================================================================
"""
Shared configuration management for microservices.

This module provides centralized configuration management with support for:
- Environment-based configuration
- Service-specific settings
- Configuration validation
- Hot reloading capabilities
"""

from .settings import MicroserviceSettings, get_service_settings
from .validation import ConfigValidator

__all__ = [
    "MicroserviceSettings",
    "get_service_settings", 
    "ConfigValidator"
]
