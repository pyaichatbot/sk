# ============================================================================
# microservices/api-gateway/middleware/rate_limiting.py
# ============================================================================
"""
Rate limiting middleware for API Gateway.
"""

import time
import asyncio
from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

from shared.infrastructure.redis import RedisManager
from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for API Gateway"""
    
    def __init__(self, app, redis_manager: RedisManager, settings: MicroserviceSettings):
        super().__init__(app)
        self.redis_manager = redis_manager
        self.settings = settings
        self.excluded_paths = {
            "/health",
            "/health/ready",
            "/health/live",
            "/info"
        }
        
        # Rate limiting configuration
        self.default_rate_limit = settings.rate_limit_requests
        self.default_burst = settings.rate_limit_burst
        self.window_size = 60  # 1 minute window
        
        # Rate limiting rules per endpoint
        self.rate_limit_rules = {
            "/api/v1/chat": {"requests": 10, "burst": 20},
            "/api/v1/chat/stream": {"requests": 5, "burst": 10},
            "/api/v1/agents": {"requests": 20, "burst": 40},
            "/api/v1/documents": {"requests": 15, "burst": 30},
            "/api/v1/orchestration": {"requests": 10, "burst": 20}
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting middleware"""
        
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)
        
        try:
            # Get client identifier
            client_id = await self._get_client_id(request)
            
            # Get rate limit for the endpoint
            rate_limit = await self._get_rate_limit(request.url.path)
            
            # Check rate limit
            if not await self._check_rate_limit(client_id, request.url.path, rate_limit):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Limit: {rate_limit['requests']} requests per minute",
                        "retry_after": 60
                    },
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(rate_limit["requests"]),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + 60)
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            remaining = await self._get_remaining_requests(client_id, request.url.path, rate_limit)
            response.headers["X-RateLimit-Limit"] = str(rate_limit["requests"])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting middleware error: {e}")
            # Continue without rate limiting if there's an error
            return await call_next(request)
    
    async def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get user ID from request state (if authenticated)
        if hasattr(request.state, 'user') and request.state.user:
            return f"user:{request.state.user.get('user_id', 'anonymous')}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    async def _get_rate_limit(self, path: str) -> Dict[str, int]:
        """Get rate limit configuration for the endpoint"""
        # Find matching rule
        for rule_path, limit in self.rate_limit_rules.items():
            if path.startswith(rule_path):
                return limit
        
        # Return default rate limit
        return {
            "requests": self.default_rate_limit,
            "burst": self.default_burst
        }
    
    async def _check_rate_limit(self, client_id: str, path: str, rate_limit: Dict[str, int]) -> bool:
        """Check if client has exceeded rate limit"""
        if not self.redis_manager:
            # If Redis is not available, allow the request
            return True
        
        try:
            # Create rate limit key
            key = f"rate_limit:{client_id}:{path}"
            current_time = int(time.time())
            window_start = current_time - self.window_size
            
            # Use Redis sorted set for sliding window rate limiting
            pipe = self.redis_manager.client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, self.window_size)
            
            results = await pipe.execute()
            current_requests = results[1]
            
            # Check if limit exceeded
            return current_requests < rate_limit["requests"]
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Allow request if rate limiting fails
            return True
    
    async def _get_remaining_requests(self, client_id: str, path: str, rate_limit: Dict[str, int]) -> int:
        """Get remaining requests for client"""
        if not self.redis_manager:
            return rate_limit["requests"]
        
        try:
            key = f"rate_limit:{client_id}:{path}"
            current_time = int(time.time())
            window_start = current_time - self.window_size
            
            # Count current requests in window
            current_requests = await self.redis_manager.client.zcount(key, window_start, current_time)
            
            return max(0, rate_limit["requests"] - current_requests)
            
        except Exception as e:
            logger.error(f"Get remaining requests error: {e}")
            return rate_limit["requests"]
