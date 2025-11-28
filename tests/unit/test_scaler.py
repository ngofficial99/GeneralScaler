"""Unit tests for safe scaler."""

import pytest
from datetime import datetime, timedelta
from generalscaler.scaler import SafeScaler, ScaleDecision


class TestSafeScaler:
    """Tests for SafeScaler class."""

    def test_scale_decision_no_change_needed(self):
        """Test decision when no scaling is needed."""
        scaler = SafeScaler()

        decision = scaler.decide_scaling(
            namespace="default",
            deployment_name="test-app",
            current_replicas=5,
            desired_replicas=5,  # Same as current
            min_replicas=1,
            max_replicas=10,
            behavior_config={},
        )

        assert decision.should_scale is False
        assert decision.current_replicas == 5
        assert decision.desired_replicas == 5

    def test_scale_decision_scale_up(self):
        """Test decision for scaling up."""
        scaler = SafeScaler()

        decision = scaler.decide_scaling(
            namespace="default",
            deployment_name="test-app",
            current_replicas=5,
            desired_replicas=8,
            min_replicas=1,
            max_replicas=10,
            behavior_config={},
        )

        assert decision.should_scale is True
        assert decision.desired_replicas == 8

    def test_scale_decision_respects_max_increment(self):
        """Test that scaling respects max increment."""
        scaler = SafeScaler()

        behavior_config = {
            "scaleUp": {"maxIncrement": 2, "cooldownSeconds": 0},
        }

        decision = scaler.decide_scaling(
            namespace="default",
            deployment_name="test-app",
            current_replicas=5,
            desired_replicas=10,  # Want to add 5
            min_replicas=1,
            max_replicas=20,
            behavior_config=behavior_config,
        )

        assert decision.should_scale is True
        assert decision.desired_replicas == 7  # Can only add 2

    def test_scale_decision_respects_max_decrement(self):
        """Test that scaling respects max decrement."""
        scaler = SafeScaler()

        behavior_config = {
            "scaleDown": {"maxDecrement": 1, "cooldownSeconds": 0},
        }

        decision = scaler.decide_scaling(
            namespace="default",
            deployment_name="test-app",
            current_replicas=10,
            desired_replicas=5,  # Want to remove 5
            min_replicas=1,
            max_replicas=20,
            behavior_config=behavior_config,
        )

        assert decision.should_scale is True
        assert decision.desired_replicas == 9  # Can only remove 1

    def test_scale_decision_cooldown_prevents_scaling(self):
        """Test that cooldown prevents scaling."""
        scaler = SafeScaler()

        # Simulate a recent scale
        scaler._update_last_scale_time("default", "test-app")

        behavior_config = {
            "scaleUp": {"maxIncrement": 5, "cooldownSeconds": 60},
        }

        decision = scaler.decide_scaling(
            namespace="default",
            deployment_name="test-app",
            current_replicas=5,
            desired_replicas=8,
            min_replicas=1,
            max_replicas=10,
            behavior_config=behavior_config,
        )

        assert decision.should_scale is False
        assert "cooldown" in decision.reason.lower()

    def test_scale_decision_respects_min_max_bounds(self):
        """Test that scaling respects min/max replica bounds."""
        scaler = SafeScaler()

        # Test max bound
        decision = scaler.decide_scaling(
            namespace="default",
            deployment_name="test-app",
            current_replicas=8,
            desired_replicas=15,
            min_replicas=1,
            max_replicas=10,  # Max is 10
            behavior_config={"scaleUp": {"cooldownSeconds": 0}},
        )

        assert decision.desired_replicas <= 10

        # Test min bound
        decision = scaler.decide_scaling(
            namespace="default",
            deployment_name="test-app",
            current_replicas=5,
            desired_replicas=1,
            min_replicas=3,  # Min is 3
            max_replicas=10,
            behavior_config={"scaleDown": {"cooldownSeconds": 0}},
        )

        assert decision.desired_replicas >= 3

    def test_cooldown_expires(self):
        """Test that cooldown expires after the specified time."""
        scaler = SafeScaler()
        key = scaler._get_resource_key("default", "test-app")

        # Set last scale time to 2 minutes ago
        scaler.last_scale_time[key] = datetime.utcnow() - timedelta(seconds=120)

        # Cooldown is 60 seconds, so it should have expired
        is_in_cooldown = scaler._is_in_cooldown(
            namespace="default",
            name="test-app",
            cooldown_seconds=60,
            scale_direction="up",
        )

        assert is_in_cooldown is False

    def test_cooldown_not_expired(self):
        """Test that cooldown is enforced when not expired."""
        scaler = SafeScaler()
        key = scaler._get_resource_key("default", "test-app")

        # Set last scale time to 30 seconds ago
        scaler.last_scale_time[key] = datetime.utcnow() - timedelta(seconds=30)

        # Cooldown is 60 seconds, so it should still be active
        is_in_cooldown = scaler._is_in_cooldown(
            namespace="default",
            name="test-app",
            cooldown_seconds=60,
            scale_direction="up",
        )

        assert is_in_cooldown is True
