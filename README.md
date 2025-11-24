# GeneralScaler - Generic Kubernetes Autoscaling Operator

[![CI](https://github.com/yourusername/generalscaler-operator/workflows/CI/badge.svg)](https://github.com/yourusername/generalscaler-operator/actions)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A production-ready, generic Kubernetes autoscaling operator that supports pluggable metrics and policies. Scale any deployment using Prometheus, Redis queues, Google Cloud Pub/Sub, or custom metrics, with SLO-based or cost-aware scaling policies.

## Features

- **Pluggable Metric Providers**
  - Prometheus queries
  - Redis queue lengths
  - Google Cloud Pub/Sub backlog
  - Custom HTTP endpoints

- **Flexible Scaling Policies**
  - SLO-based scaling (latency, error rate aware)
  - Cost-aware scaling with budget constraints
  - Simple proportional scaling

- **Production Safety**
  - Configurable cooldown periods
  - Rate limiting (max increment/decrement)
  - Min/max replica bounds
  - Safe scale operations

- **Cloud Native**
  - Custom Resource Definition (CRD)
  - Kubernetes operator pattern
  - Helm chart for easy deployment
  - RBAC-compliant

## Quick Start

### Prerequisites

- Kubernetes cluster (1.19+)
- kubectl configured
- Helm 3.x
- (Optional) kind for local testing

### Installation

#### 1. Using Helm

```bash
# Add Helm repository (if published)
helm repo add generalscaler https://yourusername.github.io/generalscaler-operator
helm repo update

# Install the operator
helm install generalscaler generalscaler/generalscaler \
  --namespace generalscaler-system \
  --create-namespace
```

#### 2. From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/generalscaler-operator.git
cd generalscaler-operator

# Install CRD
kubectl apply -f deploy/crds/generalscaler-crd.yaml

# Install using Helm chart
helm install generalscaler ./helm/generalscaler \
  --namespace generalscaler-system \
  --create-namespace
```

### Create Your First GeneralScaler

#### Example: HTTP Service with Prometheus Metrics

```yaml
apiVersion: autoscaling.generalscaler.io/v1alpha1
kind: GeneralScaler
metadata:
  name: my-app-scaler
  namespace: default
spec:
  # Target deployment to scale
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app

  # Replica constraints
  minReplicas: 2
  maxReplicas: 20

  # Metric configuration
  metric:
    type: prometheus
    targetValue: 100  # Target 100 requests/sec per pod
    prometheus:
      serverUrl: http://prometheus-server.monitoring.svc.cluster.local
      query: 'sum(rate(http_requests_total{app="my-app"}[1m])) / count(up{app="my-app"})'

  # Policy: SLO-based scaling
  policy:
    type: slo
    slo:
      targetLatencyMs: 200
      targetErrorRate: 0.01

  # Scaling behavior
  behavior:
    scaleUp:
      maxIncrement: 5
      cooldownSeconds: 60
    scaleDown:
      maxDecrement: 2
      cooldownSeconds: 300

  syncIntervalSeconds: 30
```

Apply it:

```bash
kubectl apply -f my-generalscaler.yaml
```

Check status:

```bash
kubectl get generalscalers
kubectl describe generalscaler my-app-scaler
```

## Architecture

```
┌─────────────────────────────────────────┐
│  GeneralScaler CR                       │
│  (User-defined scaling configuration)   │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│  GeneralScaler Operator (Python/kopf)   │
│  - Watches GeneralScaler resources      │
│  - Reconciliation loop every N seconds  │
└───────────────┬─────────────────────────┘
                │
     ┌──────────┴──────────┐
     ▼                     ▼
┌─────────────┐    ┌─────────────────┐
│ Metric      │    │ Policy Engine   │
│ Providers   │    │ - SLO-based     │
│ - Prometheus│    │ - Cost-aware    │
│ - Redis     │    └─────────────────┘
│ - Pub/Sub   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Safe Scaler                             │
│  - Cooldown enforcement                  │
│  - Rate limiting                         │
│  - Bounds checking                       │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│  Kubernetes API                          │
│  (Scale Deployment)                      │
└─────────────────────────────────────────┘
```

## Examples

See the [`examples/`](examples/) directory for complete examples:

### 1. HTTP Service (Prometheus)
[examples/http-service/](examples/http-service/)

Scales based on request rate from Prometheus metrics.

```bash
kubectl apply -f examples/http-service/
```

### 2. Worker Service (Redis Queue)
[examples/worker-service/](examples/worker-service/)

Scales based on Redis queue length for background job processing.

```bash
kubectl apply -f examples/worker-service/
```

### 3. Custom Metric Service
[examples/custom-metric/](examples/custom-metric/)

Demonstrates custom business metrics integration.

```bash
kubectl apply -f examples/custom-metric/
```

## Configuration Reference

### Metric Providers

#### Prometheus

```yaml
metric:
  type: prometheus
  targetValue: 100
  prometheus:
    serverUrl: http://prometheus:9090
    query: 'your_prometheus_query'
    headers:  # Optional
      Authorization: Bearer token
```

#### Redis Queue

```yaml
metric:
  type: redis
  targetValue: 50  # Max items per worker
  redis:
    host: redis.default.svc.cluster.local
    port: 6379
    db: 0
    queueName: job-queue
    password: secret  # Optional
```

#### Google Cloud Pub/Sub

```yaml
metric:
  type: pubsub
  targetValue: 100
  pubsub:
    projectId: my-project
    subscriptionId: my-subscription
    credentialsSecret:  # Optional
      name: gcp-credentials
      key: credentials.json
```

### Policies

#### SLO-Based

```yaml
policy:
  type: slo
  slo:
    targetLatencyMs: 200
    targetErrorRate: 0.01
```

#### Cost-Aware

```yaml
policy:
  type: costAware
  costAware:
    maxMonthlyCost: 1000
    costPerPodPerHour: 0.05
    preferredScaleDirection: down  # down, up, or balanced
```

### Scaling Behavior

```yaml
behavior:
  scaleUp:
    maxIncrement: 10      # Max pods to add at once
    cooldownSeconds: 30   # Wait time between scale-ups
  scaleDown:
    maxDecrement: 5       # Max pods to remove at once
    cooldownSeconds: 300  # Wait time between scale-downs
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/generalscaler-operator.git
cd generalscaler-operator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Running Locally

```bash
# Create kind cluster
kind create cluster --name generalscaler-dev

# Install CRD
kubectl apply -f deploy/crds/generalscaler-crd.yaml

# Run operator locally
kopf run --standalone src/generalscaler/operator.py --verbose
```

### Running Tests

```bash
# Lint
flake8 src/ tests/
black --check src/ tests/

# Unit tests
pytest tests/unit/ -v --cov=src/generalscaler

# E2E tests (requires kind cluster)
pytest tests/e2e/ -v
```

### Building Docker Image

```bash
docker build -t generalscaler/operator:latest .
```

## Testing

The project includes comprehensive testing:

- **Unit Tests**: Test individual components (metrics, policies, scaler)
- **E2E Tests**: Test full operator functionality on a real cluster
- **CI Pipeline**: Automated testing on every PR

### Run Unit Tests

```bash
pytest tests/unit/ -v
```

### Run E2E Tests

```bash
# Create kind cluster
kind create cluster --name generalscaler-test

# Run tests
pytest tests/e2e/ -v

# Cleanup
kind delete cluster --name generalscaler-test
```

## CI/CD

The project uses GitHub Actions for CI/CD:

- ✅ Linting (flake8, black, mypy)
- ✅ Unit tests (Python 3.9, 3.10, 3.11)
- ✅ E2E tests (kind cluster)
- ✅ Docker build
- ✅ Helm lint

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml) for details.

## FAQ

### How is this different from HPA?

GeneralScaler is more flexible than Horizontal Pod Autoscaler (HPA):

- ✅ Supports any metric source (not just metrics-server)
- ✅ Pluggable policy engine (SLO, cost-aware)
- ✅ Fine-grained control over scaling behavior
- ✅ Support for complex business metrics

### Can I use this in production?

Yes! GeneralScaler includes production safety features:

- Cooldown periods prevent thrashing
- Rate limits prevent aggressive scaling
- Status updates show current state
- Comprehensive testing

### Does this require GCP?

No! The Pub/Sub metric provider is optional. You can run entirely locally using:
- Prometheus (can run in-cluster)
- Redis (can run in-cluster)
- Custom HTTP endpoints

## Troubleshooting

### Operator not scaling

1. Check operator logs:
   ```bash
   kubectl logs -n generalscaler-system deployment/generalscaler -f
   ```

2. Check GeneralScaler status:
   ```bash
   kubectl describe generalscaler <name>
   ```

3. Verify metric source is accessible:
   ```bash
   kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
     curl http://prometheus-server.monitoring.svc.cluster.local/api/v1/query?query=up
   ```

### Deployment not found error

Ensure the target deployment exists in the same namespace:

```bash
kubectl get deployment -n <namespace>
```

### Metric fetch failures

Check that metric provider configuration is correct and accessible from the operator pod.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run linting and tests
6. Submit a pull request

## License

MIT License. See [LICENSE](LICENSE) file for details.

## Contact

- GitHub Issues: https://github.com/yourusername/generalscaler-operator/issues
- Email: your.email@example.com

## Acknowledgments

Built with:
- [kopf](https://github.com/nolar/kopf) - Kubernetes Operator Pythonic Framework
- [kubernetes-client/python](https://github.com/kubernetes-client/python) - Official Python client for Kubernetes
