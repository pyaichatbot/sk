# ============================================================================
# microservices/shared/config/observability_settings.py
# ============================================================================
"""
Enterprise Observability Configuration
=====================================

This module provides configuration management for observability features
in the microservices architecture, including intermediate messaging,
OpenTelemetry, and other monitoring capabilities.

Key Features:
- Configuration-driven observability features
- Environment-based feature toggles
- Local development support (optional features disabled by default)
- Production deployment configuration
- Comprehensive validation and error handling
"""

from pydantic import Field, validator
from pydantic_settings import BaseSettings
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import os
from pathlib import Path

class ObservabilityFeature(str, Enum):
    """Observability feature enumeration"""
    INTERMEDIATE_MESSAGING = "intermediate_messaging"
    OPENTELEMETRY = "opentelemetry"
    SK_TELEMETRY = "sk_telemetry"
    PROMETHEUS_GRAFANA = "prometheus_grafana"
    APM_INTEGRATION = "apm_integration"

class ObservabilityLevel(str, Enum):
    """Observability level enumeration"""
    DISABLED = "disabled"
    BASIC = "basic"
    STANDARD = "standard"
    ENHANCED = "enhanced"
    FULL = "full"

class ObservabilitySettings(BaseSettings):
    """
    Enterprise observability configuration settings
    
    This class manages all observability-related configuration options
    with proper validation and environment-based defaults.
    """
    
    # ============================================================================
    # MANDATORY FEATURES (Always Enabled)
    # ============================================================================
    
    # Intermediate Messaging (MANDATORY - Cannot be disabled)
    intermediate_messaging_enabled: bool = Field(
        default=True, 
        description="Enable intermediate messaging (MANDATORY - always enabled)"
    )
    
    # ============================================================================
    # OPTIONAL FEATURES (Configurable)
    # ============================================================================
    
    # OpenTelemetry Integration
    opentelemetry_enabled: bool = Field(
        default=False, 
        description="Enable OpenTelemetry integration (OPTIONAL)"
    )
    opentelemetry_endpoint: Optional[str] = Field(
        default=None, 
        description="OpenTelemetry collector endpoint"
    )
    opentelemetry_service_name: str = Field(
        default="enterprise-agentic-ai", 
        description="OpenTelemetry service name"
    )
    opentelemetry_service_version: str = Field(
        default="1.0.0", 
        description="OpenTelemetry service version"
    )
    opentelemetry_sampling_rate: float = Field(
        default=0.1, 
        ge=0.0, 
        le=1.0, 
        description="OpenTelemetry sampling rate"
    )
    
    # Semantic Kernel Telemetry
    sk_telemetry_enabled: bool = Field(
        default=False, 
        description="Enable Semantic Kernel specific telemetry (OPTIONAL)"
    )
    sk_telemetry_metrics_enabled: bool = Field(
        default=True, 
        description="Enable SK metrics collection"
    )
    sk_telemetry_logs_enabled: bool = Field(
        default=True, 
        description="Enable SK logs collection"
    )
    sk_telemetry_spans_enabled: bool = Field(
        default=True, 
        description="Enable SK spans collection"
    )
    
    # Prometheus/Grafana Integration
    prometheus_enabled: bool = Field(
        default=False, 
        description="Enable Prometheus metrics collection (OPTIONAL)"
    )
    prometheus_port: int = Field(
        default=9090, 
        ge=1024, 
        le=65535, 
        description="Prometheus metrics port"
    )
    prometheus_path: str = Field(
        default="/metrics", 
        description="Prometheus metrics endpoint path"
    )
    grafana_enabled: bool = Field(
        default=False, 
        description="Enable Grafana dashboards (OPTIONAL)"
    )
    grafana_port: int = Field(
        default=3000, 
        ge=1024, 
        le=65535, 
        description="Grafana port"
    )
    
    # APM Integration
    apm_enabled: bool = Field(
        default=False, 
        description="Enable Application Performance Monitoring (OPTIONAL)"
    )
    apm_provider: Optional[str] = Field(
        default=None, 
        description="APM provider (datadog, newrelic, azure_insights, etc.)"
    )
    apm_config: Dict[str, Any] = Field(
        default_factory=dict, 
        description="APM provider specific configuration"
    )
    
    # ============================================================================
    # INTERMEDIATE MESSAGING CONFIGURATION
    # ============================================================================
    
    # WebSocket Configuration
    websocket_max_connections: int = Field(
        default=100, 
        ge=1, 
        le=1000, 
        description="Maximum WebSocket connections"
    )
    websocket_timeout_seconds: int = Field(
        default=300, 
        ge=30, 
        le=3600, 
        description="WebSocket connection timeout"
    )
    websocket_heartbeat_interval: int = Field(
        default=30, 
        ge=5, 
        le=300, 
        description="WebSocket heartbeat interval"
    )
    
    # Event Configuration
    event_retention_hours: int = Field(
        default=24, 
        ge=1, 
        le=168, 
        description="Event retention period in hours"
    )
    max_events_per_session: int = Field(
        default=1000, 
        ge=100, 
        le=10000, 
        description="Maximum events per session"
    )
    event_batch_size: int = Field(
        default=100, 
        ge=10, 
        le=1000, 
        description="Event batch size for processing"
    )
    
    # Performance Configuration
    max_events_per_second: int = Field(
        default=100, 
        ge=1, 
        le=1000, 
        description="Maximum events per second"
    )
    enable_event_filtering: bool = Field(
        default=True, 
        description="Enable event filtering"
    )
    enable_rate_limiting: bool = Field(
        default=True, 
        description="Enable rate limiting"
    )
    
    # ============================================================================
    # CIRCUIT BREAKER CONFIGURATION
    # ============================================================================
    
    circuit_breaker_enabled: bool = Field(
        default=True, 
        description="Enable circuit breaker for error handling"
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5, 
        ge=1, 
        le=100, 
        description="Circuit breaker failure threshold"
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=60, 
        ge=10, 
        le=600, 
        description="Circuit breaker recovery timeout in seconds"
    )
    circuit_breaker_success_threshold: int = Field(
        default=3, 
        ge=1, 
        le=20, 
        description="Circuit breaker success threshold"
    )
    
    # ============================================================================
    # SECURITY CONFIGURATION
    # ============================================================================
    
    websocket_authentication_enabled: bool = Field(
        default=True, 
        description="Enable WebSocket authentication"
    )
    websocket_authorization_enabled: bool = Field(
        default=True, 
        description="Enable WebSocket authorization"
    )
    allowed_websocket_origins: List[str] = Field(
        default_factory=lambda: ["*"], 
        description="Allowed WebSocket origins"
    )
    
    # ============================================================================
    # ENVIRONMENT CONFIGURATION
    # ============================================================================
    
    environment: str = Field(
        default="development", 
        description="Environment (development, staging, production)"
    )
    observability_level: ObservabilityLevel = Field(
        default=ObservabilityLevel.BASIC, 
        description="Overall observability level"
    )
    
    # ============================================================================
    # VALIDATION AND COMPUTED PROPERTIES
    # ============================================================================
    
    @validator('environment')
    def validate_environment(cls, v):
        """Validate environment setting"""
        valid_environments = ['development', 'staging', 'production']
        if v not in valid_environments:
            raise ValueError(f'Environment must be one of: {valid_environments}')
        return v
    
    @validator('observability_level', pre=True)
    def validate_observability_level(cls, v):
        """Validate observability level"""
        if isinstance(v, str):
            return ObservabilityLevel(v.lower())
        return v
    
    @validator('opentelemetry_enabled')
    def validate_opentelemetry_config(cls, v, values):
        """Validate OpenTelemetry configuration"""
        if v and not values.get('opentelemetry_endpoint'):
            # In development, allow OpenTelemetry without endpoint
            if values.get('environment') != 'development':
                raise ValueError('OpenTelemetry endpoint is required when OpenTelemetry is enabled')
        return v
    
    @validator('apm_enabled')
    def validate_apm_config(cls, v, values):
        """Validate APM configuration"""
        if v and not values.get('apm_provider'):
            raise ValueError('APM provider is required when APM is enabled')
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == 'development'
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == 'production'
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment"""
        return self.environment == 'staging'
    
    @property
    def enabled_features(self) -> List[ObservabilityFeature]:
        """Get list of enabled observability features"""
        features = []
        
        # Intermediate messaging is always enabled (MANDATORY)
        features.append(ObservabilityFeature.INTERMEDIATE_MESSAGING)
        
        # Optional features
        if self.opentelemetry_enabled:
            features.append(ObservabilityFeature.OPENTELEMETRY)
        
        if self.sk_telemetry_enabled:
            features.append(ObservabilityFeature.SK_TELEMETRY)
        
        if self.prometheus_enabled or self.grafana_enabled:
            features.append(ObservabilityFeature.PROMETHEUS_GRAFANA)
        
        if self.apm_enabled:
            features.append(ObservabilityFeature.APM_INTEGRATION)
        
        return features
    
    @property
    def disabled_features(self) -> List[ObservabilityFeature]:
        """Get list of disabled observability features"""
        all_features = list(ObservabilityFeature)
        return [feature for feature in all_features if feature not in self.enabled_features]
    
    def get_feature_config(self, feature: ObservabilityFeature) -> Dict[str, Any]:
        """Get configuration for a specific feature"""
        configs = {
            ObservabilityFeature.INTERMEDIATE_MESSAGING: {
                "enabled": self.intermediate_messaging_enabled,
                "websocket_max_connections": self.websocket_max_connections,
                "websocket_timeout_seconds": self.websocket_timeout_seconds,
                "event_retention_hours": self.event_retention_hours,
                "max_events_per_session": self.max_events_per_session,
                "max_events_per_second": self.max_events_per_second,
                "enable_event_filtering": self.enable_event_filtering,
                "enable_rate_limiting": self.enable_rate_limiting,
                "circuit_breaker_enabled": self.circuit_breaker_enabled,
                "circuit_breaker_failure_threshold": self.circuit_breaker_failure_threshold,
                "circuit_breaker_recovery_timeout": self.circuit_breaker_recovery_timeout,
                "circuit_breaker_success_threshold": self.circuit_breaker_success_threshold,
                "websocket_authentication_enabled": self.websocket_authentication_enabled,
                "websocket_authorization_enabled": self.websocket_authorization_enabled,
                "allowed_websocket_origins": self.allowed_websocket_origins
            },
            ObservabilityFeature.OPENTELEMETRY: {
                "enabled": self.opentelemetry_enabled,
                "endpoint": self.opentelemetry_endpoint,
                "service_name": self.opentelemetry_service_name,
                "service_version": self.opentelemetry_service_version,
                "sampling_rate": self.opentelemetry_sampling_rate
            },
            ObservabilityFeature.SK_TELEMETRY: {
                "enabled": self.sk_telemetry_enabled,
                "metrics_enabled": self.sk_telemetry_metrics_enabled,
                "logs_enabled": self.sk_telemetry_logs_enabled,
                "spans_enabled": self.sk_telemetry_spans_enabled
            },
            ObservabilityFeature.PROMETHEUS_GRAFANA: {
                "prometheus_enabled": self.prometheus_enabled,
                "prometheus_port": self.prometheus_port,
                "prometheus_path": self.prometheus_path,
                "grafana_enabled": self.grafana_enabled,
                "grafana_port": self.grafana_port
            },
            ObservabilityFeature.APM_INTEGRATION: {
                "enabled": self.apm_enabled,
                "provider": self.apm_provider,
                "config": self.apm_config
            }
        }
        return configs.get(feature, {})
    
    def to_environment_variables(self) -> Dict[str, str]:
        """Convert settings to environment variables format"""
        env_vars = {}
        
        # Mandatory features
        env_vars["OBSERVABILITY_INTERMEDIATE_MESSAGING_ENABLED"] = str(self.intermediate_messaging_enabled)
        
        # Optional features
        env_vars["OBSERVABILITY_OPENTELEMETRY_ENABLED"] = str(self.opentelemetry_enabled)
        env_vars["OBSERVABILITY_SK_TELEMETRY_ENABLED"] = str(self.sk_telemetry_enabled)
        env_vars["OBSERVABILITY_PROMETHEUS_ENABLED"] = str(self.prometheus_enabled)
        env_vars["OBSERVABILITY_GRAFANA_ENABLED"] = str(self.grafana_enabled)
        env_vars["OBSERVABILITY_APM_ENABLED"] = str(self.apm_enabled)
        
        # Environment
        env_vars["OBSERVABILITY_ENVIRONMENT"] = self.environment
        env_vars["OBSERVABILITY_LEVEL"] = self.observability_level.value
        
        return env_vars
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "OBSERVABILITY_"

# Global settings instance
_observability_settings: Optional[ObservabilitySettings] = None

def get_observability_settings() -> ObservabilitySettings:
    """Get the global observability settings instance"""
    global _observability_settings
    if _observability_settings is None:
        _observability_settings = ObservabilitySettings()
    return _observability_settings

def set_observability_settings(settings: ObservabilitySettings) -> None:
    """Set the global observability settings instance"""
    global _observability_settings
    _observability_settings = settings

def create_development_settings() -> ObservabilitySettings:
    """Create development-optimized observability settings"""
    return ObservabilitySettings(
        environment="development",
        observability_level=ObservabilityLevel.BASIC,
        
        # Mandatory features (always enabled)
        intermediate_messaging_enabled=True,
        
        # Optional features (disabled for local development)
        opentelemetry_enabled=False,
        sk_telemetry_enabled=False,
        prometheus_enabled=False,
        grafana_enabled=False,
        apm_enabled=False,
        
        # Development-optimized settings
        websocket_max_connections=10,
        event_retention_hours=1,
        max_events_per_session=100,
        max_events_per_second=10,
        circuit_breaker_failure_threshold=3,
        circuit_breaker_recovery_timeout=30
    )

def create_production_settings() -> ObservabilitySettings:
    """Create production-optimized observability settings"""
    return ObservabilitySettings(
        environment="production",
        observability_level=ObservabilityLevel.FULL,
        
        # Mandatory features (always enabled)
        intermediate_messaging_enabled=True,
        
        # Optional features (enabled for production)
        opentelemetry_enabled=True,
        sk_telemetry_enabled=True,
        prometheus_enabled=True,
        grafana_enabled=True,
        apm_enabled=True,
        
        # Production-optimized settings
        websocket_max_connections=1000,
        event_retention_hours=168,  # 7 days
        max_events_per_session=10000,
        max_events_per_second=1000,
        circuit_breaker_failure_threshold=10,
        circuit_breaker_recovery_timeout=120,
        websocket_authentication_enabled=True,
        websocket_authorization_enabled=True,
        allowed_websocket_origins=["https://yourdomain.com"]
    )

def create_staging_settings() -> ObservabilitySettings:
    """Create staging-optimized observability settings"""
    return ObservabilitySettings(
        environment="staging",
        observability_level=ObservabilityLevel.ENHANCED,
        
        # Mandatory features (always enabled)
        intermediate_messaging_enabled=True,
        
        # Optional features (selectively enabled for staging)
        opentelemetry_enabled=True,
        sk_telemetry_enabled=True,
        prometheus_enabled=True,
        grafana_enabled=False,  # Disable Grafana in staging
        apm_enabled=False,      # Disable APM in staging
        
        # Staging-optimized settings
        websocket_max_connections=100,
        event_retention_hours=24,
        max_events_per_session=1000,
        max_events_per_second=100,
        circuit_breaker_failure_threshold=5,
        circuit_breaker_recovery_timeout=60
    )
