# ============================================================================
# microservices/api-gateway/routers/__init__.py
# ============================================================================
"""
API Gateway routers for request routing and handling.
"""

from routers import chat, agents, documents, orchestration, health

__all__ = ["chat", "agents", "documents", "orchestration", "health"]
