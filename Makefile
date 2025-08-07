# Makefile for postgres-mcp-pro-plus
# PostgreSQL Tuning and Analysis Tool

.PHONY: help clean build check test install upload upload-test version bump-patch bump-minor bump-major dev-install lint format

# Default target
help:
	@echo "Available targets:"
	@echo "  help         - Show this help message"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build source and wheel distributions"
	@echo "  check        - Check package before upload"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code"
	@echo "  dev-install  - Install in development mode"
	@echo "  install      - Install package"
	@echo "  upload-test  - Upload to TestPyPI"
	@echo "  upload       - Upload to PyPI"
	@echo "  publish      - Full publish workflow (clean, build, check, upload)"
	@echo "  publish-test - Full test publish workflow (clean, build, check, upload-test)"
	@echo "  version      - Show current version"
	@echo "  bump-patch   - Bump patch version (0.3.0 -> 0.3.1)"
	@echo "  bump-minor   - Bump minor version (0.3.0 -> 0.4.0)"
	@echo "  bump-major   - Bump major version (0.3.0 -> 1.0.0)"

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Clean complete"

# Build distributions
build: clean
	@echo "📦 Building distributions..."
	uv build
	@echo "✅ Build complete"
	@ls -la dist/

# Check package integrity
check:
	@echo "🔍 Checking package..."
	uv run twine check dist/*
	@echo "✅ Check complete"

# Run tests
test:
	@echo "🧪 Running tests..."
	uv run pytest
	@echo "✅ Tests complete"

# Run linting
lint:
	@echo "🔍 Running linting checks..."
	uv run pre-commit run --all-files
	@echo "✅ Linting complete"

# Install in development mode
dev-install:
	@echo "🔧 Installing in development mode..."
	uv sync --dev
	@echo "✅ Development installation complete"

# Install package
install:
	@echo "📥 Installing package..."
	uv sync
	@echo "✅ Installation complete"

# Upload to TestPyPI
upload-test: check
	@echo "🚀 Uploading to TestPyPI..."
	@read -p "Enter TestPyPI API token: " token; \
	uv run twine upload --repository testpypi dist/* --username __token__ --password $$token
	@echo "✅ Upload to TestPyPI complete"
	@echo "📋 Test installation: pip install --index-url https://test.pypi.org/simple/ postgres-mcp-pro-plus"

# Upload to PyPI
upload: check
	@echo "🚀 Uploading to PyPI..."
	@read -p "Enter PyPI API token: " token; \
	uv run twine upload dist/* --username __token__ --password $$token
	@echo "✅ Upload to PyPI complete"
	@echo "📋 Installation: pip install postgres-mcp-pro-plus"

# Full publish workflow
publish: clean build check upload
	@echo "🎉 Package successfully published to PyPI!"

# Full test publish workflow
publish-test: clean build check upload-test
	@echo "🎉 Package successfully published to TestPyPI!"

# Show current version
version:
	@echo "📋 Current version:"
	@grep "^version" pyproject.toml | cut -d'"' -f2

# Version bumping functions
bump-patch:
	@echo "📈 Bumping patch version..."
	@current=$$(grep "^version" pyproject.toml | cut -d'"' -f2); \
	new=$$(echo $$current | awk -F. '{$$3=$$3+1; print $$1"."$$2"."$$3}'); \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped: $$current -> $$new"

bump-minor:
	@echo "📈 Bumping minor version..."
	@current=$$(grep "^version" pyproject.toml | cut -d'"' -f2); \
	new=$$(echo $$current | awk -F. '{$$2=$$2+1; $$3=0; print $$1"."$$2"."$$3}'); \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped: $$current -> $$new"

bump-major:
	@echo "📈 Bumping major version..."
	@current=$$(grep "^version" pyproject.toml | cut -d'"' -f2); \
	new=$$(echo $$current | awk -F. '{$$1=$$1+1; $$2=0; $$3=0; print $$1"."$$2"."$$3}'); \
	sed -i.bak "s/version = \"$$current\"/version = \"$$new\"/" pyproject.toml && rm pyproject.toml.bak; \
	echo "Version bumped: $$current -> $$new"

# Quality checks workflow
qa: lint test
	@echo "✅ Quality assurance checks complete"

# Development workflow
dev: dev-install format lint test
	@echo "✅ Development setup complete"

# Release workflow with version bump
release-patch: bump-patch publish
	@echo "🎉 Patch release complete!"

release-minor: bump-minor publish
	@echo "🎉 Minor release complete!"

release-major: bump-major publish
	@echo "🎉 Major release complete!"

# Environment setup
setup:
	@echo "🔧 Setting up development environment..."
	@command -v uv >/dev/null 2>&1 || { echo "❌ uv is required but not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
	uv sync --dev
	@echo "✅ Environment setup complete"

# Show package info
info:
	@echo "📋 Package Information:"
	@echo "Name: $$(grep "^name" pyproject.toml | cut -d'"' -f2)"
	@echo "Version: $$(grep "^version" pyproject.toml | cut -d'"' -f2)"
	@echo "Description: $$(grep "^description" pyproject.toml | cut -d'"' -f2)"
	@echo "Author: $$(grep "^name" pyproject.toml -A 10 | grep "name =" | tail -1 | cut -d'"' -f2)"
	@echo "License: $$(grep "^license" pyproject.toml | cut -d'"' -f2)"
