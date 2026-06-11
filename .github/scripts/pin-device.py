# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 coldqubit
"""Pin a backend device into a shotgate workflow file.

Usage: pin-device.py <workflow.yaml> <device>

Sets defaults.backend.name to <device>. With an empty <device> the file is left
untouched, which keeps the least_busy default of the hardware examples.
"""

import sys

import yaml


def main() -> None:
    path, device = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""
    if not device:
        return
    with open(path) as f:
        doc = yaml.safe_load(f)
    doc["defaults"]["backend"]["name"] = device
    with open(path, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False)


if __name__ == "__main__":
    main()
