# Copilot Instructions for Agentic AI Enterprise System

## Project Overview
This codebase implements a modular, multi-agent orchestration system for enterprise AI workflows, exposed via a FastAPI service (`src/api/main.py`). Agents (LLM, RAG, Search, Jira) are coordinated by the `EnterpriseOrchestrator` in `src/orchestration/orchestration.py`. The API supports orchestration patterns: sequential, concurrent, handoff, group chat, and dynamic, with both synchronous and SSE streaming endpoints.

- **Containerization**: The system is containerized using Docker Compose (`docker/docker-compose.yml`). Services include the main app, PostgreSQL, Redis, Milvus (vector DB), monitoring (Prometheus, Grafana), and Jaeger for tracing. All services run on a shared network and use persistent volumes.
- **API Layer**: FastAPI app in `src/api/main.py` exposes endpoints for chat, streaming, document management, agent metrics, and system health. SSE streaming is used for real-time agent responses.
- **Agents**: Defined in `src/agents/`. Each agent (e.g., `LLMAgent`, `SearchAgent`, `JiraAgent`, `RAGAgent`) inherits from `BaseEnterpriseAgent` and implements async `invoke` (and optionally `invoke_stream`).
- **Orchestration**: The orchestrator manages agent execution, session threads, and result aggregation. Patterns are selected via the `OrchestrationPattern` enum and invoked via API requests.
- **Document Store**: RAG agent uses `DocumentStore` from `src/infrastructure/storage/document_store.py` for retrieval-augmented generation and document search/upload endpoints.
- **Observability**: Logging is centralized via `get_logger` from `src/infrastructure/observability/logging.py`.
- **Redis Integration**: Redis is used for rate limiting and session management (see `settings.redis_url`).

- **Containerized Development**: Use `docker-compose up --build` from the `docker/` directory to start all services. The main app is exposed on port 8000. Service health and dependencies are managed via Compose.
- **Async-first**: All agent invocations, orchestration flows, and API endpoints are async. Use `await` for all agent calls.
- **Run API**: Start the FastAPI server with `python src/api/main.py` or via Uvicorn (see entry point at file bottom).
- **Streaming**: Use `/api/v1/chat/stream` for SSE streaming responses; `/api/v1/chat` for synchronous.
- **Debugging**: Use the logging system for tracing agent, orchestration, and API activity. Adjust log levels in `logging.py` and via `settings.log_level`.
- **Session Management**: Sessions are tracked by `session_id` and managed in orchestrator and Redis.
- **Rate Limiting**: Controlled via Redis and `settings.rate_limit_requests`.
- **Document Management**: Upload/search/list/remove documents via `/api/v1/documents/*` endpoints.
- **Agent Metrics & Health**: Use `/api/v1/agents/metrics` and `/api/v1/health` endpoints for monitoring.

**Docker Cleanup**: To free disk space and remove old resources, use:
	- `docker buildx prune -a -f --filter until=168h` (remove old build cache)
	- `docker volume ls -qf dangling=true | xargs -r docker volume rm` (remove dangling volumes)
	- `docker system df -v` (show disk usage)

## Project Conventions
- **Agent Registration**: Agents are registered in orchestrator's `_initialize_agents`. To add a new agent, implement in `src/agents/` and register here.
- **Orchestration Patterns**: Select pattern via `OrchestrationRequest.pattern` (API: `orchestration_pattern`). Patterns are extensible via `OrchestrationPattern` enum.
- **Error Handling**: Errors are captured in orchestration steps and API handlers, returned as structured error responses.
- **Data Flow**: Agent responses are passed between steps; in sequential mode, output of one agent becomes input for the next. API models are defined in `src/api/main.py`.

- **Databases**: Integrates with PostgreSQL (relational), Redis (cache/rate limiting), and Milvus (vector DB). Connection details are set via environment variables in Compose and `settings.py`.
- **External Services**: Agents may integrate with external APIs (e.g., Jira, web search, LLMs). Configure credentials and endpoints in agent constructors or config files.
- **Redis**: Used for rate limiting and session management. Configure via `settings.redis_url`.
- **Extensibility**: New agents, orchestration patterns, or plugins can be added by following the structure in `src/agents/` and updating orchestrator and API models.

## Example: Adding a New Agent
1. Create `src/agents/my_agent.py` inheriting from `BaseEnterpriseAgent`.
2. Implement async `invoke` and (optionally) `invoke_stream` methods.
3. Register in `EnterpriseOrchestrator._initialize_agents`.
4. Update orchestration logic and API models if needed.

- `docker/docker-compose.yml`: Multi-service container orchestration
- `src/api/main.py`: FastAPI app, API endpoints, SSE streaming
- `src/agents/`: Agent implementations
- `src/orchestration/orchestration.py`: Orchestrator logic
- `src/infrastructure/storage/document_store.py`: Document storage for RAG
- `src/infrastructure/observability/logging.py`: Logging utilities
- `src/plugins/`: Optional plugins for extended functionality

---
_If any section is unclear or missing details (e.g., testing, build commands, API usage), please provide feedback or point to relevant files to improve these instructions._
