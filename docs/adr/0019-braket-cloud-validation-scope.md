# ADR-0019: Braket cloud-hardware validation is out of maintainer scope

- **Status:** Accepted
- **Date:** 2026-07-11

## Context

ADR-0011 shipped the Braket backend with two paths: local simulation (`LocalSimulator` via
`qiskit-braket-provider`, no AWS account, no cost, validated in CI) and cloud devices (set
`backend.name` to a real QPU or on-demand simulator, requires AWS credentials). The cloud path
has been implemented but never exercised against real Braket hardware. Every roadmap document
in this project (README, `TECHNICAL-ROADMAP.md`) has so far framed that gap as temporary,
"blocked on an AWS account with Braket access," implying it would close once the account
existed.

AWS's published Braket pricing (aws.amazon.com/braket/pricing, checked 2026-07-11) makes that
framing inaccurate. The free tier is one hour per month of the `SV1` simulator for the account's
first twelve months; it does not cover any real QPU. Real hardware carries a flat $0.30 per-task
fee plus a per-shot fee that is provider-dependent: $0.000425 (Rigetti Cepheus) up to $0.08
(IonQ Forte), with AQT, QuEra, and IQM devices in between. A single 4096-shot run, the shot count
this project's IBM hardware baseline uses, costs roughly $1.74 on the cheapest provider
(Rigetti) to $328 on the most expensive (IonQ). Reserved-capacity mode (Braket Direct) is
$2,500-$7,000 per hour. There is no free or low-cost tier for real QPU access at any provider,
regardless of which one is cheapest per shot.

The dollar figures alone are not the binding constraint (Rigetti's ~$2/run is not prohibitive).
The binding constraint is the standing commitment behind it: creating and funding a new AWS
account, managing its billing and credentials, and re-validating whenever the specific reserved
device rotates or is deprecated, for a solo maintainer who is explicitly a ~5h/week contributor
(`STRATEGY.md`) balancing employment, a degree, and an IEEE paper ahead of shotgate. An
open-ended, self-funded cloud account is a different category of cost than the engineering work
every other roadmap item on this list requires.

## Decision

- **The maintainer will not create an AWS account or spend personal funds to validate the
  Braket cloud path against real hardware, as a standing policy, not a temporary blocker
  pending resources.** This removes the "second real-hardware-validated backend" clause of the
  1.0 definition of done as originally scoped; the requirement becomes "at least one
  real-hardware-validated backend (IBM, done 2026-06-11) plus at least one additional backend
  validated in cloud simulation with no account required (Braket local, ADR-0011)."
- **The local Braket path remains the validated, documented, default path** and is what this
  project claims: `LocalSimulator`, no AWS account, no cost, exercised in CI.
- **Real-hardware Braket validation is welcomed as a community contribution, not promised as a
  maintainer deliverable.** A contributor with their own AWS Braket access can run the existing
  `hardware-validation`-style workflow against a real device and submit the result; if that
  happens, it is folded into `docs/hardware-validation.md` as a community-contributed section,
  credited to the contributor, the same evidentiary bar as the maintainer's own IBM section.
  Absent that, the item does not recur on the maintainer's own roadmap.
- Removed from README's "Toward 1.0" list and from `TECHNICAL-ROADMAP.md`'s "Remaining toward
  1.0.0" numbered list; noted as community-contribution-only in both.

## Consequences

- **+** The 1.0 milestone is no longer indefinitely blocked on an external dependency (an AWS
  account and its ongoing cost) that only the maintainer could unblock. Every remaining
  "toward 1.0" item is now closable by engineering time alone.
- **+** Honest: the project stops claiming a real-hardware validation is "planned" for
  something the maintainer has explicitly decided not to fund. The local Braket path, which is
  fully validated today, remains the first-class claim.
- **+** Leaves a real, documented door open for community contribution without making it a
  project promise or a release blocker.
- **-** shotgate cannot claim validation on two independent real quantum hardware providers,
  only one (IBM). This is narrower than the hardware-validation story `TECHNICAL-ROADMAP.md`
  originally aimed for.
- **-** If a reviewer specifically checks for multi-vendor real-hardware validation, shotgate
  shows only IBM. Mitigated by this ADR being explicit about why: a documented policy decision
  costed against real pricing data, not an oversight or a stalled task.
