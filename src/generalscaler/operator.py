"""GeneralScaler Kubernetes Operator using kopf."""

import kopf
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from kubernetes import config as k8s_config
from kubernetes.client import ApiException

from .config import setup_logging, Config
from .metrics import (
    MetricProvider,
    PrometheusMetricProvider,
    RedisMetricProvider,
    PubSubMetricProvider,
)
from .policies import ScalingPolicy, SLOPolicy, CostAwarePolicy
from .scaler import SafeScaler

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Global scaler instance
scaler = SafeScaler()

# Track active metric providers and policies
active_resources: Dict[str, Dict[str, Any]] = {}


def create_metric_provider(metric_config: Dict[str, Any]) -> Optional[MetricProvider]:
    """
    Create a metric provider based on configuration.

    Args:
        metric_config: Metric configuration from spec

    Returns:
        MetricProvider instance or None if invalid
    """
    metric_type = metric_config.get("type", "").lower()

    try:
        if metric_type == "prometheus":
            return PrometheusMetricProvider(metric_config.get("prometheus", {}))
        elif metric_type == "redis":
            return RedisMetricProvider(metric_config.get("redis", {}))
        elif metric_type == "pubsub":
            return PubSubMetricProvider(metric_config.get("pubsub", {}))
        else:
            logger.error(f"Unknown metric type: {metric_type}")
            return None
    except Exception as e:
        logger.error(f"Error creating metric provider: {e}")
        return None


def create_policy(policy_config: Dict[str, Any]) -> ScalingPolicy:
    """
    Create a scaling policy based on configuration.

    Args:
        policy_config: Policy configuration from spec

    Returns:
        ScalingPolicy instance
    """
    policy_type = policy_config.get("type", "simple").lower()

    try:
        if policy_type == "slo":
            return SLOPolicy(policy_config.get("slo", {}))
        elif policy_type == "costaware":
            return CostAwarePolicy(policy_config.get("costAware", {}))
        else:
            # Default to SLO policy with default config
            logger.info(f"Using default SLO policy (type was: {policy_type})")
            return SLOPolicy({})
    except Exception as e:
        logger.error(f"Error creating policy, using default: {e}")
        return SLOPolicy({})


@kopf.on.create("autoscaling.generalscaler.io", "v1alpha1", "generalscalers")
async def on_create(spec, name, namespace, **kwargs):
    """Handle GeneralScaler resource creation."""
    logger.info(f"GeneralScaler {namespace}/{name} created")

    # Validate spec
    if not validate_spec(spec):
        logger.error(f"Invalid spec for {namespace}/{name}")
        return {"message": "Invalid specification"}

    # Create metric provider
    metric_provider = create_metric_provider(spec.get("metric", {}))
    if metric_provider is None:
        return {"message": "Failed to create metric provider"}

    # Validate metric provider config
    if not await metric_provider.validate_config():
        return {"message": "Invalid metric provider configuration"}

    # Create policy
    policy = create_policy(spec.get("policy", {}))
    if not policy.validate_config():
        return {"message": "Invalid policy configuration"}

    # Store in active resources
    resource_key = f"{namespace}/{name}"
    active_resources[resource_key] = {
        "metric_provider": metric_provider,
        "policy": policy,
        "spec": spec,
    }

    logger.info(f"GeneralScaler {namespace}/{name} initialized successfully")
    return {"message": "GeneralScaler created successfully"}


@kopf.on.update("autoscaling.generalscaler.io", "v1alpha1", "generalscalers")
async def on_update(spec, name, namespace, **kwargs):
    """Handle GeneralScaler resource updates."""
    logger.info(f"GeneralScaler {namespace}/{name} updated")

    # Clean up old resources
    resource_key = f"{namespace}/{name}"
    if resource_key in active_resources:
        old_provider = active_resources[resource_key].get("metric_provider")
        if old_provider:
            await old_provider.close()

    # Recreate with new config (same as create)
    await on_create(spec, name, namespace, **kwargs)


@kopf.on.delete("autoscaling.generalscaler.io", "v1alpha1", "generalscalers")
async def on_delete(spec, name, namespace, **kwargs):
    """Handle GeneralScaler resource deletion."""
    logger.info(f"GeneralScaler {namespace}/{name} deleted")

    # Clean up resources
    resource_key = f"{namespace}/{name}"
    if resource_key in active_resources:
        provider = active_resources[resource_key].get("metric_provider")
        if provider:
            await provider.close()
        del active_resources[resource_key]


@kopf.timer(
    "autoscaling.generalscaler.io",
    "v1alpha1",
    "generalscalers",
    interval=30.0,  # Default interval, can be overridden by spec
)
async def reconcile(spec, name, namespace, status, patch, **kwargs):
    """
    Periodic reconciliation loop for autoscaling.

    This is the main scaling loop that:
    1. Fetches current metric value
    2. Calculates desired replicas using policy
    3. Makes safe scaling decision
    4. Updates deployment if needed
    5. Updates status
    """
    resource_key = f"{namespace}/{name}"

    # Get active resource data
    resource_data = active_resources.get(resource_key)
    if not resource_data:
        logger.warning(f"Resource {namespace}/{name} not found in active resources")
        return

    metric_provider = resource_data["metric_provider"]
    policy = resource_data["policy"]

    try:
        # Extract config
        target_ref = spec.get("targetRef", {})
        deployment_name = target_ref.get("name")
        min_replicas = spec.get("minReplicas", 1)
        max_replicas = spec.get("maxReplicas", 10)
        target_value = spec.get("metric", {}).get("targetValue", 100)
        behavior_config = spec.get("behavior", {})

        if not deployment_name:
            logger.error(f"No target deployment specified for {namespace}/{name}")
            return

        # Get current replicas
        current_replicas = await scaler.get_current_replicas(namespace, deployment_name)
        if current_replicas is None:
            logger.error(f"Failed to get current replicas for {namespace}/{deployment_name}")
            patch.status["conditions"] = [
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "DeploymentNotFound",
                    "message": f"Failed to get deployment {deployment_name}",
                    "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
                }
            ]
            return

        # Fetch current metric value
        logger.info(f"Fetching metric for {namespace}/{name}")
        current_metric_value = await metric_provider.get_metric_value()

        if current_metric_value is None:
            logger.warning(f"Failed to fetch metric for {namespace}/{name}")
            patch.status["conditions"] = [
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "MetricFetchFailed",
                    "message": "Failed to fetch metric value",
                    "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
                }
            ]
            return

        # Calculate desired replicas using policy
        policy_desired_replicas = policy.calculate_desired_replicas(
            current_replicas=current_replicas,
            current_metric_value=current_metric_value,
            target_metric_value=target_value,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
        )

        logger.info(
            f"Scaling decision for {namespace}/{name}: "
            f"current={current_replicas}, metric={current_metric_value}, "
            f"target={target_value}, policy_desired={policy_desired_replicas}"
        )

        # Make safe scaling decision (apply cooldown and rate limits)
        scale_decision = scaler.decide_scaling(
            namespace=namespace,
            deployment_name=deployment_name,
            current_replicas=current_replicas,
            desired_replicas=policy_desired_replicas,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            behavior_config=behavior_config,
        )

        # Update status
        patch.status["currentReplicas"] = current_replicas
        patch.status["desiredReplicas"] = scale_decision.desired_replicas
        patch.status["currentMetricValue"] = current_metric_value
        patch.status["lastMetricCheckTime"] = datetime.utcnow().isoformat() + "Z"

        # Perform scaling if needed
        if scale_decision.should_scale:
            logger.info(
                f"Scaling {namespace}/{deployment_name}: {scale_decision.reason}"
            )

            success = await scaler.scale_deployment(
                namespace=namespace,
                deployment_name=deployment_name,
                desired_replicas=scale_decision.desired_replicas,
            )

            if success:
                patch.status["lastScaleTime"] = datetime.utcnow().isoformat() + "Z"
                patch.status["conditions"] = [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "ScalingSucceeded",
                        "message": scale_decision.reason,
                        "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
                    }
                ]
            else:
                patch.status["conditions"] = [
                    {
                        "type": "Ready",
                        "status": "False",
                        "reason": "ScalingFailed",
                        "message": "Failed to scale deployment",
                        "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
                    }
                ]
        else:
            logger.debug(f"No scaling needed for {namespace}/{name}: {scale_decision.reason}")
            patch.status["conditions"] = [
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "NoScalingNeeded",
                    "message": scale_decision.reason,
                    "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
                }
            ]

    except Exception as e:
        logger.error(f"Error in reconciliation loop for {namespace}/{name}: {e}", exc_info=True)
        patch.status["conditions"] = [
            {
                "type": "Ready",
                "status": "False",
                "reason": "ReconciliationError",
                "message": str(e),
                "lastTransitionTime": datetime.utcnow().isoformat() + "Z",
            }
        ]


def validate_spec(spec: Dict[str, Any]) -> bool:
    """
    Validate GeneralScaler spec.

    Args:
        spec: The spec to validate

    Returns:
        True if valid, False otherwise
    """
    # Check required fields
    if "targetRef" not in spec:
        logger.error("Missing targetRef in spec")
        return False

    if "name" not in spec["targetRef"]:
        logger.error("Missing targetRef.name in spec")
        return False

    if "minReplicas" not in spec or "maxReplicas" not in spec:
        logger.error("Missing minReplicas or maxReplicas in spec")
        return False

    if spec["minReplicas"] > spec["maxReplicas"]:
        logger.error("minReplicas cannot be greater than maxReplicas")
        return False

    if "metric" not in spec:
        logger.error("Missing metric configuration in spec")
        return False

    return True


def main():
    """Main entry point for the operator."""
    logger.info("Starting GeneralScaler operator")

    # Try to load in-cluster config, fall back to kubeconfig
    try:
        k8s_config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes configuration")
    except k8s_config.ConfigException:
        try:
            k8s_config.load_kube_config()
            logger.info("Loaded kubeconfig")
        except k8s_config.ConfigException:
            logger.error("Failed to load Kubernetes configuration")
            raise

    # Note: kopf.run() is not called here because kopf CLI will handle it
    logger.info("GeneralScaler operator ready")


if __name__ == "__main__":
    main()
