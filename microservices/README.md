# Microservices Architecture

This directory contains the decomposed microservices from the monolithic Enterprise Agentic AI System.

## Service Architecture

```
microservices/
├── shared/                          # Shared infrastructure and utilities
│   ├── config/                      # Common configuration
│   ├── infrastructure/              # Shared infrastructure components
│   ├── models/                      # Common data models
│   └── utils/                       # Shared utilities
├── api-gateway/                     # API Gateway Service
├── orchestration/                   # Orchestration Service
├── agents/
│   ├── rag-agent/                   # RAG Agent Service
│   ├── search-agent/                # Search Agent Service
│   ├── jira-agent/                  # JIRA Agent Service
│   └── llm-agent/                   # LLM Agent Service
└── docker/                          # Microservices Docker configurations
```

## Service Responsibilities

### API Gateway Service
- Request routing and load balancing
- Authentication and authorization
- Rate limiting and throttling
- API versioning and documentation
- Request/response transformation

### Orchestration Service
- Agent coordination and workflow management
- Orchestration pattern execution
- Session management
- Result aggregation and streaming
- Agent health monitoring

### Agent Services
Each agent service is responsible for:
- Specific domain functionality
- Plugin management
- Health checks and metrics
- Configuration management
- Error handling and logging

### Shared Infrastructure
- Common configuration management
- Shared data models and DTOs
- Infrastructure utilities (logging, monitoring, etc.)
- Database connection management
- Security utilities

## Communication Patterns

- **Synchronous**: HTTP/REST for request-response patterns
- **Asynchronous**: Message queues for event-driven communication
- **Streaming**: WebSocket/SSE for real-time data streaming
- **Service Discovery**: Consul/Kubernetes for service registration

## Deployment Strategy

- **Containerization**: Each service runs in its own Docker container
- **Orchestration**: Kubernetes for container orchestration
- **Service Mesh**: Istio for service-to-service communication
- **Monitoring**: Prometheus/Grafana for metrics and observability
