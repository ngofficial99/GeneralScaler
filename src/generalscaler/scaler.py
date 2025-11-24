"""Safe scaling operations with cooldown and rate limiting."""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from kubernetes import client
from kubernetes.client.rest import ApiException

from .config import Config

logger = logging.getLogger(__name__)


class ScaleDecision:
    """Represents a scaling decision."""

    def __init__(
        self,
        should_scale: bool,
        current_replicas: int,
        desired_replicas: int,
        reason: str,
    ):
        self.should_scale = should_scale
        self.current_replicas = current_replicas
        self.desired_replicas = desired_replicas
        self.reason = reason


class SafeScaler:
    """
    Handles safe scaling operations with cooldown and rate limiting.

    This class ensures that scaling operations are performed safely by:
    - Enforcing cooldown periods between scale operations
    - Limiting the rate of change (max increment/decrement)
    - Validating replica bounds
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.apps_api = client.AppsV1Api()
        # Track last scale time per resource
        self.last_scale_time: Dict[str, datetime] = {}

    def _get_resource_key(self, namespace: str, name: str) -> str:
        """Generate unique key for tracking resource state."""
        return f"{namespace}/{name}"

    def _get_last_scale_time(self, namespace: str, name: str) -> Optional[datetime]:
        """Get the last time this resource was scaled."""
        key = self._get_resource_key(namespace, name)
        return self.last_scale_time.get(key)

    def _update_last_scale_time(self, namespace: str, name: str):
        """Update the last scale time for this resource."""
        key = self._get_resource_key(namespace, name)
        self.last_scale_time[key] = datetime.utcnow()

    def _is_in_cooldown(
        self,
        namespace: str,
        name: str,
        cooldown_seconds: int,
        scale_direction: str,
    ) -> bool:
        """
        Check if resource is in cooldown period.

        Args:
            namespace: Kubernetes namespace
            name: Resource name
            cooldown_seconds: Cooldown period in seconds
            scale_direction: 'up' or 'down'

        Returns:
            True if in cooldown, False otherwise
        """
        last_scale = self._get_last_scale_time(namespace, name)
        if last_scale is None:
            return False

        time_since_last_scale = (datetime.utcnow() - last_scale).total_seconds()

        if time_since_last_scale < cooldown_seconds:
            remaining = cooldown_seconds - time_since_last_scale
            self.logger.info(
                f"Resource {namespace}/{name} is in {scale_direction} cooldown. "
                f"Remaining: {remaining:.0f}s"
            )
            return True

        return False

    def decide_scaling(
        self,
        namespace: str,
        deployment_name: str,
        current_replicas: int,
        desired_replicas: int,
        min_replicas: int,
        max_replicas: int,
        behavior_config: Dict[str, Any],
    ) -> ScaleDecision:
        """
        Decide whether and how to scale based on safety constraints.

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            current_replicas: Current replica count
            desired_replicas: Desired replica count from policy
            min_replicas: Minimum allowed replicas
            max_replicas: Maximum allowed replicas
            behavior_config: Scaling behavior configuration

        Returns:
            ScaleDecision object
        """
        # Extract behavior config with defaults
        scale_up_config = behavior_config.get("scaleUp", {})
        scale_down_config = behavior_config.get("scaleDown", {})

        scale_up_cooldown = scale_up_config.get(
            "cooldownSeconds", Config.DEFAULT_SCALE_UP_COOLDOWN
        )
        scale_down_cooldown = scale_down_config.get(
            "cooldownSeconds", Config.DEFAULT_SCALE_DOWN_COOLDOWN
        )
        max_increment = scale_up_config.get(
            "maxIncrement", Config.DEFAULT_MAX_SCALE_UP_INCREMENT
        )
        max_decrement = scale_down_config.get(
            "maxDecrement", Config.DEFAULT_MAX_SCALE_DOWN_DECREMENT
        )

        # No scaling needed
        if current_replicas == desired_replicas:
            return ScaleDecision(
                should_scale=False,
                current_replicas=current_replicas,
                desired_replicas=current_replicas,
                reason="Already at desired replica count",
            )

        # Determine scale direction
        is_scale_up = desired_replicas > current_replicas
        scale_direction = "up" if is_scale_up else "down"
        cooldown_seconds = scale_up_cooldown if is_scale_up else scale_down_cooldown
        max_change = max_increment if is_scale_up else max_decrement

        # Check cooldown
        if self._is_in_cooldown(namespace, deployment_name, cooldown_seconds, scale_direction):
            return ScaleDecision(
                should_scale=False,
                current_replicas=current_replicas,
                desired_replicas=current_replicas,
                reason=f"In {scale_direction} cooldown period",
            )

        # Apply rate limiting
        change = abs(desired_replicas - current_replicas)
        if change > max_change:
            limited_desired = (
                current_replicas + max_change
                if is_scale_up
                else current_replicas - max_change
            )
            self.logger.info(
                f"Rate limiting: desired change of {change} exceeds max {max_change}. "
                f"Limiting to {limited_desired}"
            )
            desired_replicas = limited_desired

        # Final bounds check
        desired_replicas = max(min_replicas, min(max_replicas, desired_replicas))

        return ScaleDecision(
            should_scale=True,
            current_replicas=current_replicas,
            desired_replicas=desired_replicas,
            reason=f"Scaling {scale_direction} from {current_replicas} to {desired_replicas}",
        )

    async def scale_deployment(
        self,
        namespace: str,
        deployment_name: str,
        desired_replicas: int,
    ) -> bool:
        """
        Scale a deployment to the desired replica count.

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            desired_replicas: Desired replica count

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current deployment
            deployment = self.apps_api.read_namespaced_deployment(
                name=deployment_name, namespace=namespace
            )

            current_replicas = deployment.spec.replicas

            if current_replicas == desired_replicas:
                self.logger.debug(
                    f"Deployment {namespace}/{deployment_name} already has "
                    f"{desired_replicas} replicas"
                )
                return True

            # Update replicas
            deployment.spec.replicas = desired_replicas

            self.apps_api.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment,
            )

            self.logger.info(
                f"Scaled deployment {namespace}/{deployment_name} from "
                f"{current_replicas} to {desired_replicas} replicas"
            )

            # Update last scale time
            self._update_last_scale_time(namespace, deployment_name)

            return True

        except ApiException as e:
            self.logger.error(
                f"Failed to scale deployment {namespace}/{deployment_name}: {e}"
            )
            return False
        except Exception as e:
            self.logger.error(
                f"Unexpected error scaling deployment {namespace}/{deployment_name}: {e}"
            )
            return False

    async def get_current_replicas(
        self, namespace: str, deployment_name: str
    ) -> Optional[int]:
        """
        Get current replica count for a deployment.

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment

        Returns:
            Current replica count, or None if error
        """
        try:
            deployment = self.apps_api.read_namespaced_deployment(
                name=deployment_name, namespace=namespace
            )
            return deployment.spec.replicas
        except ApiException as e:
            self.logger.error(
                f"Failed to get deployment {namespace}/{deployment_name}: {e}"
            )
            return None
        except Exception as e:
            self.logger.error(
                f"Unexpected error getting deployment {namespace}/{deployment_name}: {e}"
            )
            return None
