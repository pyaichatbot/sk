# GitLab Agent Service

A GitLab agent microservice built using Microsoft Semantic Kernel agent template approach for project management, issue tracking, and repository operations.

## 🎯 **Features**

- **Project Management**: Query and retrieve GitLab project information
- **Issue Tracking**: Access and filter project issues with various criteria
- **Merge Request Management**: Handle merge requests and their states
- **User Management**: Get current user information and profiles
- **Templated Instructions**: Dynamic agent behavior based on context
- **Streaming Support**: Real-time response streaming
- **RESTful API**: Comprehensive API endpoints for GitLab operations

## 🏗️ **Architecture**

Based on Microsoft Semantic Kernel agent template approach:

- **ChatCompletionAgent**: Core agent using templated instructions
- **GitLab Plugin**: Custom plugin for GitLab API integration
- **FastAPI**: RESTful API with comprehensive endpoints
- **Docker**: Containerized deployment
- **Shared Infrastructure**: Common models, logging, and configuration

## 🚀 **Quick Start**

### **Prerequisites**

- Python 3.11+
- Docker (optional)
- GitLab instance access
- GitLab access token

### **Environment Variables**

```bash
# GitLab Configuration
GITLAB_URL=https://gitlab.com  # or your GitLab instance
GITLAB_ACCESS_TOKEN=your_gitlab_token

# Service Configuration
SERVICE_NAME=gitlab-agent
SERVICE_PORT=8007
POSTGRES_HOST=localhost
REDIS_HOST=localhost
CONSUL_HOST=localhost
```

### **Local Development**

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py
```

### **Docker Deployment**

```bash
# Build the image
docker build -t gitlab-agent:latest .

# Run the container
docker run -p 8007:8007 \
  -e GITLAB_URL=https://gitlab.com \
  -e GITLAB_ACCESS_TOKEN=your_token \
  gitlab-agent:latest
```

## 📡 **API Endpoints**

### **Core Endpoints**

- `GET /health` - Health check
- `GET /capabilities` - Agent capabilities
- `POST /invoke` - Invoke agent with request

### **GitLab-Specific Endpoints**

- `GET /gitlab/user` - Get current user information
- `GET /gitlab/projects/{project_id}` - Get project information
- `GET /gitlab/projects/{project_id}/issues` - Get project issues
- `GET /gitlab/projects/{project_id}/merge_requests` - Get merge requests

### **Example Usage**

```python
import requests

# Get current user
response = requests.get("http://localhost:8007/gitlab/user")
user_info = response.json()

# Get project issues
response = requests.get("http://localhost:8007/gitlab/projects/my-group/my-project/issues")
issues = response.json()

# Invoke agent
response = requests.post("http://localhost:8007/invoke", json={
    "input": "Show me all open issues for project my-group/my-project",
    "user_id": "user123",
    "session_id": "session456"
})
agent_response = response.json()
```

## 🔧 **Configuration**

### **GitLab Settings**

The agent uses `GitLabSettings` for configuration:

```python
@dataclass
class GitLabSettings:
    gitlab_url: str          # GitLab instance URL
    access_token: str        # GitLab access token
    api_version: str = "v4"  # GitLab API version
```

### **Agent Capabilities**

```python
capabilities = AgentCapabilities(
    agent_name="GitLabAgent",
    capabilities=[
        "gitlab_integration",
        "project_management", 
        "issue_tracking",
        "merge_request_management",
        "repository_operations"
    ],
    input_formats=["text", "json"],
    output_formats=["text", "json"],
    max_input_size=10000,
    rate_limit=50,
    timeout=30
)
```

## 🎨 **Templated Instructions**

The agent uses templated instructions for dynamic behavior:

```python
instructions = """
You are a GitLab agent designed to query and retrieve information from GitLab repositories and projects.

The GitLab instance you are querying is: {{$gitlab_url}}
The current date and time is: {{$now}}.

When providing information about issues or merge requests, always include:
- Title and description
- Current state (opened/closed/merged)
- Author and assignee information
- Creation and update dates
- Web URL for direct access
- Labels (for issues)
- Source and target branches (for merge requests)
"""
```

## 🔌 **GitLab Plugin**

The `GitLabPlugin` provides comprehensive GitLab API integration:

### **Available Methods**

- `get_current_user()` - Get authenticated user
- `get_project(project_id)` - Get project information
- `get_project_issues(project_id, ...)` - Get project issues with filtering
- `get_project_merge_requests(project_id, ...)` - Get merge requests
- `search_projects(search)` - Search for projects
- `get_issue(project_id, issue_id)` - Get specific issue
- `get_merge_request(project_id, mr_id)` - Get specific merge request

### **Filtering Options**

**Issues:**
- `state`: opened/closed/all
- `labels`: comma-separated label names
- `assignee_id`: specific assignee
- `per_page`: number of results

**Merge Requests:**
- `state`: opened/closed/merged/all
- `per_page`: number of results

## 🐳 **Docker Compose Integration**

Add to your `docker-compose.yml`:

```yaml
gitlab-agent:
  build:
    context: ..
    dockerfile: agents/gitlab-agent/Dockerfile
  ports:
    - "8007:8007"
  environment:
    - SERVICE_NAME=gitlab-agent
    - SERVICE_PORT=8007
    - GITLAB_URL=https://gitlab.com
    - GITLAB_ACCESS_TOKEN=${GITLAB_ACCESS_TOKEN}
    - POSTGRES_HOST=postgres
    - REDIS_HOST=redis
    - CONSUL_HOST=consul
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    consul:
      condition: service_healthy
  volumes:
    - ../shared:/app/shared
    - ./logs/gitlab-agent:/var/log/gitlab-agent
  restart: unless-stopped
  networks:
    - microservices-network
```

## 📊 **Monitoring**

The service includes comprehensive monitoring:

- **Health Checks**: `/health` endpoint
- **Metrics**: Prometheus-compatible metrics
- **Logging**: Structured logging with context
- **Tracing**: Distributed tracing support

## 🔒 **Security**

- **Authentication**: GitLab token-based authentication
- **Authorization**: GitLab permission-based access
- **Input Validation**: Pydantic model validation
- **Rate Limiting**: Built-in rate limiting
- **CORS**: Configurable CORS policies

## 🧪 **Testing**

```bash
# Run health check
curl http://localhost:8007/health

# Test GitLab integration
curl http://localhost:8007/gitlab/user

# Test agent invocation
curl -X POST http://localhost:8007/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": "Show me my projects", "user_id": "test"}'
```

## 📚 **References**

- [Microsoft Semantic Kernel Agent Templates](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-templates?pivots=programming-language-python)
- [Semantic Kernel ChatCompletionAgent](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/examples/example-chat-agent?pivots=programming-language-python)
- [GitLab API Documentation](https://docs.gitlab.com/ee/api/)

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 **License**

This project is part of the Enterprise Agentic AI System and follows the same licensing terms.
