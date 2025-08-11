# Makefile for Lambda Coverage Layer
# Provides convenient commands for building, testing, and deploying the layer

.PHONY: help build test validate deploy clean install-deps version

# Default target
help:
	@echo "Lambda Coverage Layer - Available Commands:"
	@echo ""
	@echo "  build          Build the Lambda layer package"
	@echo "  test           Run tests for the layer"
	@echo "  validate       Validate the built layer package"
	@echo "  deploy         Deploy layer to AWS (requires AWS credentials)"
	@echo "  clean          Clean build artifacts"
	@echo "  install-deps   Install development dependencies"
	@echo "  version        Show current version"
	@echo "  bump-patch     Bump patch version"
	@echo "  bump-minor     Bump minor version"
	@echo "  bump-major     Bump major version"
	@echo ""
	@echo "Examples:"
	@echo "  make build                    # Build the layer"
	@echo "  make deploy REGIONS=us-east-1 # Deploy to specific region"
	@echo "  make validate VERSION=1.2.0   # Validate specific version"

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
	@echo "Deploying layer to AWS..."
	./scripts/deploy-layer.sh $(if $(REGIONS),-r $(REGIONS),) $(if $(PROFILE),-p $(PROFILE),)

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

# CDK commands
cdk-synth:
	@echo "Synthesizing CDK stack..."
	cd cdk && cdk synth

cdk-deploy:
	@echo "Deploying CDK stack..."
	cd cdk && cdk deploy

cdk-destroy:
	@echo "Destroying CDK stack..."
	cd cdk && cdk destroy

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