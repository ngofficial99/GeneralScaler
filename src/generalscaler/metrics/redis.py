"""Redis queue metric provider."""

from typing import Optional, Dict, Any
import redis.asyncio as aioredis
import logging
from .base import MetricProvider

logger = logging.getLogger(__name__)


class RedisMetricProvider(MetricProvider):
    """Metric provider for Redis queue length."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 6379)
        self.password = config.get("password")
        self.db = config.get("db", 0)
        self.queue_name = config.get("queueName", "")
        self.redis_client: Optional[aioredis.Redis] = None

    async def validate_config(self) -> bool:
        """Validate Redis configuration."""
        if not self.queue_name:
            self.logger.error("Redis queue name is required")
            return False

        if not self.host:
            self.logger.error("Redis host is required")
            return False

        return True

    async def _get_client(self) -> aioredis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = await aioredis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}",
                password=self.password,
                decode_responses=False,
            )
        return self.redis_client

    async def get_metric_value(self) -> Optional[float]:
        """
        Fetch queue length from Redis.

        Returns:
            The queue length as a float, or None if unavailable
        """
        try:
            client = await self._get_client()

            # Check if the key exists and get its type
            key_type = await client.type(self.queue_name)

            if key_type == b"none":
                self.logger.warning(f"Redis queue '{self.queue_name}' does not exist")
                return 0.0

            # Support both list (LLEN) and sorted set (ZCARD) types
            if key_type == b"list":
                queue_length = await client.llen(self.queue_name)
            elif key_type == b"zset":
                queue_length = await client.zcard(self.queue_name)
            else:
                self.logger.error(
                    f"Unsupported Redis key type: {key_type.decode()}. "
                    "Only 'list' and 'zset' are supported."
                )
                return None

            metric_value = float(queue_length)
            self.logger.info(f"Redis queue '{self.queue_name}' length: {metric_value}")
            return metric_value

        except aioredis.ConnectionError as e:
            self.logger.error(f"Redis connection error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching Redis metric: {e}")
            return None

    async def close(self):
        """Close the Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
