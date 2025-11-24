"""Pytest configuration for E2E tests."""

import pytest
import subprocess
import time
from kubernetes import client, config


@pytest.fixture(scope="session")
def k8s_cluster():
    """
    Create a kind cluster for testing.

    This fixture creates a kind cluster before tests and tears it down after.
    """
    cluster_name = "generalscaler-test"

    # Create kind cluster
    print(f"\nCreating kind cluster: {cluster_name}")
    subprocess.run(
        [
            "kind",
            "create",
            "cluster",
            "--name",
            cluster_name,
            "--wait",
            "60s",
        ],
        check=True,
    )

    # Load kubeconfig
    subprocess.run(
        ["kind", "get", "kubeconfig", "--name", cluster_name],
        check=True,
    )

    # Load k8s config
    config.load_kube_config()

    yield cluster_name

    # Cleanup: Delete kind cluster
    print(f"\nDeleting kind cluster: {cluster_name}")
    subprocess.run(
        ["kind", "delete", "cluster", "--name", cluster_name],
        check=False,  # Don't fail if cluster is already gone
    )


@pytest.fixture(scope="session")
def k8s_client(k8s_cluster):
    """Get Kubernetes client."""
    return client.CoreV1Api()


@pytest.fixture(scope="session")
def apps_client(k8s_cluster):
    """Get Kubernetes apps client."""
    return client.AppsV1Api()


@pytest.fixture
def namespace(k8s_client):
    """Create a test namespace."""
    namespace_name = "test-generalscaler"

    # Create namespace
    namespace_manifest = client.V1Namespace(
        metadata=client.V1ObjectMeta(name=namespace_name)
    )

    try:
        k8s_client.create_namespace(namespace_manifest)
    except client.ApiException as e:
        if e.status != 409:  # Ignore if already exists
            raise

    yield namespace_name

    # Cleanup: Delete namespace
    try:
        k8s_client.delete_namespace(namespace_name)
    except client.ApiException:
        pass


def wait_for_deployment_ready(apps_client, namespace, name, timeout=120):
    """Wait for a deployment to be ready."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            deployment = apps_client.read_namespaced_deployment(name, namespace)

            if (
                deployment.status.ready_replicas is not None
                and deployment.status.ready_replicas == deployment.spec.replicas
            ):
                return True

        except client.ApiException:
            pass

        time.sleep(2)

    return False


def wait_for_replicas(apps_client, namespace, name, expected_replicas, timeout=120):
    """Wait for a deployment to have expected number of replicas."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            deployment = apps_client.read_namespaced_deployment(name, namespace)

            if deployment.spec.replicas == expected_replicas:
                return True

        except client.ApiException:
            pass

        time.sleep(2)

    return False
