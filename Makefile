# qforge — Podman/QEMU task runner.
#
# Everything runs in containers or VMs; nothing is installed on the host.
# Override any variable on the command line, e.g.  make run WORKFLOW=examples/ghz-state/workflow.yaml

PODMAN      ?= podman
IMAGE       ?= qforge:dev
TEST_IMAGE  ?= qforge:test
WORKFLOW    ?= examples/bell-state/workflow.yaml
PYTHON_VERSION ?= 3.12

# Mount the repo read/write with an SELinux relabel (:Z) for Fedora/RHEL hosts.
MOUNT       := -v "$(CURDIR):/work:Z" -w /work
RUN         := $(PODMAN) run --rm $(MOUNT)

# Map the invoking host user through the container's user namespace so that
# report files written to the bind mount are owned by you — while the image
# keeps its non-root default user. The standard Podman idiom for this case.
USERMAP     := --userns=keep-id --user $(shell id -u):$(shell id -g)

.DEFAULT_GOAL := help

## ----------------------------------------------------------------------------
## Images
## ----------------------------------------------------------------------------

.PHONY: build
build: ## Build the qforge runtime image (qiskit + Aer baked in)
	$(PODMAN) build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) -t $(IMAGE) .

.PHONY: build-test
build-test: ## Build the test image (adds dev deps + tests)
	$(PODMAN) build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) --target test -t $(TEST_IMAGE) .

## ----------------------------------------------------------------------------
## Run / validate workflows
## ----------------------------------------------------------------------------

.PHONY: run
run: build ## Run WORKFLOW as a CI quality gate (exit 1 on failure)
	$(PODMAN) run --rm $(USERMAP) $(MOUNT) $(IMAGE) run $(WORKFLOW) --junit report.xml --json report.json

.PHONY: validate
validate: build ## Schema-validate WORKFLOW without executing it
	$(RUN) $(IMAGE) validate $(WORKFLOW)

.PHONY: backends
backends: build ## List backends and whether their dependencies are installed
	$(RUN) $(IMAGE) backends

.PHONY: shell
shell: build ## Open a shell inside the runtime image
	$(PODMAN) run --rm -it $(MOUNT) --entrypoint /bin/bash $(IMAGE)

## ----------------------------------------------------------------------------
## Quality gates
## ----------------------------------------------------------------------------

.PHONY: test
test: build-test ## Run the full test suite (unit + integration) in a container
	$(PODMAN) run --rm $(TEST_IMAGE) pytest -q

.PHONY: lint
lint: ## Run ruff in an ephemeral container
	$(RUN) docker.io/library/python:$(PYTHON_VERSION)-slim \
		bash -c "pip install -q ruff && ruff check src tests"

.PHONY: typecheck
typecheck: ## Run mypy in an ephemeral container
	$(RUN) docker.io/library/python:$(PYTHON_VERSION)-slim \
		bash -c "pip install -q -e '.[dev]' && mypy"

.PHONY: check
check: lint test ## Lint + test (what CI runs)

## ----------------------------------------------------------------------------
## Infrastructure: KVM/QEMU micro-VM and Terraform
## ----------------------------------------------------------------------------

.PHONY: vm-up
vm-up: ## Boot an ephemeral KVM/QEMU runner VM and execute WORKFLOW inside it
	WORKFLOW=$(WORKFLOW) infra/qemu/create-runner-vm.sh up

.PHONY: vm-down
vm-down: ## Tear down the QEMU runner VM and its artifacts
	infra/qemu/create-runner-vm.sh down

.PHONY: tf-plan
tf-plan: ## terraform plan for the example IaC stack (runs terraform in a container)
	$(RUN) docker.io/hashicorp/terraform:latest -chdir=infra/terraform/examples/basic init -input=false
	$(RUN) docker.io/hashicorp/terraform:latest -chdir=infra/terraform/examples/basic plan -input=false

## ----------------------------------------------------------------------------
## Housekeeping
## ----------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts and local reports
	$(RUN) docker.io/library/python:$(PYTHON_VERSION)-slim \
		bash -c "rm -rf build dist .pytest_cache .ruff_cache .mypy_cache **/__pycache__ report.xml report.json"

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
