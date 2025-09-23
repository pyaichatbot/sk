# Orchestration Service

## Overview
The Orchestration Service is responsible for coordinating multiple agents to execute complex workflows. It manages agent communication, workflow execution, and result aggregation.

## Responsibilities
- **Agent Coordination**: Manage communication between different agents
- **Workflow Execution**: Execute orchestration patterns (sequential, concurrent, handoff, group chat, dynamic)
- **Session Management**: Maintain conversation context and session state
- **Result Aggregation**: Combine and synthesize results from multiple agents
- **Streaming Support**: Provide real-time streaming of orchestration steps
- **Error Handling**: Manage failures and provide fallback mechanisms
- **Performance Monitoring**: Track orchestration metrics and performance

## Architecture
```
API Gateway → Orchestration Service → Agent Services
                ↓
            Session Management
                ↓
            Pattern Execution
                ↓
            Result Aggregation
```

## Orchestration Patterns
- **Sequential**: Execute agents one after another
- **Concurrent**: Execute multiple agents simultaneously
- **Handoff**: Dynamic agent selection based on context
- **Group Chat**: Collaborative agent discussion
- **Dynamic**: LLM-determined orchestration strategy

## Configuration
- **Port**: 8001 (configurable)
- **Session Storage**: Redis-backed session management
- **Agent Discovery**: Service discovery integration
- **Timeout**: Configurable request timeouts
- **Max Iterations**: Configurable iteration limits

## Dependencies
- Redis (for session management)
- Service Discovery (for agent discovery)
- Agent Services (RAG, Search, JIRA, LLM)
- Message Queue (for async communication)

## API Endpoints
- `POST /orchestrate` - Execute orchestration
- `POST /orchestrate/stream` - Streaming orchestration
- `GET /sessions/{session_id}` - Get session details
- `DELETE /sessions/{session_id}` - Delete session
- `GET /patterns` - List available patterns
- `GET /health` - Health check
