"""Unit tests for metric providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from generalscaler.metrics import (
    PrometheusMetricProvider,
    RedisMetricProvider,
)


class TestPrometheusMetricProvider:
    """Tests for Prometheus metric provider."""

    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful config validation."""
        config = {
            "serverUrl": "http://prometheus:9090",
            "query": "http_requests_total",
        }
        provider = PrometheusMetricProvider(config)
        assert await provider.validate_config() is True

    @pytest.mark.asyncio
    async def test_validate_config_missing_query(self):
        """Test config validation with missing query."""
        config = {"serverUrl": "http://prometheus:9090"}
        provider = PrometheusMetricProvider(config)
        assert await provider.validate_config() is False

    @pytest.mark.asyncio
    async def test_get_metric_value_success(self):
        """Test successful metric fetch."""
        config = {
            "serverUrl": "http://prometheus:9090",
            "query": "http_requests_total",
        }
        provider = PrometheusMetricProvider(config)

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "success",
                "data": {"result": [{"value": [1234567890, "42.5"]}]},
            }
        )

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            value = await provider.get_metric_value()
            assert value == 42.5

    @pytest.mark.asyncio
    async def test_get_metric_value_no_results(self):
        """Test metric fetch with no results."""
        config = {
            "serverUrl": "http://prometheus:9090",
            "query": "http_requests_total",
        }
        provider = PrometheusMetricProvider(config)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"status": "success", "data": {"result": []}}
        )

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            value = await provider.get_metric_value()
            assert value is None


class TestRedisMetricProvider:
    """Tests for Redis metric provider."""

    @pytest.mark.asyncio
    async def test_validate_config_success(self):
        """Test successful config validation."""
        config = {"host": "redis", "port": 6379, "queueName": "job-queue"}
        provider = RedisMetricProvider(config)
        assert await provider.validate_config() is True

    @pytest.mark.asyncio
    async def test_validate_config_missing_queue_name(self):
        """Test config validation with missing queue name."""
        config = {"host": "redis", "port": 6379}
        provider = RedisMetricProvider(config)
        assert await provider.validate_config() is False

    @pytest.mark.asyncio
    async def test_get_metric_value_list_type(self):
        """Test metric fetch for list type queue."""
        config = {"host": "redis", "port": 6379, "queueName": "job-queue"}
        provider = RedisMetricProvider(config)

        # Mock redis client
        mock_client = AsyncMock()
        mock_client.type = AsyncMock(return_value=b"list")
        mock_client.llen = AsyncMock(return_value=10)

        with patch("redis.asyncio.from_url", return_value=mock_client):
            value = await provider.get_metric_value()
            assert value == 10.0

    @pytest.mark.asyncio
    async def test_get_metric_value_nonexistent_queue(self):
        """Test metric fetch for nonexistent queue."""
        config = {"host": "redis", "port": 6379, "queueName": "job-queue"}
        provider = RedisMetricProvider(config)

        mock_client = AsyncMock()
        mock_client.type = AsyncMock(return_value=b"none")

        with patch("redis.asyncio.from_url", return_value=mock_client):
            value = await provider.get_metric_value()
            assert value == 0.0
