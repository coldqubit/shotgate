# Motivation: the quantum × DevOps gap

This document records *why* qforge exists — the market and community signals that
point to a real, currently-unmet need — and how qforge is positioned against them.

## The shape of the gap

Quantum tooling is mature at the **bottom** of the stack (writing and running
circuits) and immature at the **DevOps** layer (orchestration, automated testing,
infrastructure-as-code). The "write a circuit" problem is solved by excellent SDKs —
Qiskit, Cirq, PennyLane, pytket, Q# — and cloud access via IBM Quantum, AWS Braket,
and Azure Quantum. What's missing is everything a software-delivery org expects
*around* that core.

| Layer | State of the art |
| --- | --- |
| Circuit authoring / simulation | **Mature** (Qiskit, Cirq, Aer, …) |
| Cloud execution | **Mature** (IBM, Braket, Azure) |
| Error mitigation | **Emerging** (Mitiq) |
| **Statistical testing in CI/CD** | **Research prototypes only** |
| **Cross-provider orchestration** | **Fragmented / absent** |
| **IaC for quantum workloads** | **Effectively empty** |

## Three corroborated signals

**1. Probabilistic output breaks classical CI — and there's no standard fix.**
Industry DevOps guidance is explicit that *"unlike deterministic classical programs,
quantum algorithms often produce probabilistic results, requiring specialized
validation and error mitigation strategies in CI/CD pipelines,"* and that
*"DevOps thrives on testing, but quantum computing lacks robust test frameworks."*

**2. The correct techniques exist only as academic prototypes.** The research
literature has converged on statistical oracles — chi-square goodness-of-fit, total
variation distance, Hellinger fidelity — and on the reality of *flaky* quantum tests
(one study executes a Qiskit test suite 10,000× across 23 releases to characterize
flakiness). Frameworks like QUTest, QuCheck, and QUT implement statistical and
probabilistic assertions. **But these live in papers and prototypes, not in a
maintained, container-native tool wired into mainstream CI/CD.**

**3. Infrastructure-as-Code can't describe quantum workloads.** DevOps analyses note
that *"Terraform modules and Helm charts may need support for quantum backends,
simulators…"* — i.e. they don't today. The one Terraform "quantum" provider in the
wild (`coveooss/terraform-provider-quantum`) is unrelated to circuits; it manipulates
JSON. The IaC space for real quantum workloads is empty.

## How qforge is positioned

qforge **productizes the academically-validated statistical oracles** into a single,
container-native CLI and wraps them in the DevOps surfaces that are missing:

- A declarative **"workflow as code"** schema (validated YAML).
- The statistical **assertion catalog** (χ², TVD, Hellinger fidelity, marginal
  probability, structural leakage) as a first-class CI quality gate.
- CI-native **reporting** (JUnit/JSON/Markdown) and **exit-code gating**.
- A **Terraform module** and **KVM/QEMU isolation tier** for the IaC / runtime story.

It deliberately does **not** reinvent circuit authoring or simulation — it stands on
the mature SDKs and fills the layer above them.

## Honest framing

The demand today is **anticipatory**: few organizations run quantum workloads in
production at a scale that *requires* an industrial pipeline. The near-term value of
qforge is therefore as much about **positioning and capability** — being early and
credible at the DevOps × quantum junction — as about immediate commercial pull. The
design reflects that: minimal but scalable, with clean extension points so it can grow
as the hybrid classical-quantum model matures.

## Sources

Community and industry guidance (DevOps.com / DEVOPSdigest, Red Hat Developer,
Microsoft Quantum DevOps blog) on quantum-ready DevOps and probabilistic CI/CD;
academic work on quantum software testing and statistical oracles (QUTest, QuCheck,
QUT; chi-square-as-oracle; flaky-test characterization) via arXiv / IEEE; the SDK and
provider ecosystem (Qiskit, Cirq, Aer, IBM Quantum, AWS Braket, Mitiq); and the prior
art of `coveooss/terraform-provider-quantum`.
