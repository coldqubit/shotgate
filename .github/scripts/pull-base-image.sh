#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
#
# Pull an image from its canonical registry with retries; on failure fall back to a
# mirror and retag it under the canonical name. Later `podman build` / `podman run`
# steps then resolve the canonical reference from local storage (pull policy
# "missing") instead of the network.
#
# Why: Docker Hub (registry-1.docker.io) is intermittently unreachable from CI
# runners for minutes at a time (observed 2026-06-10: i/o timeouts for >3 min, which
# exhausts podman's built-in 3 retries). A second registry hosting the same official
# image removes that single point of failure.
#
# Usage: pull-base-image.sh <canonical-ref> [mirror-ref]

set -euo pipefail

canonical="$1"
mirror="${2:-}"

pull_with_retries() {
  local img="$1" attempts=5 delay=10 i
  for i in $(seq 1 "$attempts"); do
    if podman pull "$img"; then
      return 0
    fi
    echo "pull ${img} failed (attempt ${i}/${attempts}); retrying in ${delay}s" >&2
    sleep "$delay"
    delay=$((delay * 2))
  done
  return 1
}

if pull_with_retries "$canonical"; then
  exit 0
fi

if [ -z "$mirror" ]; then
  echo "no mirror configured for ${canonical}; giving up" >&2
  exit 1
fi

echo "falling back to mirror ${mirror}" >&2
pull_with_retries "$mirror"
podman tag "$mirror" "$canonical"
