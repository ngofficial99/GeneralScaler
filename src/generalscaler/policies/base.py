"""Base scaling policy interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ScalingPolicy(ABC):
    """Abstract base class for scaling policies."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the scaling policy.

        Args:
            config: Configuration dictionary for the policy
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def calculate_desired_replicas(
        self,
        current_replicas: int,
        current_metric_value: float,
        target_metric_value: float,
        min_replicas: int,
        max_replicas: int,
    ) -> int:
        """
        Calculate the desired number of replicas based on policy.

        Args:
            current_replicas: Current number of replicas
            current_metric_value: Current metric value
            target_metric_value: Target metric value
            min_replicas: Minimum allowed replicas
            max_replicas: Maximum allowed replicas

        Returns:
            Desired number of replicas
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate the policy configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    def _clamp_replicas(self, replicas: int, min_replicas: int, max_replicas: int) -> int:
        """
        Ensure replicas is within min and max bounds.

        Args:
            replicas: Desired replicas
            min_replicas: Minimum allowed replicas
            max_replicas: Maximum allowed replicas

        Returns:
            Clamped replicas value
        """
        return max(min_replicas, min(max_replicas, replicas))
