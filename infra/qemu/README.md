# Ephemeral KVM/QEMU runner

Run a qforge workflow inside a **disposable, hardware-isolated virtual machine**.
This is the strongest isolation tier: the workflow (and any untrusted circuit) runs
in a throwaway Fedora Cloud VM, and qforge itself runs in a Podman container *inside*
that VM. The host only needs `qemu` and `/dev/kvm`.

```
host (qemu) ──► KVM micro-VM (Fedora Cloud, cloud-init) ──► Podman ──► qforge ──► report
        repo shared in over virtio-9p ◄── report.xml / report.json written back
```

## Requirements

- A writable `/dev/kvm` (hardware virtualization enabled).
- `qemu-system-x86_64` on the host.
- `podman` on the host (used as a fallback to build the cloud-init seed ISO when
  `cloud-localds`/`genisoimage` are absent — keeping with "no host installs").

## Usage

```bash
# Boot the VM, build qforge inside it, run the Bell-state workflow, write report.xml
make vm-up WORKFLOW=examples/bell-state/workflow.yaml

# Or call the script directly
WORKFLOW=examples/ghz-state/workflow.yaml infra/qemu/create-runner-vm.sh up

# Tear down the overlay + seed (base image stays cached)
make vm-down
```

## What happens

1. **Fetch** the Fedora Cloud base image (cached in `infra/qemu/.cache/`).
2. **Overlay** a copy-on-write qcow2 so the base is never mutated — the VM is disposable.
3. **Seed** a cloud-init NoCloud ISO (`user-data` + `meta-data`) with the chosen workflow.
4. **Boot** with `-machine accel=kvm`, sharing the repo read/write over `virtio-9p`.
5. Inside the guest, cloud-init installs Podman, builds the qforge image, runs the
   workflow, writes `report.xml`/`report.json` to the shared repo, and powers off.

## Notes

- The pinned `IMAGE_URL` may age out; override it for your Fedora version:
  `IMAGE_URL=https://.../Fedora-Cloud-Base-Generic-XX.qcow2 make vm-up`.
- `security_model=mapped-xattr` keeps host file ownership sane across the 9p share.
- This is intentionally heavier than the plain container flow (`make run`). Use it
  when you need VM-grade isolation between pipeline stages or when running circuits
  from untrusted sources.
