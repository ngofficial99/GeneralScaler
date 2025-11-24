"""Prometheus metric provider."""

from typing import Optional, Dict, Any
import aiohttp
import logging
from .base import MetricProvider

logger = logging.getLogger(__name__)


class PrometheusMetricProvider(MetricProvider):
    """Metric provider for Prometheus queries."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.server_url = config.get("serverUrl", "http://prometheus:9090")
        self.query = config.get("query", "")
        self.headers = config.get("headers", {})
        self.session: Optional[aiohttp.ClientSession] = None

    async def validate_config(self) -> bool:
        """Validate Prometheus configuration."""
        if not self.query:
            self.logger.error("Prometheus query is required")
            return False

        if not self.server_url:
            self.logger.error("Prometheus server URL is required")
            return False

        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers)
        return self.session

    async def get_metric_value(self) -> Optional[float]:
        """
        Fetch metric value from Prometheus.

        Returns:
            The metric value as a float, or None if unavailable
        """
        try:
            session = await self._get_session()
            url = f"{self.server_url}/api/v1/query"
            params = {"query": self.query}

            self.logger.debug(f"Querying Prometheus: {self.query}")

            async with session.get(url, params=params, timeout=10) as response:
                if response.status != 200:
                    self.logger.error(
                        f"Prometheus query failed with status {response.status}"
                    )
                    return None

                data = await response.json()

                if data.get("status") != "success":
                    self.logger.error(f"Prometheus query failed: {data}")
                    return None

                results = data.get("data", {}).get("result", [])

                if not results:
                    self.logger.warning("Prometheus query returned no results")
                    return None

                # Get the first result's value
                value = results[0].get("value", [None, None])[1]

                if value is None:
                    self.logger.warning("Prometheus query returned None value")
                    return None

                metric_value = float(value)
                self.logger.info(f"Prometheus metric value: {metric_value}")
                return metric_value

        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error querying Prometheus: {e}")
            return None
        except (ValueError, KeyError, IndexError) as e:
            self.logger.error(f"Error parsing Prometheus response: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error querying Prometheus: {e}")
            return None

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
