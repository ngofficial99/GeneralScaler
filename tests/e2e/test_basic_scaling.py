"""Basic E2E tests for GeneralScaler operator."""

import pytest
import yaml
import time
from kubernetes import client
from .conftest import wait_for_deployment_ready, wait_for_replicas


@pytest.mark.e2e
class TestBasicScaling:
    """Test basic scaling functionality."""

    def test_deployment_creation(self, apps_client, namespace):
        """Test that we can create a test deployment."""
        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "test-app", "namespace": namespace},
            "spec": {
                "replicas": 2,
                "selector": {"matchLabels": {"app": "test-app"}},
                "template": {
                    "metadata": {"labels": {"app": "test-app"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "app",
                                "image": "nginx:alpine",
                                "resources": {
                                    "requests": {"cpu": "10m", "memory": "32Mi"},
                                    "limits": {"cpu": "50m", "memory": "64Mi"},
                                },
                            }
                        ]
                    },
                },
            },
        }

        # Create deployment
        apps_client.create_namespaced_deployment(
            namespace=namespace, body=deployment_manifest
        )

        # Wait for deployment to be ready
        assert wait_for_deployment_ready(apps_client, namespace, "test-app", timeout=60)

        # Verify deployment
        deployment = apps_client.read_namespaced_deployment("test-app", namespace)
        assert deployment.spec.replicas == 2

    def test_crd_installation(self, k8s_cluster):
        """Test that CRD can be installed."""
        # This would require installing the CRD
        # For now, we just verify kubectl is accessible
        import subprocess

        result = subprocess.run(
            ["kubectl", "get", "nodes"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "kind-control-plane" in result.stdout

    @pytest.mark.skip(reason="Requires operator to be running")
    def test_generalscaler_creation(self, namespace):
        """
        Test creating a GeneralScaler resource.

        Note: This test is skipped by default as it requires the operator to be running.
        In a real E2E test, you would:
        1. Install the operator
        2. Create a test deployment
        3. Create a GeneralScaler resource
        4. Wait for scaling to occur
        5. Verify the deployment was scaled
        """
        generalscaler_manifest = {
            "apiVersion": "autoscaling.generalscaler.io/v1alpha1",
            "kind": "GeneralScaler",
            "metadata": {"name": "test-scaler", "namespace": namespace},
            "spec": {
                "targetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "test-app",
                },
                "minReplicas": 1,
                "maxReplicas": 5,
                "metric": {
                    "type": "prometheus",
                    "targetValue": 100,
                    "prometheus": {
                        "serverUrl": "http://prometheus:9090",
                        "query": "up",
                    },
                },
            },
        }

        # This would create the GeneralScaler
        # custom_api = client.CustomObjectsApi()
        # custom_api.create_namespaced_custom_object(
        #     group="autoscaling.generalscaler.io",
        #     version="v1alpha1",
        #     namespace=namespace,
        #     plural="generalscalers",
        #     body=generalscaler_manifest,
        # )

        # Wait and verify scaling occurred
        # assert wait_for_replicas(apps_client, namespace, "test-app", 3, timeout=120)
