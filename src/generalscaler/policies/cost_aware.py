"""Cost-aware scaling policy."""

from typing import Dict, Any
import math
import logging
from datetime import datetime
from .base import ScalingPolicy

logger = logging.getLogger(__name__)


class CostAwarePolicy(ScalingPolicy):
    """
    Cost-aware scaling policy.

    This policy considers cost constraints when making scaling decisions.
    It respects budget limits and can prefer scaling down to reduce costs.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.max_monthly_cost = config.get("maxMonthlyCost", float("inf"))
        self.cost_per_pod_per_hour = config.get("costPerPodPerHour", 0.0)
        self.preferred_scale_direction = config.get("preferredScaleDirection", "balanced")
        # Scaling factors based on preference
        self.scale_up_factor = 1.0
        self.scale_down_factor = 1.0

        if self.preferred_scale_direction == "down":
            self.scale_down_factor = 1.2  # More aggressive scale down
            self.scale_up_factor = 0.8  # More conservative scale up
        elif self.preferred_scale_direction == "up":
            self.scale_up_factor = 1.2  # More aggressive scale up
            self.scale_down_factor = 0.8  # More conservative scale down

    def validate_config(self) -> bool:
        """Validate cost-aware policy configuration."""
        if self.cost_per_pod_per_hour < 0:
            self.logger.error("Cost per pod per hour must be non-negative")
            return False

        if self.max_monthly_cost < 0:
            self.logger.error("Max monthly cost must be non-negative")
            return False

        if self.preferred_scale_direction not in ["up", "down", "balanced"]:
            self.logger.error(
                "Preferred scale direction must be 'up', 'down', or 'balanced'"
            )
            return False

        return True

    def _calculate_monthly_cost(self, replicas: int) -> float:
        """
        Calculate the projected monthly cost for given replicas.

        Args:
            replicas: Number of replicas

        Returns:
            Projected monthly cost in USD
        """
        hours_per_month = 730  # Average hours in a month
        return replicas * self.cost_per_pod_per_hour * hours_per_month

    def _is_within_budget(self, replicas: int) -> bool:
        """
        Check if the given replica count is within budget.

        Args:
            replicas: Number of replicas to check

        Returns:
            True if within budget, False otherwise
        """
        if self.max_monthly_cost == float("inf"):
            return True

        projected_cost = self._calculate_monthly_cost(replicas)
        return projected_cost <= self.max_monthly_cost

    def calculate_desired_replicas(
        self,
        current_replicas: int,
        current_metric_value: float,
        target_metric_value: float,
        min_replicas: int,
        max_replicas: int,
    ) -> int:
        """
        Calculate desired replicas based on cost-aware policy.

        Applies standard proportional scaling but considers cost constraints
        and scaling direction preferences.

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

        # Calculate base desired replicas using proportional scaling
        ratio = current_metric_value / target_metric_value

        if ratio > 1.0:
            # Need to scale up
            base_desired = math.ceil(current_replicas * ratio * self.scale_up_factor)
        else:
            # Can scale down
            base_desired = math.ceil(current_replicas * ratio * self.scale_down_factor)

        # Clamp to min/max bounds
        desired_replicas = self._clamp_replicas(base_desired, min_replicas, max_replicas)

        # Check budget constraint
        if not self._is_within_budget(desired_replicas):
            # Find the maximum replicas within budget
            for replicas in range(desired_replicas, min_replicas - 1, -1):
                if self._is_within_budget(replicas):
                    projected_cost = self._calculate_monthly_cost(replicas)
                    self.logger.warning(
                        f"Budget constraint applied: reducing from {desired_replicas} "
                        f"to {replicas} replicas (projected monthly cost: ${projected_cost:.2f}, "
                        f"max: ${self.max_monthly_cost:.2f})"
                    )
                    desired_replicas = replicas
                    break
            else:
                # Even min_replicas exceeds budget
                self.logger.error(
                    f"Even minimum replicas ({min_replicas}) exceeds budget. "
                    f"Using minimum anyway."
                )
                desired_replicas = min_replicas

        current_cost = self._calculate_monthly_cost(current_replicas)
        desired_cost = self._calculate_monthly_cost(desired_replicas)

        self.logger.info(
            f"Cost-aware scaling: current={current_replicas} "
            f"(${current_cost:.2f}/mo), desired={desired_replicas} "
            f"(${desired_cost:.2f}/mo), direction={self.preferred_scale_direction}"
        )

        return desired_replicas
