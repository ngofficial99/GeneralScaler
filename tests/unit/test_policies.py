"""Unit tests for scaling policies."""

import pytest
from generalscaler.policies import SLOPolicy, CostAwarePolicy


class TestSLOPolicy:
    """Tests for SLO-based scaling policy."""

    def test_validate_config_success(self):
        """Test successful config validation."""
        config = {"targetLatencyMs": 100, "targetErrorRate": 0.01}
        policy = SLOPolicy(config)
        assert policy.validate_config() is True

    def test_validate_config_invalid_error_rate(self):
        """Test config validation with invalid error rate."""
        config = {"targetLatencyMs": 100, "targetErrorRate": 1.5}
        policy = SLOPolicy(config)
        assert policy.validate_config() is False

    def test_calculate_desired_replicas_scale_up(self):
        """Test replica calculation when scaling up is needed."""
        config = {}
        policy = SLOPolicy(config)

        desired = policy.calculate_desired_replicas(
            current_replicas=5,
            current_metric_value=150,  # Above target
            target_metric_value=100,
            min_replicas=1,
            max_replicas=20,
        )

        # Should scale up due to SLO violation
        assert desired > 5
        assert desired <= 20

    def test_calculate_desired_replicas_scale_down(self):
        """Test replica calculation when scaling down is possible."""
        config = {}
        policy = SLOPolicy(config)

        desired = policy.calculate_desired_replicas(
            current_replicas=10,
            current_metric_value=50,  # Below target
            target_metric_value=100,
            min_replicas=1,
            max_replicas=20,
        )

        # Should scale down
        assert desired < 10
        assert desired >= 1

    def test_calculate_desired_replicas_respects_min_max(self):
        """Test that replica calculation respects min/max bounds."""
        config = {}
        policy = SLOPolicy(config)

        # Test max bound
        desired = policy.calculate_desired_replicas(
            current_replicas=5,
            current_metric_value=1000,  # Very high
            target_metric_value=10,
            min_replicas=1,
            max_replicas=10,
        )
        assert desired <= 10

        # Test min bound
        desired = policy.calculate_desired_replicas(
            current_replicas=5,
            current_metric_value=1,  # Very low
            target_metric_value=100,
            min_replicas=2,
            max_replicas=20,
        )
        assert desired >= 2


class TestCostAwarePolicy:
    """Tests for cost-aware scaling policy."""

    def test_validate_config_success(self):
        """Test successful config validation."""
        config = {
            "maxMonthlyCost": 500,
            "costPerPodPerHour": 0.05,
            "preferredScaleDirection": "balanced",
        }
        policy = CostAwarePolicy(config)
        assert policy.validate_config() is True

    def test_validate_config_invalid_direction(self):
        """Test config validation with invalid scale direction."""
        config = {
            "maxMonthlyCost": 500,
            "costPerPodPerHour": 0.05,
            "preferredScaleDirection": "invalid",
        }
        policy = CostAwarePolicy(config)
        assert policy.validate_config() is False

    def test_calculate_monthly_cost(self):
        """Test monthly cost calculation."""
        config = {"costPerPodPerHour": 0.1}
        policy = CostAwarePolicy(config)

        cost = policy._calculate_monthly_cost(10)
        # 10 pods * 0.1 $/hour * 730 hours/month = 730
        assert cost == 730.0

    def test_is_within_budget(self):
        """Test budget checking."""
        config = {"maxMonthlyCost": 100, "costPerPodPerHour": 0.1}
        policy = CostAwarePolicy(config)

        # 1 pod: 0.1 * 730 = 73 (within budget)
        assert policy._is_within_budget(1) is True

        # 20 pods: 0.1 * 730 * 20 = 1460 (exceeds budget)
        assert policy._is_within_budget(20) is False

    def test_calculate_desired_replicas_with_budget_constraint(self):
        """Test replica calculation with budget constraint."""
        config = {
            "maxMonthlyCost": 100,  # $100/month
            "costPerPodPerHour": 0.1,  # Can afford ~13 pods max
        }
        policy = CostAwarePolicy(config)

        desired = policy.calculate_desired_replicas(
            current_replicas=5,
            current_metric_value=200,  # Would want to scale up
            target_metric_value=100,
            min_replicas=1,
            max_replicas=20,
        )

        # Should be limited by budget
        assert desired <= 13  # Budget allows max ~13 pods

    def test_preferred_scale_direction_down(self):
        """Test scale direction preference toward down."""
        config = {"preferredScaleDirection": "down"}
        policy = CostAwarePolicy(config)

        assert policy.scale_down_factor > policy.scale_up_factor

    def test_preferred_scale_direction_up(self):
        """Test scale direction preference toward up."""
        config = {"preferredScaleDirection": "up"}
        policy = CostAwarePolicy(config)

        assert policy.scale_up_factor > policy.scale_down_factor
