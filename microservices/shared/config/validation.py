# ============================================================================
# microservices/shared/config/validation.py
# ============================================================================
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, ValidationError
import re
from urllib.parse import urlparse

from .settings import MicroserviceSettings

class ConfigValidationError(Exception):
    """Configuration validation error"""
    pass

class ConfigValidator:
    """Configuration validator for microservices"""
    
    @staticmethod
    def validate_settings(settings: MicroserviceSettings) -> Dict[str, List[str]]:
        """
        Validate microservice settings and return validation results.
        
        Args:
            settings: Microservice settings to validate
            
        Returns:
            Dictionary with validation results (errors and warnings)
        """
        errors = []
        warnings = []
        
        # Validate service identity
        errors.extend(ConfigValidator._validate_service_identity(settings))
        
        # Validate database configuration
        errors.extend(ConfigValidator._validate_database_config(settings))
        
        # Validate Redis configuration
        errors.extend(ConfigValidator._validate_redis_config(settings))
        
        # Validate message queue configuration
        errors.extend(ConfigValidator._validate_message_queue_config(settings))
        
        # Validate service discovery configuration
        errors.extend(ConfigValidator._validate_service_discovery_config(settings))
        
        # Validate security configuration
        errors.extend(ConfigValidator._validate_security_config(settings))
        
        # Validate monitoring configuration
        warnings.extend(ConfigValidator._validate_monitoring_config(settings))
        
        return {
            "errors": errors,
            "warnings": warnings,
            "valid": len(errors) == 0
        }
    
    @staticmethod
    def _validate_service_identity(settings: MicroserviceSettings) -> List[str]:
        """Validate service identity configuration"""
        errors = []
        
        if not settings.service_name or len(settings.service_name.strip()) == 0:
            errors.append("Service name is required and cannot be empty")
        
        if not re.match(r'^[a-z0-9-]+$', settings.service_name):
            errors.append("Service name must contain only lowercase letters, numbers, and hyphens")
        
        if settings.service_port < 1024 or settings.service_port > 65535:
            errors.append("Service port must be between 1024 and 65535")
        
        return errors
    
    @staticmethod
    def _validate_database_config(settings: MicroserviceSettings) -> List[str]:
        """Validate database configuration"""
        errors = []
        
        if not settings.postgres_host:
            errors.append("PostgreSQL host is required")
        
        if not settings.postgres_user:
            errors.append("PostgreSQL user is required")
        
        if not settings.postgres_password:
            errors.append("PostgreSQL password is required")
        
        if not settings.postgres_db:
            errors.append("PostgreSQL database name is required")
        
        if settings.postgres_pool_size < 1:
            errors.append("PostgreSQL pool size must be at least 1")
        
        if settings.postgres_max_overflow < 0:
            errors.append("PostgreSQL max overflow must be non-negative")
        
        return errors
    
    @staticmethod
    def _validate_redis_config(settings: MicroserviceSettings) -> List[str]:
        """Validate Redis configuration"""
        errors = []
        
        if not settings.redis_host:
            errors.append("Redis host is required")
        
        if settings.redis_pool_size < 1:
            errors.append("Redis pool size must be at least 1")
        
        if settings.redis_timeout < 1:
            errors.append("Redis timeout must be at least 1 second")
        
        return errors
    
    @staticmethod
    def _validate_message_queue_config(settings: MicroserviceSettings) -> List[str]:
        """Validate message queue configuration"""
        errors = []
        
        if not settings.rabbitmq_host:
            errors.append("RabbitMQ host is required")
        
        if not settings.rabbitmq_user:
            errors.append("RabbitMQ user is required")
        
        if not settings.rabbitmq_password:
            errors.append("RabbitMQ password is required")
        
        return errors
    
    @staticmethod
    def _validate_service_discovery_config(settings: MicroserviceSettings) -> List[str]:
        """Validate service discovery configuration"""
        errors = []
        
        if not settings.consul_host:
            errors.append("Consul host is required")
        
        if settings.consul_port < 1 or settings.consul_port > 65535:
            errors.append("Consul port must be between 1 and 65535")
        
        return errors
    
    @staticmethod
    def _validate_security_config(settings: MicroserviceSettings) -> List[str]:
        """Validate security configuration"""
        errors = []
        
        if not settings.secret_key:
            errors.append("Secret key is required")
        
        if len(settings.secret_key) < 32:
            errors.append("Secret key must be at least 32 characters long")
        
        if settings.access_token_expire_minutes < 1:
            errors.append("Access token expiration must be at least 1 minute")
        
        return errors
    
    @staticmethod
    def _validate_monitoring_config(settings: MicroserviceSettings) -> List[str]:
        """Validate monitoring configuration"""
        warnings = []
        
        if not settings.jaeger_endpoint and settings.enable_tracing:
            warnings.append("Jaeger endpoint not configured but tracing is enabled")
        
        if settings.prometheus_port < 1024 or settings.prometheus_port > 65535:
            warnings.append("Prometheus port should be between 1024 and 65535")
        
        return warnings
    
    @staticmethod
    def validate_url(url: str, scheme: str = None) -> bool:
        """Validate URL format"""
        try:
            parsed = urlparse(url)
            if scheme and parsed.scheme != scheme:
                return False
            return bool(parsed.netloc)
        except Exception:
            return False
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """Validate port number"""
        return 1 <= port <= 65535
