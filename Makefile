.PHONY: help install lint test test-unit test-e2e clean docker-build kind-create kind-delete deploy undeploy run

help:
	@echo "GeneralScaler Operator - Available targets:"
	@echo "  install       - Install Python dependencies"
	@echo "  lint          - Run linters (flake8, black)"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-e2e      - Run E2E tests only"
	@echo "  clean         - Clean up generated files"
	@echo "  docker-build  - Build Docker image"
	@echo "  kind-create   - Create kind cluster for testing"
	@echo "  kind-delete   - Delete kind cluster"
	@echo "  deploy        - Deploy operator to current cluster"
	@echo "  undeploy      - Remove operator from current cluster"
	@echo "  run           - Run operator locally (requires cluster)"

install:
	pip install -r requirements.txt
	pip install -e .

lint:
	@echo "Running flake8..."
	flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 src/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	@echo "Running black..."
	black --check src/ tests/
	@echo "Running mypy..."
	mypy src/ --ignore-missing-imports || true

format:
	black src/ tests/

test: test-unit

test-unit:
	pytest tests/unit/ -v --cov=src/generalscaler --cov-report=term --cov-report=html

test-e2e:
	pytest tests/e2e/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov/ dist/ build/

docker-build:
	docker build -t generalscaler/operator:latest .

kind-create:
	kind create cluster --name generalscaler-dev --wait 60s
	kubectl cluster-info

kind-delete:
	kind delete cluster --name generalscaler-dev

deploy:
	@echo "Installing CRD..."
	kubectl apply -f deploy/crds/generalscaler-crd.yaml
	@echo "Installing operator via Helm..."
	helm upgrade --install generalscaler ./helm/generalscaler \
		--namespace generalscaler-system \
		--create-namespace \
		--wait

undeploy:
	helm uninstall generalscaler -n generalscaler-system || true
	kubectl delete crd generalscalers.autoscaling.generalscaler.io || true

run:
	@echo "Running operator locally (use Ctrl+C to stop)..."
	kopf run --standalone src/generalscaler/operator.py --verbose

# Example deployments
deploy-examples:
	@echo "Deploying example applications..."
	kubectl apply -f examples/http-service/deployment.yaml
	kubectl apply -f examples/worker-service/deployment.yaml
	kubectl apply -f examples/custom-metric/deployment.yaml
	@echo "Waiting for deployments to be ready..."
	sleep 10
	kubectl apply -f examples/http-service/generalscaler.yaml
	kubectl apply -f examples/worker-service/generalscaler.yaml
	kubectl apply -f examples/custom-metric/generalscaler.yaml
	@echo "Examples deployed! Check status with: kubectl get generalscalers"

undeploy-examples:
	kubectl delete -f examples/http-service/ || true
	kubectl delete -f examples/worker-service/ || true
	kubectl delete -f examples/custom-metric/ || true
