"""
Logging Module
Centralized logging configuration with structured logging support
"""

import logging
import sys
from typing import Optional
from pathlib import Path

import structlog
from structlog.types import Processor

from app.core.config import settings


def setup_logging(
    log_level: str = None,
    log_file: Optional[str] = None,
    json_logs: bool = False
) -> None:
    """
    Configure application logging with structlog for structured logs.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        json_logs: Whether to output logs in JSON format
    """
    level = getattr(logging, (log_level or settings.log_level).upper(), logging.INFO)

    # Configure log handlers
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    # Configure logging format
    if json_logs or not settings.is_development:
        # JSON format for production
        shared_processors: list[Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
        ]

        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Console format for development
        shared_processors: list[Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

        structlog.configure(
            processors=[
                *shared_processors,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=handlers,
    )

    # Set third-party library log levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


class Logger:
    """
    Wrapper class for structured logging.
    Provides convenient methods for common logging patterns.
    """

    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)

    def info(self, message: str, **kwargs) -> None:
        """Log an info message."""
        self.logger.info(message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        """Log a debug message."""
        self.logger.debug(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log a warning message."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log an error message."""
        self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log a critical message."""
        self.logger.critical(message, **kwargs)

    def exception(self, message: str, exc: Optional[Exception] = None, **kwargs) -> None:
        """Log an exception with traceback."""
        self.logger.exception(message, exc_info=True, **kwargs)

    @staticmethod
    def get_timestamp() -> str:
        """Get current ISO timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log an HTTP request with common fields."""
        self.info(
            "HTTP Request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            client_ip=client_ip,
            user_agent=user_agent,
            **kwargs
        )

    def log_chat(
        self,
        user_id: Optional[str],
        query: str,
        response: str,
        source: str,
        duration_ms: float,
        **kwargs
    ) -> None:
        """Log a chat interaction."""
        self.info(
            "Chat Interaction",
            user_id=user_id,
            query_length=len(query),
            response_length=len(response),
            source=source,
            duration_ms=round(duration_ms, 2),
            **kwargs
        )

    def log_file_upload(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        user_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a file upload event."""
        self.info(
            "File Upload",
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size,
            user_id=user_id,
            **kwargs
        )

    def log_aggregation(
        self,
        query: str,
        operation: str,
        result_count: int,
        duration_ms: float,
        **kwargs
    ) -> None:
        """Log an aggregation query."""
        self.info(
            "Aggregation Query",
            query=query,
            operation=operation,
            result_count=result_count,
            duration_ms=round(duration_ms, 2),
            **kwargs
        )


# Global logger instance for general use
logger = Logger("banking_chatbot")


def get_logger(name: str) -> Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Name for the logger (usually __name__)

    Returns:
        Logger instance
    """
    return Logger(name)