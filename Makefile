# Makefile for Lambda Coverage Layer
# Provides convenient commands for building, testing, and deploying the layer

.PHONY: help build test validate deploy clean install-deps version test-synth test-deploy test-destroy test-status load-test load-test-quick load-test-full test-all

# Default target
help:
	@echo "Lambda Coverage Layer - Available Commands:"
	@echo ""
	@echo "Layer Management:"
	@echo "  build          Build the Lambda layer package"
	@echo "  test           Run tests for the layer"
	@echo "  validate       Validate the built layer package"
	@echo "  deploy         Deploy layer to AWS (requires AWS credentials)"
	@echo "  clean          Clean build artifacts"
	@echo ""
	@echo "Testing Infrastructure (CDK):"
	@echo "  test-synth     Synthesize testing infrastructure"
	@echo "  test-deploy    Deploy test Lambda functions and S3 bucket"
	@echo "  test-destroy   Destroy testing infrastructure"
	@echo "  test-status    Show testing infrastructure status"
	@echo ""
	@echo "Load Testing:"
	@echo "  load-test      Run comprehensive load tests"
	@echo "  load-test-quick Run quick load test (1 iteration)"
	@echo "  load-test-full  Run full load test (5 iterations)"
	@echo "  test-all       Complete workflow: build + deploy + test"
	@echo ""
	@echo "Development:"
	@echo "  install-deps   Install development dependencies"
	@echo "  version        Show current version"
	@echo "  bump-patch     Bump patch version"
	@echo "  bump-minor     Bump minor version"
	@echo "  bump-major     Bump major version"
	@echo ""
	@echo "Examples:"
	@echo "  make build                                    # Build the layer"
	@echo "  make deploy                                   # Deploy layer to us-east-1"
	@echo "  make test-deploy                              # Deploy test infrastructure"
	@echo "  make load-test                                # Run load tests"
	@echo "  make test-all                                 # Complete workflow"

# Build the layer
build:
	@echo "Building Lambda Coverage Layer..."
	./scripts/build-layer.sh

# Run tests
test:
	@echo "Running tests..."
	python -m pytest tests/ -v --cov=layer/python/coverage_wrapper --cov-report=html --cov-report=term

# Validate the built package
validate:
	@echo "Validating layer package..."
	./scripts/validate-layer.sh $(if $(VERSION),-v $(VERSION),)

# Deploy the layer
deploy:
	@echo "Deploying layer to AWS (us-east-1)..."
	./scripts/deploy-layer.sh -r us-east-1 $(if $(PROFILE),-p $(PROFILE),)

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf layer/python/coverage_wrapper/__pycache__/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Install development dependencies
install-deps:
	@echo "Installing development dependencies..."
	pip install -r requirements-dev.txt

# Version management
version:
	@./scripts/version-manager.sh current

bump-patch:
	@./scripts/version-manager.sh bump patch

bump-minor:
	@./scripts/version-manager.sh bump minor

bump-major:
	@./scripts/version-manager.sh bump major

# CDK commands for layer deployment
cdk-synth:
	@echo "Synthesizing CDK layer stack..."
	cdk synth

cdk-deploy:
	@echo "Deploying CDK layer stack..."
	cdk deploy

cdk-destroy:
	@echo "Destroying CDK layer stack..."
	cdk destroy

# CDK commands for testing infrastructure
test-synth:
	@echo "Synthesizing CDK stack with testing infrastructure..."
	cdk synth --context include_testing=true

test-deploy:
	@echo "Deploying CDK infrastructure with testing functions..."
	cdk deploy \
		--context include_testing=true \
		--require-approval never \
		--outputs-file cdk-outputs.json

test-destroy:
	@echo "Destroying CDK infrastructure..."
	cdk destroy --force

test-status:
	@echo "Checking CDK testing stack status..."
	@if [ -f "cdk-outputs.json" ]; then \
		echo "Testing infrastructure is deployed:"; \
		echo "  S3 Bucket: $$(jq -r '.LambdaCoverageLayerStack.CoverageBucketName' cdk-outputs.json 2>/dev/null || echo 'N/A')"; \
		echo "  Test Function: $$(jq -r '.LambdaCoverageLayerStack.TestFunctionName' cdk-outputs.json 2>/dev/null || echo 'N/A')"; \
		echo "  Simple Function: $$(jq -r '.LambdaCoverageLayerStack.SimpleTestFunctionName' cdk-outputs.json 2>/dev/null || echo 'N/A')"; \
		echo "  Error Function: $$(jq -r '.LambdaCoverageLayerStack.ErrorTestFunctionName' cdk-outputs.json 2>/dev/null || echo 'N/A')"; \
	else \
		echo "Testing infrastructure not deployed or outputs not available."; \
	fi

# Development workflow
dev-setup: install-deps
	@echo "Setting up development environment..."
	@echo "Development environment ready!"

dev-build: clean build validate
	@echo "Development build complete!"

dev-test: test validate
	@echo "Development testing complete!"

# Release workflow
release-patch: bump-patch build validate
	@echo "Patch release ready!"

release-minor: bump-minor build validate
	@echo "Minor release ready!"

release-major: bump-major build validate
	@echo "Major release ready!"

# Load testing commands
load-test:
	@echo "Running load tests..."
	@if [ ! -f "cdk-outputs.json" ]; then \
		echo "Error: Testing infrastructure not deployed. Run 'make test-deploy LAYER_ARN=...' first"; \
		exit 1; \
	fi
	@BUCKET_NAME=$$(jq -r '.LambdaCoverageLayerStack.CoverageBucketName' cdk-outputs.json 2>/dev/null); \
	TEST_FUNCTION=$$(jq -r '.LambdaCoverageLayerStack.TestFunctionName' cdk-outputs.json 2>/dev/null); \
	SIMPLE_FUNCTION=$$(jq -r '.LambdaCoverageLayerStack.SimpleTestFunctionName' cdk-outputs.json 2>/dev/null); \
	ERROR_FUNCTION=$$(jq -r '.LambdaCoverageLayerStack.ErrorTestFunctionName' cdk-outputs.json 2>/dev/null); \
	if [ "$$BUCKET_NAME" = "null" ] || [ "$$TEST_FUNCTION" = "null" ]; then \
		echo "Error: Could not extract function names from CDK outputs"; \
		exit 1; \
	fi; \
	python load_test.py \
		--functions "$$TEST_FUNCTION,$$SIMPLE_FUNCTION,$$ERROR_FUNCTION" \
		--bucket "$$BUCKET_NAME" \
		--iterations $(if $(ITERATIONS),$(ITERATIONS),2) \
		--workers $(if $(WORKERS),$(WORKERS),3)

load-test-quick:
	@echo "Running quick load test (1 iteration, 2 workers)..."
	@$(MAKE) load-test ITERATIONS=1 WORKERS=2

load-test-full:
	@echo "Running full load test (5 iterations, 5 workers)..."
	@$(MAKE) load-test ITERATIONS=5 WORKERS=5

# Complete testing workflow
test-all: build test-deploy load-test
	@echo "Complete testing workflow finished!"
	@echo "Coverage reports should be available in S3."
	@echo "Run 'make test-status' to see deployment details."