---
name: "pypi-publishing"
displayName: "PyPI Publishing with uv"
description: "Quick guide to build and publish Python packages to PyPI using uv"
keywords: ["pypi", "uv", "python", "publish", "package"]
author: "Henry Bui"
---

# PyPI Publishing with uv

## Overview

This power guides you through publishing Python packages to PyPI using `uv`, the fast Python package manager. It covers the essential steps: configuring your project, building the distribution, and uploading to PyPI.

## Onboarding

### Prerequisites

- Python 3.8+
- `uv` installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- A PyPI account ([register here](https://pypi.org/account/register/))
- A PyPI API token ([create one here](https://pypi.org/manage/account/token/))

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv

# Or via Homebrew
brew install uv
```

### Verify Installation

```bash
uv --version
```

## Common Workflows

### Workflow 1: Configure Your Project

Ensure your `pyproject.toml` has the required metadata:

```toml
[project]
name = "your-package-name"
version = "0.1.0"
description = "A short description of your package"
readme = "README.md"
requires-python = ">=3.8"
authors = [
    { name = "Your Name", email = "you@example.com" }
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Key fields:**
- `name`: Your package name on PyPI (must be unique)
- `version`: Semantic version (update before each release)
- `description`: Shows on PyPI listing
- `readme`: Path to your README file

### Workflow 2: Build the Package

```bash
# Build source distribution and wheel
uv build
```

This creates files in the `dist/` directory:
- `your_package-0.1.0.tar.gz` (source distribution)
- `your_package-0.1.0-py3-none-any.whl` (wheel)

### Workflow 3: Publish to PyPI

```bash
# Publish to PyPI (will prompt for token)
uv publish
```

**Using an API token:**

```bash
# Set token via environment variable
export UV_PUBLISH_TOKEN=pypi-your-token-here
uv publish

# Or pass directly (less secure)
uv publish --token pypi-your-token-here
```

### Complete Example

```bash
# 1. Update version in pyproject.toml
# 2. Build
uv build

# 3. Publish
export UV_PUBLISH_TOKEN=pypi-your-token-here
uv publish

# 4. Verify on PyPI
# Visit: https://pypi.org/project/your-package-name/
```

## Troubleshooting

### Error: "File already exists"

**Cause:** You're trying to upload a version that already exists on PyPI.

**Solution:** Bump the version in `pyproject.toml` and rebuild:
```bash
# Update version in pyproject.toml, then:
uv build
uv publish
```

### Error: "Invalid API token"

**Cause:** Token is incorrect or expired.

**Solution:**
1. Go to [PyPI Account Settings](https://pypi.org/manage/account/token/)
2. Create a new API token
3. Use the new token (starts with `pypi-`)

### Error: "Package name already taken"

**Cause:** Someone else owns that package name on PyPI.

**Solution:** Choose a different, unique name in `pyproject.toml`.

### Error: "Missing required metadata"

**Cause:** `pyproject.toml` is missing required fields.

**Solution:** Ensure you have at minimum:
- `name`
- `version`
- `[build-system]` section

## Best Practices

- Always test your package locally before publishing: `uv pip install -e .`
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Keep your API token secure - use environment variables, not command line args
- Clean old builds before rebuilding: `rm -rf dist/`
- Include a good README.md - it's your PyPI landing page

## Quick Reference

| Command | Description |
|---------|-------------|
| `uv build` | Build source dist and wheel |
| `uv publish` | Upload to PyPI |
| `uv publish --token TOKEN` | Upload with explicit token |

---

**Tool:** `uv`
**Documentation:** https://docs.astral.sh/uv/
