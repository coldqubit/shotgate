# Contributing to shotgate

Thanks for helping build the missing CI/CD layer for quantum software. This project
favors small, well-tested, well-reasoned changes.

## Ground rules

- Be kind; follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Discuss non-trivial changes in an issue first (especially new assertion oracles or
  backends — they have design implications).
- Keep the **validation core dependency-free** (standard library + pydantic). Quantum
  SDKs are optional extras, imported lazily inside backends only.

## Development workflow (containers only — no host installs)

Everything runs through Podman via the `Makefile`:

```bash
make build        # build the runtime image
make test         # full test suite (unit + integration) in a container
make lint         # ruff in an ephemeral container
make typecheck    # mypy in an ephemeral container
make check        # lint + test (what CI runs)
make run WORKFLOW=examples/bell-state/workflow.yaml
```

Prefer a local virtualenv? It's supported but optional:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[aer,dev]"
pytest -q
```

## Tests

- **Core tests** (`tests/test_metrics.py`, `test_assertions.py`, `test_config.py`,
  `test_report.py`) must run **without** a quantum SDK. Don't import qiskit there.
- **Integration tests** (`tests/test_runner_integration.py`) are marked
  `@pytest.mark.integration` and auto-skip when aer is absent. Run them in the image.
- New behavior needs a test. Statistical code needs a test against a known value or
  quantile.

## Adding an assertion oracle

1. Add a metric to `src/shotgate/validation/metrics.py` (pure Python, unit-tested).
2. Add a pydantic model in `validation/assertions.py` with a unique `type` literal and
   an `evaluate(counts, shots) -> AssertionResult`.
3. Append it to the `Assertion` union and `ASSERTION_TYPES`.
4. Document it in [`docs/assertions.md`](docs/assertions.md) with the math.
5. Add unit tests (pass and fail cases).

## Adding a backend

1. Implement `Backend` in `src/shotgate/backends/<provider>.py`; import the SDK **lazily**
   inside methods and gate `is_available()` on `importlib.util.find_spec`.
2. Register `"module:Class"` in `backends/registry.py`.
3. Add an optional extra in `pyproject.toml`.

## Style & commits

- `ruff` is the linter/formatter of record; `make lint` must pass.
- Type hints everywhere; `make typecheck` should stay clean.
- Conventional-ish commit subjects (`feat:`, `fix:`, `docs:`, `ci:`) appreciated.
- Update [`CHANGELOG.md`](CHANGELOG.md) under "Unreleased".

## Developer Certificate of Origin (DCO)

Contributions are accepted under the [Developer Certificate of Origin](https://developercertificate.org/)
1.1: you certify that you wrote the change, or otherwise have the right to submit it
under the project's [Apache-2.0 License](LICENSE). You assert this by signing off each
commit, which `git commit -s` appends automatically:

```text
Signed-off-by: Your Name <you@example.com>
```

Use a real name and a reachable email; the commit trailer is the one place your identity
is recorded. Commits without a sign-off are asked to amend (`git commit --amend -s`, or
`git rebase --signoff` for a branch). Inbound contributions carry the same Apache-2.0
terms the project ships under (Apache-2.0 section 5), so no separate license assignment
is required.
