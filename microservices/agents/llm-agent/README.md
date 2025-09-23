# LLM Agent Service

## Overview
The LLM Agent Service provides natural language processing and generation capabilities. It integrates with various language models and provides text generation, analysis, and processing services.

## Responsibilities
- **Text Generation**: Generate text based on prompts and context
- **Language Analysis**: Analyze text for sentiment, topics, etc.
- **Text Processing**: Summarization, translation, and transformation
- **Model Management**: Manage different LLM models and configurations
- **Performance Optimization**: Optimize model performance and caching
- **Custom Integration**: Support for custom in-house LLM services

## Architecture
```
Orchestration Service → LLM Agent Service → LLM Models
                        ↓
                    Model Manager
                        ↓
                    Response Processor
```

## Features
- **Multi-model Support**: Support for various LLM providers
- **Custom Models**: Integration with custom in-house models
- **Streaming**: Real-time streaming responses
- **Caching**: Response caching for performance
- **Token Management**: Token counting and optimization
- **Context Management**: Long context handling

## Configuration
- **Port**: 8005 (configurable)
- **LLM Endpoint**: Custom LLM service endpoint
- **Model Configuration**: Model-specific parameters
- **Token Limits**: Maximum token limits
- **Cache Settings**: Response caching configuration
- **Streaming**: Streaming response configuration

## Dependencies
- LLM Service (Custom or external)
- HTTP Client (aiohttp)
- Redis (for caching)
- PostgreSQL (for logs)
- Token Counter Service

## API Endpoints
- `POST /generate` - Generate text
- `POST /analyze` - Analyze text
- `POST /summarize` - Summarize text
- `GET /models` - List available models
- `GET /health` - Health check
