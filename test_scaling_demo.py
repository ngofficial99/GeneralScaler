#!/usr/bin/env python3
"""
Demo script to test GeneralScaler scaling logic without running the full operator.

This script simulates what the operator would do:
1. Connects to Redis
2. Checks queue length (metric)
3. Calculates desired replicas using a policy
4. Scales the deployment
"""

import time
import sys
import os
import asyncio
from kubernetes import client, config

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from generalscaler.metrics.redis import RedisMetricProvider
from generalscaler.policies.cost_aware import CostAwarePolicy
from generalscaler.scaler import SafeScaler


async def main():
    """Main demo function."""
    print("=" * 60)
    print("GeneralScaler - Live Scaling Demo")
    print("=" * 60)

    # Load Kubernetes config
    try:
        config.load_kube_config()
        print("✅ Connected to Kubernetes cluster")
    except Exception as e:
        print(f"❌ Failed to connect to Kubernetes: {e}")
        return

    # Configuration
    namespace = "default"
    deployment_name = "test-app"
    min_replicas = 1
    max_replicas = 10
    target_queue_length = 10  # Target: 10 items per pod

    # Create components
    print("\n📦 Initializing components...")

    # Metric provider (Redis queue)
    metric_config = {
        "host": "redis.default.svc.cluster.local",
        "port": 6379,
        "db": 0,
        "queueName": "test-queue"
    }
    metric_provider = RedisMetricProvider(metric_config)

    # Policy (Cost-aware)
    policy_config = {
        "maxMonthlyCost": 1000,
        "costPerPodPerHour": 0.05,
        "preferredScaleDirection": "balanced"
    }
    policy = CostAwarePolicy(policy_config)

    # Scaler
    scaler = SafeScaler()

    # Behavior config
    behavior_config = {
        "scaleUp": {
            "maxIncrement": 3,
            "cooldownSeconds": 30
        },
        "scaleDown": {
            "maxDecrement": 2,
            "cooldownSeconds": 60
        }
    }

    print("✅ Components initialized")
    print(f"\nTarget: {deployment_name} in namespace: {namespace}")
    print(f"Min replicas: {min_replicas}, Max replicas: {max_replicas}")
    print(f"Target metric: {target_queue_length} queue items per pod")
    print(f"Policy: Cost-aware (max $1000/month, $0.05/pod/hour)")

    print("\n" + "=" * 60)
    print("Starting monitoring loop (Ctrl+C to stop)")
    print("=" * 60)

    iteration = 0
    try:
        while True:
            iteration += 1
            print(f"\n[Iteration {iteration}] {time.strftime('%H:%M:%S')}")
            print("-" * 60)

            # Get current replicas
            current_replicas = await scaler.get_current_replicas(namespace, deployment_name)
            if current_replicas is None:
                print(f"❌ Could not get deployment {deployment_name}")
                await asyncio.sleep(10)
                continue

            print(f"📊 Current replicas: {current_replicas}")

            # Get metric value
            metric_value = await metric_provider.get_metric_value()
            if metric_value is None:
                print("⚠️  Could not fetch metric, using 0")
                metric_value = 0.0

            print(f"📈 Queue length: {metric_value}")

            # Calculate desired replicas
            policy_desired = policy.calculate_desired_replicas(
                current_replicas=current_replicas,
                current_metric_value=metric_value,
                target_metric_value=target_queue_length,
                min_replicas=min_replicas,
                max_replicas=max_replicas
            )

            print(f"🎯 Policy suggests: {policy_desired} replicas")

            # Make scaling decision
            decision = scaler.decide_scaling(
                namespace=namespace,
                deployment_name=deployment_name,
                current_replicas=current_replicas,
                desired_replicas=policy_desired,
                min_replicas=min_replicas,
                max_replicas=max_replicas,
                behavior_config=behavior_config
            )

            # Apply scaling
            if decision.should_scale:
                print(f"⚡ SCALING: {decision.reason}")
                success = await scaler.scale_deployment(
                    namespace=namespace,
                    deployment_name=deployment_name,
                    desired_replicas=decision.desired_replicas
                )
                if success:
                    print(f"✅ Scaled to {decision.desired_replicas} replicas")
                else:
                    print("❌ Scaling failed")
            else:
                print(f"⏸️  No scaling: {decision.reason}")

            # Wait before next iteration
            await asyncio.sleep(15)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping demo...")
    finally:
        await metric_provider.close()
        print("👋 Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())
