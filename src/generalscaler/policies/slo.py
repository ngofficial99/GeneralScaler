"""SLO-based scaling policy."""

from typing import Dict, Any
import math
import logging
from .base import ScalingPolicy

logger = logging.getLogger(__name__)


class SLOPolicy(ScalingPolicy):
    """
    SLO-based scaling policy.

    This policy scales based on SLO targets (latency, error rate).
    If current metric exceeds target, scale up more aggressively.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.target_latency_ms = config.get("targetLatencyMs", 100)
        self.target_error_rate = config.get("targetErrorRate", 0.01)
        # Aggressive scaling factor when SLO is violated
        self.slo_violation_multiplier = config.get("sloViolationMultiplier", 1.5)

    def validate_config(self) -> bool:
        """Validate SLO policy configuration."""
        if self.target_latency_ms is not None and self.target_latency_ms <= 0:
            self.logger.error("Target latency must be positive")
            return False

        if self.target_error_rate is not None:
            if not (0 <= self.target_error_rate <= 1):
                self.logger.error("Target error rate must be between 0 and 1")
                return False

        return True

    def calculate_desired_replicas(
        self,
        current_replicas: int,
        current_metric_value: float,
        target_metric_value: float,
        min_replicas: int,
        max_replicas: int,
    ) -> int:
        """
        Calculate desired replicas based on SLO policy.

        Uses a more aggressive scaling approach when metrics exceed targets,
        implementing a simple proportional scaling with SLO awareness.

        Args:
            current_replicas: Current number of replicas
            current_metric_value: Current metric value
            target_metric_value: Target metric value
            min_replicas: Minimum allowed replicas
            max_replicas: Maximum allowed replicas

        Returns:
            Desired number of replicas
        """
        if current_metric_value <= 0:
            self.logger.warning("Current metric value is 0 or negative")
            return current_replicas

        if target_metric_value <= 0:
            self.logger.warning("Target metric value is 0 or negative")
            return current_replicas

        # Calculate the ratio of current to target
        ratio = current_metric_value / target_metric_value

        # If we're exceeding the target (SLO violation), apply aggressive scaling
        if ratio > 1.0:
            # Scale more aggressively when SLO is violated
            desired_replicas = math.ceil(
                current_replicas * ratio * self.slo_violation_multiplier
            )
            self.logger.warning(
                f"SLO violation detected: current={current_metric_value}, "
                f"target={target_metric_value}, ratio={ratio:.2f}. "
                f"Scaling from {current_replicas} to {desired_replicas}"
            )
        else:
            # Normal proportional scaling
            desired_replicas = math.ceil(current_replicas * ratio)
            self.logger.info(
                f"SLO maintained: current={current_metric_value}, "
                f"target={target_metric_value}, ratio={ratio:.2f}. "
                f"Scaling from {current_replicas} to {desired_replicas}"
            )

        # Clamp to min/max bounds
        clamped_replicas = self._clamp_replicas(
            desired_replicas, min_replicas, max_replicas
        )

        if clamped_replicas != desired_replicas:
            self.logger.info(
                f"Clamping replicas from {desired_replicas} to {clamped_replicas} "
                f"(min={min_replicas}, max={max_replicas})"
            )

        return clamped_replicas
