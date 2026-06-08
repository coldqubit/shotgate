# shotgate runtime image — built and run with Podman (rootless-friendly).
#
# Multi-stage:
#   builder  -> installs shotgate + the Aer simulator into an isolated venv
#   test     -> adds dev/test deps + tests for reproducible CI runs (--target test)
#   runtime  -> minimal, non-root image with just the venv (DEFAULT / last stage)
#
# Build:  podman build -t shotgate:dev .                       # -> runtime image (aer)
# IBM:    podman build --build-arg SHOTGATE_EXTRAS="aer,ibm" \
#           -t shotgate:dev-ibm .                              # -> runtime image (aer + IBM Runtime)
# Test:   podman build --target test -t shotgate:test .        # -> test image
# Run:    podman run --rm -v "$PWD:/work:Z" -w /work shotgate:dev run examples/bell-state/workflow.yaml

ARG PYTHON_VERSION=3.12

# --------------------------------------------------------------------------- #
FROM docker.io/library/python:${PYTHON_VERSION}-slim AS builder

# Which optional extras to bake into the image. Default = local Aer simulator only.
# Override with --build-arg SHOTGATE_EXTRAS="aer,ibm" to bake in the cloud/QPU path.
ARG SHOTGATE_EXTRAS=aer

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /src
RUN python -m venv /opt/venv && pip install --upgrade pip

# Copy only what the build needs first (better layer caching).
COPY pyproject.toml README.md ./
COPY src ./src

# Bake in the selected extras so the image works out of the box (offline for aer).
RUN pip install ".[${SHOTGATE_EXTRAS}]"

# --------------------------------------------------------------------------- #
# Test stage: same venv + dev deps + tests. Selected explicitly with --target test.
FROM builder AS test

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /src
RUN pip install ".[aer,dev]"
COPY tests ./tests
COPY examples ./examples
ENTRYPOINT []
CMD ["pytest", "-q"]

# --------------------------------------------------------------------------- #
# Runtime stage: the default image. Kept LAST so `podman build .` yields it.
FROM docker.io/library/python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="shotgate" \
      org.opencontainers.image.description="Container-native CI/CD quality gates for quantum circuits" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/coldqubit/shotgate"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Run as a non-root user; CI runners and rootless Podman both prefer this.
RUN groupadd --gid 1001 shotgate \
 && useradd --uid 1001 --gid 1001 --create-home --shell /usr/sbin/nologin shotgate

COPY --from=builder /opt/venv /opt/venv

USER shotgate
WORKDIR /work

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["shotgate", "--version"]
ENTRYPOINT ["shotgate"]
CMD ["--help"]
