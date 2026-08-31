"""Structured logging configuration using Loguru."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from src.config import settings


class LoggerConfig:
    """Logger configuration and setup."""

    LOG_FORMAT = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    LOG_JSON_FORMAT = (
        '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSSZ}", '
        '"level": "{level}", '
        '"name": "{name}", '
        '"function": "{function}", '
        '"line": {line}, '
        '"message": "{message}", '
        '"extra": {extra}}}'
    )

    @classmethod
    def setup(cls, log_level: Optional[str] = None) -> None:
        """
        Configure logging with structured output.

        Args:
            log_level: Override the log level from settings.
        """
        level = log_level or settings.LOG_LEVEL

        # Remove default handler
        logger.remove()

        # Console handler with color
        logger.add(
            sys.stdout,
            format=cls.LOG_FORMAT,
            level=level,
            colorize=True,
            enqueue=True,
        )

        # File handler for JSON logs (for log aggregation)
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.json.log",
            format=cls.LOG_JSON_FORMAT,
            level=level,
            rotation="1 day",
            retention="30 days",
            compression="gz",
            enqueue=True,
            serialize=True,
        )

        # File handler for human-readable logs
        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.log",
            format=cls.LOG_FORMAT,
            level=level,
            rotation="1 day",
            retention="7 days",
            compression="gz",
            enqueue=True,
        )

        # Set as default logger
        logger.debug(f"Logger initialized with level: {level}")


def get_logger(name: str):
    """
    Get a logger instance with context.

    Args:
        name: The name of the module/class.

    Returns:
        Configured logger instance.
    """
    return logger.bind(module=name)


# Initialize logger
LoggerConfig.setup()


class LoggerContext:
    """Context manager for adding extra context to logs."""

    def __init__(self, **kwargs):
        self.extra = kwargs
        self._logger = logger

    def __enter__(self):
        self._logger = self._logger.bind(**self.extra)
        return self._logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Convenience function for correlation IDs
def with_correlation_id(correlation_id: str):
    """Add correlation ID to all logs in the context."""
    return LoggerContext(correlation_id=correlation_id)