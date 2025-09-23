# ============================================================================
# microservices/api-gateway/middleware/logging_middleware.py
# ============================================================================
"""
Logging middleware for API Gateway.
"""

import time
import uuid
import json
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import structlog

from shared.config.settings import MicroserviceSettings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware for API Gateway"""
    
    def __init__(self, app, settings: MicroserviceSettings):
        super().__init__(app)
        self.settings = settings
        self.excluded_paths = {
            "/health",
            "/health/ready",
            "/health/live",
            "/info"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through logging middleware"""
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Log request start
        await self._log_request_start(request, request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log request completion
            await self._log_request_completion(request, response, request_id, process_time)
            
            return response
            
        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log request error
            await self._log_request_error(request, e, request_id, process_time)
            
            raise
    
    async def _log_request_start(self, request: Request, request_id: str) -> None:
        """Log request start"""
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return
        
        # Extract request information
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        content_length = request.headers.get("content-length", "0")
        
        # Get user information if available
        user_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('user_id')
        
        # Log request
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query_params=dict(request.query_params),
            client_ip=client_ip,
            user_agent=user_agent,
            content_length=content_length,
            user_id=user_id,
            headers=self._sanitize_headers(request.headers)
        )
    
    async def _log_request_completion(
        self, 
        request: Request, 
        response: Response, 
        request_id: str, 
        process_time: float
    ) -> None:
        """Log request completion"""
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return
        
        # Extract response information
        status_code = response.status_code
        content_length = response.headers.get("content-length", "0")
        
        # Get user information if available
        user_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('user_id')
        
        # Determine log level based on status code
        if status_code >= 500:
            log_level = "error"
        elif status_code >= 400:
            log_level = "warning"
        else:
            log_level = "info"
        
        # Log response
        getattr(logger, log_level)(
            "Request completed",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            status_code=status_code,
            process_time=process_time,
            content_length=content_length,
            user_id=user_id,
            response_headers=self._sanitize_headers(response.headers)
        )
    
    async def _log_request_error(
        self, 
        request: Request, 
        error: Exception, 
        request_id: str, 
        process_time: float
    ) -> None:
        """Log request error"""
        # Extract error information
        error_type = type(error).__name__
        error_message = str(error)
        
        # Get user information if available
        user_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('user_id')
        
        # Log error
        logger.error(
            "Request error",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            error_type=error_type,
            error_message=error_message,
            process_time=process_time,
            user_id=user_id,
            exc_info=True
        )
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize headers for logging"""
        sensitive_headers = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
            "x-access-token"
        }
        
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Audit logging middleware for API Gateway"""
    
    def __init__(self, app, settings: MicroserviceSettings):
        super().__init__(app)
        self.settings = settings
        self.audit_logger = structlog.get_logger("audit")
        
        # Define audit-worthy endpoints
        self.audit_endpoints = {
            "/api/v1/chat",
            "/api/v1/chat/stream",
            "/api/v1/agents",
            "/api/v1/documents",
            "/api/v1/orchestration"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through audit logging middleware"""
        
        # Check if endpoint requires audit logging
        if not any(request.url.path.startswith(path) for path in self.audit_endpoints):
            return await call_next(request)
        
        # Get user information
        user_id = None
        username = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('user_id')
            username = request.state.user.get('username')
        
        # Log audit event
        self.audit_logger.info(
            "API access",
            request_id=getattr(request.state, 'request_id', None),
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            user_id=user_id,
            username=username,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", ""),
            timestamp=time.time()
        )
        
        return await call_next(request)
