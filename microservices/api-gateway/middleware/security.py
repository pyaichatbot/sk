# ============================================================================
# microservices/api-gateway/middleware/security.py
# ============================================================================
"""
Security middleware for API Gateway.
Handles authentication, authorization, and security headers.
"""

import time
import uuid
from typing import Dict, Any, Optional, List
from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt
import logging

from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for API Gateway"""
    
    def __init__(self, app, settings: MicroserviceSettings):
        super().__init__(app)
        self.settings = settings
        self.security = HTTPBearer(auto_error=False)
        self.excluded_paths = {
            "/health",
            "/health/ready",
            "/health/live",
            "/info",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
        self.rate_limit_cache: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware"""
        start_time = time.time()
        
        try:
            # Add request ID for tracking
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            
            # Add security headers
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            # Add CORS headers if needed
            if request.method == "OPTIONS":
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                response.headers["Access-Control-Max-Age"] = "86400"
            
            # Log request
            process_time = time.time() - start_time
            logger.info(
                f"Request processed",
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time=process_time,
                client_ip=request.client.host if request.client else None
            )
            
            return response
            
        except HTTPException as e:
            # Handle HTTP exceptions
            process_time = time.time() - start_time
            logger.warning(
                f"HTTP exception",
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=e.status_code,
                detail=e.detail,
                process_time=process_time
            )
            raise
            
        except Exception as e:
            # Handle unexpected exceptions
            process_time = time.time() - start_time
            logger.error(
                f"Unexpected error",
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                error=str(e),
                process_time=process_time
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": request_id,
                    "timestamp": time.time()
                }
            )

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for API Gateway"""
    
    def __init__(self, app, settings: MicroserviceSettings):
        super().__init__(app)
        self.settings = settings
        self.security = HTTPBearer(auto_error=False)
        self.excluded_paths = {
            "/health",
            "/health/ready",
            "/health/live",
            "/info",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through authentication middleware"""
        
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)
        
        try:
            # Extract token from request
            token = await self._extract_token(request)
            
            if not token:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Authentication required",
                        "message": "No authentication token provided"
                    }
                )
            
            # Validate token
            user_info = await self._validate_token(token)
            if not user_info:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Invalid token",
                        "message": "Authentication token is invalid or expired"
                    }
                )
            
            # Add user info to request state
            request.state.user = user_info
            
            return await call_next(request)
            
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "Authentication error",
                    "message": e.detail
                }
            )
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Authentication service error",
                    "message": "Internal authentication error"
                }
            )
    
    async def _extract_token(self, request: Request) -> Optional[str]:
        """Extract authentication token from request"""
        # Try Authorization header first
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            return authorization[7:]
        
        # Try query parameter
        token = request.query_params.get("token")
        if token:
            return token
        
        # Try cookie
        token = request.cookies.get("auth_token")
        if token:
            return token
        
        return None
    
    async def _validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token and return user info"""
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.algorithm]
            )
            
            # Check token expiration
            if "exp" in payload:
                if time.time() > payload["exp"]:
                    return None
            
            # Extract user info
            user_info = {
                "user_id": payload.get("sub"),
                "username": payload.get("username"),
                "email": payload.get("email"),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", []),
                "token": token
            }
            
            return user_info
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Authorization middleware for API Gateway"""
    
    def __init__(self, app, settings: MicroserviceSettings):
        super().__init__(app)
        self.settings = settings
        self.excluded_paths = {
            "/health",
            "/health/ready",
            "/health/live",
            "/info",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
        
        # Define role-based access control
        self.rbac_rules = {
            "/api/v1/chat": ["user", "admin"],
            "/api/v1/chat/stream": ["user", "admin"],
            "/api/v1/agents": ["admin"],
            "/api/v1/documents": ["user", "admin"],
            "/api/v1/orchestration": ["user", "admin"],
            "/api/v1/admin": ["admin"]
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through authorization middleware"""
        
        # Skip authorization for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)
        
        # Check if user is authenticated
        if not hasattr(request.state, 'user') or not request.state.user:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required",
                    "message": "User not authenticated"
                }
            )
        
        user = request.state.user
        user_roles = user.get("roles", [])
        
        # Check authorization for the requested path
        if not await self._check_authorization(request.url.path, user_roles):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Access denied",
                    "message": "Insufficient permissions for this resource"
                }
            )
        
        return await call_next(request)
    
    async def _check_authorization(self, path: str, user_roles: List[str]) -> bool:
        """Check if user has authorization for the requested path"""
        
        # Find matching RBAC rule
        for rule_path, required_roles in self.rbac_rules.items():
            if path.startswith(rule_path):
                # Check if user has any of the required roles
                if any(role in user_roles for role in required_roles):
                    return True
                return False
        
        # Default: allow access if no specific rule is defined
        return True

class InputValidationMiddleware(BaseHTTPMiddleware):
    """Input validation middleware for API Gateway"""
    
    def __init__(self, app, settings: MicroserviceSettings):
        super().__init__(app)
        self.settings = settings
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.allowed_content_types = {
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through input validation middleware"""
        
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request too large",
                    "message": f"Request size exceeds maximum allowed size of {self.max_request_size} bytes"
                }
            )
        
        # Check content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not any(ct in content_type for ct in self.allowed_content_types):
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": "Unsupported media type",
                        "message": f"Content type {content_type} is not supported"
                    }
                )
        
        # Validate request headers
        if not await self._validate_headers(request):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid headers",
                    "message": "Request contains invalid or malicious headers"
                }
            )
        
        return await call_next(request)
    
    async def _validate_headers(self, request: Request) -> bool:
        """Validate request headers for security"""
        
        # Check for suspicious headers
        suspicious_headers = [
            "x-forwarded-for",
            "x-real-ip",
            "x-originating-ip",
            "x-remote-ip",
            "x-remote-addr"
        ]
        
        for header_name in suspicious_headers:
            if header_name in request.headers:
                # Log suspicious header
                logger.warning(
                    f"Suspicious header detected",
                    header=header_name,
                    value=request.headers[header_name],
                    client_ip=request.client.host if request.client else None
                )
        
        # Check for SQL injection patterns in headers
        sql_patterns = ["'", '"', ";", "--", "/*", "*/", "xp_", "sp_"]
        for header_name, header_value in request.headers.items():
            if any(pattern in header_value.lower() for pattern in sql_patterns):
                logger.warning(
                    f"Potential SQL injection in header",
                    header=header_name,
                    value=header_value,
                    client_ip=request.client.host if request.client else None
                )
                return False
        
        return True
