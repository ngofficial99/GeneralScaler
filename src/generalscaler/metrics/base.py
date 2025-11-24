"""Base metric provider interface."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class MetricProvider(ABC):
    """Abstract base class for metric providers."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the metric provider.

        Args:
            config: Configuration dictionary for the metric provider
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def get_metric_value(self) -> Optional[float]:
        """
        Fetch the current metric value.

        Returns:
            The current metric value as a float, or None if unavailable

        Raises:
            Exception: If there's an error fetching the metric
        """
        pass

    @abstractmethod
    async def validate_config(self) -> bool:
        """
        Validate the metric provider configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    async def close(self):
        """
        Clean up resources (override if needed).
        """
        pass
