# JIRA Agent Service

## Overview
The JIRA Agent Service provides integration with JIRA for project management and issue tracking. It enables creating, updating, and managing JIRA issues through the agent system.

## Responsibilities
- **Issue Management**: Create, update, and manage JIRA issues
- **Project Tracking**: Track project progress and metrics
- **Workflow Management**: Handle JIRA workflows and transitions
- **Reporting**: Generate reports and analytics
- **User Management**: Manage user permissions and access
- **Integration**: Seamless integration with JIRA APIs

## Architecture
```
Orchestration Service → JIRA Agent Service → JIRA API
                        ↓
                    Issue Manager
                        ↓
                    Workflow Engine
```

## Features
- **Issue Operations**: Create, read, update, delete issues
- **JQL Support**: JIRA Query Language support
- **Workflow Transitions**: Handle issue state transitions
- **Project Management**: Project creation and management
- **User Management**: User and permission management
- **Reporting**: Custom reports and dashboards

## Configuration
- **Port**: 8004 (configurable)
- **JIRA URL**: JIRA instance URL
- **Authentication**: Basic auth or OAuth
- **API Version**: JIRA REST API version
- **Rate Limits**: JIRA API rate limits
- **Webhook Support**: JIRA webhook integration

## Dependencies
- JIRA REST API
- HTTP Client (aiohttp)
- Authentication Service
- Redis (for caching)
- PostgreSQL (for audit logs)

## API Endpoints
- `POST /issues` - Create issue
- `GET /issues/{key}` - Get issue details
- `PUT /issues/{key}` - Update issue
- `POST /search` - Search issues with JQL
- `GET /projects` - List projects
- `GET /health` - Health check
