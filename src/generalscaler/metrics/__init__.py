"""Metric plugins for GeneralScaler."""

from .base import MetricProvider
from .prometheus import PrometheusMetricProvider
from .redis import RedisMetricProvider
from .pubsub import PubSubMetricProvider

__all__ = [
    "MetricProvider",
    "PrometheusMetricProvider",
    "RedisMetricProvider",
    "PubSubMetricProvider",
]
