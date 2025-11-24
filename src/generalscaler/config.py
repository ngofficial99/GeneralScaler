"""Configuration management for GeneralScaler operator."""

import os
import logging
from pythonjsonlogger import jsonlogger


def setup_logging():
    """Configure structured logging for the operator."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger()
    logger.setLevel(log_level)

    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


class Config:
    """Operator configuration."""

    # Kubernetes configuration
    NAMESPACE = os.getenv("WATCH_NAMESPACE", "")  # Empty means all namespaces

    # Default scaling behavior
    DEFAULT_SYNC_INTERVAL = 30  # seconds
    DEFAULT_SCALE_UP_COOLDOWN = 60  # seconds
    DEFAULT_SCALE_DOWN_COOLDOWN = 300  # seconds
    DEFAULT_MAX_SCALE_UP_INCREMENT = 5
    DEFAULT_MAX_SCALE_DOWN_DECREMENT = 2

    # Safety limits
    ABSOLUTE_MAX_REPLICAS = 100
    ABSOLUTE_MIN_REPLICAS = 0

    # Metric fetch timeout
    METRIC_FETCH_TIMEOUT = 10  # seconds
