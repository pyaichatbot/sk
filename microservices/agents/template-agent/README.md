# Template Agent

This is a template agent for creating new agents in the microservices architecture. Copy this template and customize it for your specific needs.

## Quick Start

1. **Copy the template:**
   ```bash
   cp -r template-agent your-new-agent
   cd your-new-agent
   ```

2. **Rename files and update references:**
   - Rename `template_agent.py` to `your_agent.py`
   - Update all imports and class names
   - Update `main.py` to import your new agent class
   - Update `Dockerfile` port if needed
   - Update `requirements.txt` with your specific dependencies

3. **Customize the agent:**
   - Update `TemplateAgent` class name and functionality
   - Modify capabilities, input/output formats
   - Add your specific processing logic
   - Update endpoints in `main.py`

4. **Build and test:**
   ```bash
   docker build -f your-new-agent/Dockerfile -t your-new-agent:latest .
   docker run --rm -p 8007:8007 your-new-agent:latest
   ```

## Files Structure

- `main.py` - FastAPI application with endpoints
- `template_agent.py` - Main agent implementation (rename and customize)
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `README.md` - This file

## Customization Points

### 1. Agent Class (`template_agent.py`)
- Change class name from `TemplateAgent` to your agent name
- Update `agent_id` and `capabilities`
- Customize `invoke()` and `invoke_stream()` methods
- Add your specific processing logic

### 2. Main Application (`main.py`)
- Update imports to use your agent class
- Change service name and description
- Add custom endpoints as needed
- Update port number if required

### 3. Dependencies (`requirements.txt`)
- Add your specific dependencies
- Remove unused dependencies
- Update versions as needed

### 4. Docker Configuration (`Dockerfile`)
- Update port number if different from 8006
- Add any system dependencies
- Customize health check if needed

## Example Customization

```python
# In your_agent.py
class YourAgent:
    def __init__(self, settings: MicroserviceSettings):
        self.agent_id = "your-agent-001"
        self.capabilities = AgentCapabilities(
            agent_name="YourAgent",
            capabilities=["your_capability1", "your_capability2"],
            input_formats=["text", "json", "your_format"],
            output_formats=["text", "json"],
            max_input_size=50000,
            rate_limit=50,
            timeout=60
        )
    
    async def invoke(self, message: str, **kwargs) -> AgentResponse:
        # Your custom logic here
        result = await self.process_your_data(message)
        return AgentResponse(content=result, agent_id=self.agent_id)
```

## Integration with Docker Compose

Add your new agent to the docker-compose file:

```yaml
your-agent:
  build:
    context: ..
    dockerfile: agents/your-agent/Dockerfile
  ports:
    - "8007:8007"  # Use your port
  environment:
    - SERVICE_NAME=your-agent
    - SERVICE_PORT=8007
    # Add your environment variables
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    consul:
      condition: service_healthy
  volumes:
    - ../shared:/app/shared
    - ./logs/your-agent:/var/log/your-agent
  restart: unless-stopped
  networks:
    - microservices-network
```

## Testing

1. **Health Check:**
   ```bash
   curl http://localhost:8006/health
   ```

2. **Capabilities:**
   ```bash
   curl http://localhost:8006/capabilities
   ```

3. **Invoke Agent:**
   ```bash
   curl -X POST http://localhost:8006/invoke \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello, template agent!"}'
   ```

## Best Practices

1. **Error Handling:** Always wrap your logic in try-catch blocks
2. **Logging:** Use the provided logger for debugging
3. **Metrics:** Update metrics for monitoring
4. **Documentation:** Update this README for your specific agent
5. **Testing:** Add unit tests for your agent logic
6. **Configuration:** Use environment variables for configuration
7. **Security:** Validate inputs and sanitize outputs

## Support

For questions or issues with the template, refer to the main project documentation or create an issue in the project repository.
