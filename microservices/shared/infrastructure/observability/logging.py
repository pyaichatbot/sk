# ============================================================================
# microservices/shared/infrastructure/observability/logging.py
# ============================================================================
import logging
import sys
from typing import Dict, Any, Optional
from pathlib import Path
import json
import traceback
from datetime import datetime
from contextlib import contextmanager

class StructuredFormatter(logging.Formatter):
    """Structured logging formatter for enterprise logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in log_data and not key.startswith('_'):
                log_data[key] = value
        
        return json.dumps(log_data, default=str)

def setup_logging(
    service_name: str = "microservice",
    log_level: str = "INFO",
    log_format: str = "json"
) -> logging.Logger:
    """
    Setup structured logging for microservices
    
    Args:
        service_name: Name of the service
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (json, text)
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Set formatter
    if log_format.lower() == "json":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name (defaults to calling module)
    
    Returns:
        Logger instance
    """
    if name is None:
        # Get the calling module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return logging.getLogger(name)

@contextmanager
def log_context(logger: logging.Logger, operation: str, **context):
    """
    Context manager for structured logging with operation context
    
    Args:
        logger: Logger instance
        operation: Operation name
        **context: Additional context data
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting {operation}", extra={"operation": operation, **context})
    
    try:
        yield
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Completed {operation}",
            extra={
                "operation": operation,
                "duration_seconds": duration,
                "status": "success",
                **context
            }
        )
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"Failed {operation}: {str(e)}",
            extra={
                "operation": operation,
                "duration_seconds": duration,
                "status": "error",
                "error": str(e),
                **context
            },
            exc_info=True
        )
        raise
