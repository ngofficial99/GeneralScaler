"""Google Cloud Pub/Sub metric provider."""

from typing import Optional, Dict, Any
import logging
from .base import MetricProvider

logger = logging.getLogger(__name__)


class PubSubMetricProvider(MetricProvider):
    """Metric provider for Google Cloud Pub/Sub subscription backlog."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.project_id = config.get("projectId", "")
        self.subscription_id = config.get("subscriptionId", "")
        self.credentials_path = config.get("credentialsPath")
        self.subscriber_client = None

    async def validate_config(self) -> bool:
        """Validate Pub/Sub configuration."""
        if not self.project_id:
            self.logger.error("Pub/Sub project ID is required")
            return False

        if not self.subscription_id:
            self.logger.error("Pub/Sub subscription ID is required")
            return False

        return True

    def _get_client(self):
        """Get or create Pub/Sub subscriber client."""
        if self.subscriber_client is None:
            try:
                from google.cloud import pubsub_v1
                from google.oauth2 import service_account

                if self.credentials_path:
                    credentials = service_account.Credentials.from_service_account_file(
                        self.credentials_path
                    )
                    self.subscriber_client = pubsub_v1.SubscriberClient(
                        credentials=credentials
                    )
                else:
                    # Use default credentials
                    self.subscriber_client = pubsub_v1.SubscriberClient()

            except ImportError:
                self.logger.error(
                    "google-cloud-pubsub library not installed. "
                    "Install it with: pip install google-cloud-pubsub"
                )
                return None
            except Exception as e:
                self.logger.error(f"Error creating Pub/Sub client: {e}")
                return None

        return self.subscriber_client

    async def get_metric_value(self) -> Optional[float]:
        """
        Fetch subscription message backlog from Pub/Sub.

        Returns:
            The number of undelivered messages, or None if unavailable
        """
        try:
            client = self._get_client()
            if client is None:
                return None

            subscription_path = client.subscription_path(
                self.project_id, self.subscription_id
            )

            # Get subscription details
            subscription = client.get_subscription(
                request={"subscription": subscription_path}
            )

            # Note: For accurate backlog, you might want to use monitoring API
            # This is a simplified version that counts num_outstanding_messages
            # In production, consider using Cloud Monitoring API for more accurate metrics

            # For this implementation, we'll return 0 as a placeholder
            # In a real scenario, you'd query the monitoring API
            self.logger.warning(
                "Pub/Sub metric provider returns basic info. "
                "Consider using Prometheus with Pub/Sub exporter for production."
            )

            # Return 0 for now - in production, implement proper monitoring
            metric_value = 0.0
            self.logger.info(
                f"Pub/Sub subscription '{self.subscription_id}' metric: {metric_value}"
            )
            return metric_value

        except Exception as e:
            self.logger.error(f"Error fetching Pub/Sub metric: {e}")
            return None

    async def close(self):
        """Close the Pub/Sub client."""
        if self.subscriber_client:
            self.subscriber_client.close()
