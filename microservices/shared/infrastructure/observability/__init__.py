# ============================================================================
# microservices/shared/infrastructure/observability/__init__.py
# ============================================================================
"""
Observability infrastructure for microservices
"""

from .logging import get_logger, setup_logging

__all__ = ["get_logger", "setup_logging"]
