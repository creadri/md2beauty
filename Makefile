# Makefile for md2beauty
# Usage: make <target>

SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c

# ---- Config ----
PYTHON ?= python3
VENV_DIR ?= .venv
PY := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest
TWINE := $(VENV_DIR)/bin/twine
NPM ?= npm

PACKAGE_NAME := md2beauty
DIST_DIR := dist
BUNDLE_OUT := md2beauty/js_renderers/mermaid.bundle.mjs
HTML_DOC_FOLDER := site

.PHONY: help venv install-dev npm-install bundle init test build check-dist install-local publish ci clean distclean clean-venv clean-node system-deps release tag docs-install docs-serve docs-build docs-deploy

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---- Environment setup ----

$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)
	$(PY) -m pip install --upgrade pip setuptools wheel

venv: $(VENV_DIR) ## Create Python virtual environment (.venv)

install-dev: venv ## Install project in editable mode with runtime + test/packaging tools
	$(PIP) install -U pip setuptools wheel
	# Project extras (runtime). Dev tooling is handled via npm for JS.
	$(PIP) install -e '.[all]'
	# Test and packaging tools
	$(PIP) install pytest pytest-cov build twine

system-deps: ## Install system packages required for PDF rendering (Ubuntu/Debian). Requires sudo.
	@echo "Installing system dependencies for WeasyPrint (requires sudo)..."
	@command -v sudo >/dev/null 2>&1 || { echo "sudo not found. Attempting without sudo (container/root?)."; SUDO=; }; \
	${SUDO:-sudo} apt-get update && \
	${SUDO:-sudo} apt-get install -y --no-install-recommends \
		libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
		libcairo2 libgdk-pixbuf-2.0-0 libffi8 libglib2.0-0 libxml2 \
		fonts-dejavu-core && \
	${SUDO:-sudo} apt-get clean && \
	rm -rf /var/lib/apt/lists/*

npm-install: ## Install Node.js dev dependencies
	@if command -v $(NPM) >/dev/null 2>&1; then \
		if [ -f package-lock.json ]; then \
			$(NPM) ci; \
		else \
			$(NPM) install; \
		fi; \
	else \
		echo "[WARN] npm not found. Mermaid bundling will be skipped unless installed."; \
	fi

bundle: npm-install ## Bundle Mermaid renderer to $(BUNDLE_OUT)
	@if command -v $(NPM) >/dev/null 2>&1; then \
		$(NPM) run bundle:mermaid; \
	else \
		echo "[WARN] Skipping bundle: npm not found."; \
	fi

init: install-dev bundle ## Setup dev environment (venv + deps) and bundle assets

# ---- Quality & Tests ----

test: ## Run test suite (pytest)
	MD2BEAUTY_DEBUG=1 $(PYTEST)

# ---- Build & Release ----

build: bundle ## Build sdist and wheel in ./dist
	$(PY) -m build
	@ls -l $(DIST_DIR) || true

check-dist: ## Validate built artifacts metadata with twine
	$(TWINE) check $(DIST_DIR)/*

install-local: ## Install the wheel from ./dist into the venv
	@ls $(DIST_DIR)/*.whl >/dev/null 2>&1 || (echo "No wheel found in $(DIST_DIR). Run 'make build' first." && false)
	$(PIP) install -U $(DIST_DIR)/*.whl

publish: check-dist ## Publish dist/* to PyPI using TWINE_USERNAME/PASSWORD or token
	$(TWINE) upload $(DIST_DIR)/*

release: clean build check-dist ## Build and validate release artifacts
	@echo "Artifacts in $(DIST_DIR):" && ls -l $(DIST_DIR) || true

tag: ## Create and push a git tag. Usage: make tag VERSION=1.2.3
	@test -n "$(VERSION)" || (echo "VERSION is required, e.g., make tag VERSION=1.2.3" && false)
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	git push origin v$(VERSION)

ci: ## Run tests then build (used locally to simulate CI)
	$(PYTEST)
	$(PY) -m build

# ---- Docs ----

docs-install: venv ## Install documentation tooling (MkDocs + plugins)
	$(PIP) install -U pip
	$(PIP) install -e '.[docs]'

docs-serve: ## Serve docs locally with live reload
	$(VENV_DIR)/bin/mkdocs serve -d $(HTML_DOC_FOLDER) -a 0.0.0.0:8000

docs-build: ## Build the documentation site into ./site
	$(VENV_DIR)/bin/mkdocs build -d) $(HTML_DOC_FOLDER)

docs-deploy: ## Deploy documentation to GitHub Pages
	$(VENV_DIR)/bin/mkdocs gh-deploy --force

# ---- Cleaning ----

clean: ## Remove build/test artifacts
	rm -rf $(DIST_DIR) build *.egg-info
	rm -rf .pytest_cache .coverage coverage.xml htmlcov
	find . -name '__pycache__' -type d -exec rm -rf {} +
	rm -f $(BUNDLE_OUT)

clean-venv: ## Remove Python virtual environment
	rm -rf $(VENV_DIR)

clean-node: ## Remove Node.js artifacts
	rm -rf node_modules

distclean: clean clean-venv clean-node ## Full cleanup: build artifacts, venv, node_modules
