#!/usr/bin/env bash
#
# create-runner-vm.sh: boot an ephemeral, hardware-isolated shotgate runner.
#
# Why a VM?  CI for quantum circuits should be reproducible and disposable. This
# script boots a throwaway Fedora Cloud micro-VM with KVM acceleration, shares the
# repository into it over virtio-9p, and runs shotgate *inside Podman inside the VM*.
# Nothing is installed on the host except qemu; the base cloud image is never
# mutated (we boot a copy-on-write overlay) and the whole environment is destroyed
# on teardown.
#
#   ./create-runner-vm.sh up      # build seed + boot VM + run WORKFLOW
#   ./create-runner-vm.sh down    # remove overlay, seed ISO and caches
#
# Configuration (environment variables):
#   WORKFLOW       workflow to run inside the VM   (default: examples/bell-state/workflow.yaml)
#   IMAGE_URL      Fedora Cloud Base qcow2 URL     (override if the pinned one 404s)
#   VM_MEM_MB      guest memory                    (default: 2048)
#   VM_CPUS        guest vCPUs                      (default: 2)
#   PODMAN         container engine on the host    (default: podman)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
CACHE_DIR="${HERE}/.cache"

WORKFLOW="${WORKFLOW:-examples/bell-state/workflow.yaml}"
VM_MEM_MB="${VM_MEM_MB:-2048}"
VM_CPUS="${VM_CPUS:-2}"
PODMAN="${PODMAN:-podman}"
IMAGE_URL="${IMAGE_URL:-https://download.fedoraproject.org/pub/fedora/linux/releases/41/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-41-1.4.x86_64.qcow2}"

BASE_IMG="${CACHE_DIR}/base.qcow2"
OVERLAY_IMG="${CACHE_DIR}/overlay.qcow2"
SEED_ISO="${CACHE_DIR}/seed.iso"

log() { printf '\033[1;35m[shotgate-vm]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[shotgate-vm] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

require_kvm() {
  [[ -w /dev/kvm ]] || die "KVM not available (/dev/kvm not writable). Enable virtualization."
  command -v qemu-system-x86_64 >/dev/null || die "qemu-system-x86_64 not found on host."
}

fetch_base_image() {
  mkdir -p "${CACHE_DIR}"
  if [[ -f "${BASE_IMG}" ]]; then
    log "base image already cached"
    return
  fi
  log "downloading Fedora Cloud base image..."
  if command -v curl >/dev/null; then
    curl -fL --retry 3 -o "${BASE_IMG}.part" "${IMAGE_URL}"
  else
    wget -O "${BASE_IMG}.part" "${IMAGE_URL}"
  fi
  mv "${BASE_IMG}.part" "${BASE_IMG}"
}

make_overlay() {
  # Copy-on-write overlay: the base image stays pristine, the VM is disposable.
  log "creating copy-on-write overlay"
  qemu-img create -q -f qcow2 -F qcow2 -b "${BASE_IMG}" "${OVERLAY_IMG}" 20G
}

render_seed_iso() {
  # cloud-init NoCloud datasource: an ISO labelled "cidata" with user-data + meta-data.
  log "rendering cloud-init seed (WORKFLOW=${WORKFLOW})"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "${tmp}"' RETURN

  sed "s|@@WORKFLOW@@|${WORKFLOW}|g" "${HERE}/cloud-init/user-data" > "${tmp}/user-data"
  cp "${HERE}/cloud-init/meta-data" "${tmp}/meta-data"

  if command -v cloud-localds >/dev/null; then
    cloud-localds "${SEED_ISO}" "${tmp}/user-data" "${tmp}/meta-data"
  elif command -v genisoimage >/dev/null; then
    genisoimage -quiet -output "${SEED_ISO}" -volid cidata -joliet -rock \
      "${tmp}/user-data" "${tmp}/meta-data"
  else
    # No host ISO tooling: build the seed in an ephemeral Alpine container.
    log "no host ISO tool; building seed.iso in a container"
    "${PODMAN}" run --rm -v "${tmp}:/seed:Z" docker.io/library/alpine:3.20 sh -c \
      "apk add --no-cache cdrkit >/dev/null && \
       genisoimage -quiet -output /seed/seed.iso -volid cidata -joliet -rock \
       /seed/user-data /seed/meta-data"
    mv "${tmp}/seed.iso" "${SEED_ISO}"
  fi
}

boot_vm() {
  log "booting VM (KVM, ${VM_CPUS} vCPU, ${VM_MEM_MB} MiB), sharing repo over virtio-9p"
  log "the guest will: mount the repo, build the shotgate image, run '${WORKFLOW}', then poweroff"
  qemu-system-x86_64 \
    -name shotgate-runner \
    -machine type=q35,accel=kvm \
    -cpu host -smp "${VM_CPUS}" -m "${VM_MEM_MB}" \
    -nographic -serial mon:stdio \
    -drive if=virtio,file="${OVERLAY_IMG}",format=qcow2 \
    -drive if=virtio,file="${SEED_ISO}",format=raw,readonly=on \
    -netdev user,id=net0 -device virtio-net-pci,netdev=net0 \
    -virtfs local,path="${REPO_ROOT}",mount_tag=shotgate,security_model=mapped-xattr,id=shotgate \
    -no-reboot

  if [[ -f "${REPO_ROOT}/report.xml" ]]; then
    log "report.xml produced by the VM run:"
    head -n 20 "${REPO_ROOT}/report.xml" || true
  fi
}

cmd_up() {
  require_kvm
  fetch_base_image
  make_overlay
  render_seed_iso
  boot_vm
  log "done. tear down with: $0 down"
}

cmd_down() {
  log "removing VM artifacts"
  rm -f "${OVERLAY_IMG}" "${SEED_ISO}"
  rm -f "${REPO_ROOT}/.shotgate-vm-done"
  log "base image kept at ${BASE_IMG} (delete ${CACHE_DIR} to remove it)"
}

case "${1:-up}" in
  up)   cmd_up ;;
  down) cmd_down ;;
  *)    die "usage: $0 {up|down}" ;;
esac
