#!/usr/bin/env bash
#
# demo.sh — build the shotgate image and run every example workflow as a gate.
# Pure Podman; nothing is installed on the host.
#
#   ./scripts/demo.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PODMAN="${PODMAN:-podman}"
IMAGE="${IMAGE:-shotgate:demo}"

cd "${REPO_ROOT}"

echo "==> building ${IMAGE}"
"${PODMAN}" build -t "${IMAGE}" .

# Map the host user through the container userns so any report files are owned by us.
USERMAP=(--userns=keep-id --user "$(id -u):$(id -g)")

rc=0
for wf in examples/*/workflow.yaml; do
  # Skip hardware examples — they target a real QPU and need SHOTGATE_IBM_TOKEN.
  case "${wf}" in
    *-hardware/*) echo "==> skipping ${wf} (needs a real QPU / token)"; continue ;;
  esac
  echo
  echo "==> shotgate run ${wf}"
  if ! "${PODMAN}" run --rm "${USERMAP[@]}" -v "${REPO_ROOT}:/work:Z" -w /work "${IMAGE}" run "${wf}"; then
    rc=1
  fi
done

echo
if [ "${rc}" -eq 0 ]; then
  echo "All example workflows passed ✅"
else
  echo "Some example workflows failed ❌" >&2
fi
exit "${rc}"
