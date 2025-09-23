# ============================================================================
# microservices/shared/config/settings.py
# ============================================================================
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from typing import Dict, List, Optional, Any
from enum import Enum
import os
from pathlib import Path

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class MicroserviceSettings(BaseSettings):
    """Base settings for all microservices"""
    
    # Service Identity
    service_name: str = Field(default="orchestration-service", description="Name of the microservice")
    service_version: str = Field(default="1.0.0", description="Service version")
    service_port: int = Field(default=8000, description="Service port")
    service_host: str = Field(default="0.0.0.0", description="Service host")
    
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="Environment")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Logging
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    log_file_path: Optional[Path] = Field(default=None, description="Log file path")
    
    # Security
    secret_key: str = Field(default="development-secret-key-change-in-production", description="Secret key for JWT tokens")
    access_token_expire_minutes: int = Field(default=60, description="Access token expiration")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    
    # Database
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(default="orchestration_user", description="PostgreSQL user")
    postgres_password: str = Field(default="orchestration_password", description="PostgreSQL password")
    postgres_db: str = Field(default="orchestration_db", description="PostgreSQL database name")
    postgres_pool_size: int = Field(default=10, description="PostgreSQL pool size")
    postgres_max_overflow: int = Field(default=20, description="PostgreSQL max overflow")
    
    # Redis
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_pool_size: int = Field(default=10, description="Redis pool size")
    redis_timeout: int = Field(default=5, description="Redis timeout")
    
    # Service Discovery
    consul_host: str = Field(default="localhost", description="Consul host")
    consul_port: int = Field(default=8500, description="Consul port")
    consul_token: Optional[str] = Field(default=None, description="Consul token")
    
    # Message Queue
    rabbitmq_host: str = Field(default="localhost", description="RabbitMQ host")
    rabbitmq_port: int = Field(default=5672, description="RabbitMQ port")
    rabbitmq_user: str = Field(default="guest", description="RabbitMQ user")
    rabbitmq_password: str = Field(default="guest", description="RabbitMQ password")
    rabbitmq_vhost: str = Field(default="/", description="RabbitMQ virtual host")
    
    # Monitoring
    jaeger_endpoint: Optional[str] = Field(default=None, description="Jaeger endpoint")
    prometheus_port: int = Field(default=9090, description="Prometheus metrics port")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_tracing: bool = Field(default=True, description="Enable distributed tracing")
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100, description="Rate limit requests per minute")
    rate_limit_burst: int = Field(default=200, description="Rate limit burst capacity")
    
    # Health Checks
    health_check_interval: int = Field(default=30, description="Health check interval in seconds")
    health_check_timeout: int = Field(default=10, description="Health check timeout in seconds")
    
    @validator('environment', pre=True)
    def validate_environment(cls, v):
        if isinstance(v, str):
            return Environment(v.lower())
        return v
    
    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def redis_url(self) -> str:
        """Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def rabbitmq_url(self) -> str:
        """RabbitMQ connection URL"""
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}{self.rabbitmq_vhost}"
    
    @property
    def consul_url(self) -> str:
        """Consul connection URL"""
        return f"http://{self.consul_host}:{self.consul_port}"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == Environment.DEVELOPMENT
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Global settings instance
_service_settings: Optional[MicroserviceSettings] = None

def get_service_settings() -> MicroserviceSettings:
    """Get the global service settings instance"""
    global _service_settings
    if _service_settings is None:
        _service_settings = MicroserviceSettings()
    return _service_settings

def set_service_settings(settings: MicroserviceSettings) -> None:
    """Set the global service settings instance"""
    global _service_settings
    _service_settings = settings
