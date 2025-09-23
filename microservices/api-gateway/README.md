# API Gateway Service

## Overview
The API Gateway serves as the single entry point for all client requests to the microservices architecture. It handles routing, authentication, rate limiting, and request/response transformation.

## Responsibilities
- **Request Routing**: Route requests to appropriate microservices
- **Authentication & Authorization**: Validate JWT tokens and enforce access control
- **Rate Limiting**: Implement per-user and per-endpoint rate limiting
- **Load Balancing**: Distribute requests across service instances
- **API Versioning**: Handle multiple API versions
- **Request/Response Transformation**: Modify requests and responses as needed
- **Monitoring**: Collect metrics and logs for all requests

## Architecture
```
Client Request → API Gateway → Service Discovery → Target Service
                ↓
            Rate Limiting
                ↓
            Authentication
                ↓
            Request Routing
                ↓
            Load Balancing
```

## Configuration
- **Port**: 8000 (configurable)
- **Authentication**: JWT-based with configurable secret
- **Rate Limiting**: Redis-backed with configurable limits
- **Service Discovery**: Consul integration
- **Load Balancing**: Round-robin with health checks

## Endpoints
- `/api/v1/health` - Health check
- `/api/v1/chat` - Chat orchestration
- `/api/v1/chat/stream` - Streaming chat
- `/api/v1/agents/*` - Agent management
- `/api/v1/documents/*` - Document management
- `/api/v1/orchestration/*` - Orchestration management

## Dependencies
- Redis (for rate limiting and caching)
- Consul (for service discovery)
- Target microservices (orchestration, agents)
