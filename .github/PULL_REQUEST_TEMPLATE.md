# Summary

<!-- What does this PR change and why? Link any related issues. -->

## Type of change

- [ ] Bug fix
- [ ] New feature (new assertion oracle / backend / reporter)
- [ ] Documentation
- [ ] Infrastructure (Containerfile, CI, Terraform, QEMU)

## Checklist

- [ ] `make check` passes (ruff + full test suite in containers)
- [ ] New/changed behavior is covered by tests
- [ ] Docs updated (`docs/`, `README.md`) where relevant
- [ ] For a new assertion type: added to `ASSERTION_TYPES`, documented in
      `docs/assertions.md`, and covered by a unit test
- [ ] For a new backend: registered in `backends/registry.py` and import-guarded
      so the validation core stays SDK-free

## Notes for reviewers

<!-- Anything that needs special attention, trade-offs, or follow-ups. -->
