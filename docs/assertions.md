# Assertion Catalog (Statistical Oracles)

Quantum measurement outcomes are samples from a distribution. An assertion is a
*statistical oracle*: it decides whether the observed sample is consistent with an
expected distribution or property. This page gives the math, the YAML, and guidance
on choosing thresholds.

Notation: let $p$ be the **observed** distribution (normalised shot counts over
bitstrings) and $q$ the **expected** distribution. The domain $\mathcal{D}$ is the
union of their supports; bitstring keys are whitespace-stripped before comparison.

---

## `distribution_tvd`: Total Variation Distance

$$ \mathrm{TVD}(p, q) = \tfrac{1}{2} \sum_{x \in \mathcal{D}} |p(x) - q(x)| \in [0, 1] $$

Passes when $\mathrm{TVD} \le$ `max_distance`. **The recommended default oracle:**
interpretable (it's the maximum probability disagreement on any event), symmetric,
and not sensitive to shot count.

```yaml
- type: distribution_tvd
  expected: { "00": 0.5, "11": 0.5 }
  max_distance: 0.03
```

Typical thresholds: `0.01–0.03` on a noiseless simulator, `0.05–0.15` on noisy
hardware (the measured ibm_fez Bell TVD was 0.1284 at 4096 shots; see the
[hardware baseline](hardware-validation.md#9-measured-baseline-ibm_fez-2026-06-11)).

---

## `hellinger_fidelity`: Classical Fidelity

With the Bhattacharyya coefficient $\mathrm{BC}(p,q) = \sum_x \sqrt{p(x)\,q(x)}$,

$$ F(p, q) = \mathrm{BC}(p, q)^2 \in [0, 1] $$

Passes when $F \ge$ `min_fidelity`. Identical to
`qiskit.quantum_info.hellinger_fidelity`. Fidelity emphasises overlap and is a common
single-number "closeness" score to track across commits.

```yaml
- type: hellinger_fidelity
  expected: { "00": 0.5, "11": 0.5 }
  min_fidelity: 0.99
```

---

## `chi_square`: Pearson Goodness-of-Fit

With $N$ shots, expected counts $E_x = N q(x)$ and observed $O_x = N p(x)$:

$$ \chi^2 = \sum_{x \in \mathcal{D}} \frac{(O_x - E_x)^2}{E_x}, \qquad \mathrm{dof} = |\mathcal{D}| - 1 $$

The p-value is the chi-square survival function $Q(\mathrm{dof}/2,\ \chi^2/2)$,
computed from the regularised incomplete gamma function (no SciPy). Passes when
**p-value $\ge$ `significance`**, i.e. we *fail to reject* the hypothesis that the
counts came from $q$.

```yaml
- type: chi_square
  expected: { "00": 0.5, "11": 0.5 }
  significance: 0.01     # alpha
```

Notes & caveats:

- This is the formal hypothesis test used in the quantum-testing literature as an
  oracle. A **smaller** `significance` (e.g. `0.01`) makes the gate more permissive
  (rejects only strong evidence of mismatch), reducing flakiness.
- Outcomes expected with probability 0 but observed (leakage) push the statistic up
  and the p-value down, so the test correctly fails. (Internally, expected counts are
  floored at a tiny epsilon to keep the statistic finite.)
- Classical validity expects $E_x \gtrsim 5$ per category; with many categories and
  few shots, prefer `distribution_tvd`.
- **Simulator-only (enforced).** `chi_square` compares against the *exact* `expected`, so on
  a real device the leakage onto error states the ideal assigns zero probability forces
  rejection regardless of `significance` (on `ibm_fez`, Bell, 4096 shots, it returned p-value
  0.0000 on counts whose TVD 0.1350 and fidelity 0.8650 passed). The oracle therefore **fails
  closed on real hardware** with a message pointing at the noise-tolerant oracles, rather than
  reporting a guaranteed, uninformative failure. Gate hardware with `distribution_tvd`,
  `hellinger_fidelity`, or `allowed_states`. The mechanism and the record of three attempts to
  make it hardware-capable (a readout transform, auto-calibrated readout, and a full
  `NoiseModel.from_backend` digital twin, all retired in 0.7.0) are in
  [ADR-0015](adr/0015-chi-square-simulator-only.md) and
  [hardware-validation.md](hardware-validation.md#9-measured-baseline-ibm_fez-2026-06-11)
  sections 9-12. To experiment with those modes, pin `shotgate==0.6.x`.

---

## `state_probability`: Marginal Outcome Probability

Bounds the measured probability of a single basis state $s$: $p(s)$.

```yaml
# window form
- type: state_probability
  state: "11"
  min: 0.99
# target form
- type: state_probability
  state: "00"
  equals: 0.5
  tolerance: 0.02
```

Passes when all provided constraints hold: `min` $\le p(s)$, $p(s) \le$ `max`, and/or
$|p(s) - \text{equals}| \le$ `tolerance`. At least one of `min`/`max`/`equals` is
required. Ideal for amplitude-amplification checks (e.g. Grover's marked state).

The result also reports a 95% Wilson confidence interval on the measured probability
(`ci95_lower`/`ci95_upper` in `metrics`, and in the message), so a passing or failing result
also shows how tightly `shots` actually constrains $p(s)$: `P(11) = 0.62 (95% CI [0.53, 0.70])`
at 100 shots reads very differently from the same point estimate at 100000 shots, even though
both might cross the same `min`. See [ADR-0017](adr/0017-statistical-power-tooling.md) and
`shotgate shots` below for planning the shot count a target interval width needs.

---

## `allowed_states`: Structural / Leakage Oracle

Bounds the probability mass measured **outside** an allowed support set:

$$ \text{leakage} = \sum_{x \notin S} p(x) $$

```yaml
- type: allowed_states
  states: ["000", "111"]
  max_leakage: 0.005
```

Passes when $\text{leakage} \le$ `max_leakage`. Encodes structural truths
independent of exact probabilities: a perfect GHZ state only occupies the all-zero
and all-one corners; anything else is error/leakage.

---

## `kl_divergence`: Kullback-Leibler Divergence

$$ D(p \,\|\, q) = \sum_{x} p(x)\,\log_2 \frac{p(x)}{q(x)} \ \ge 0 $$

Passes when $D(p \,\|\, q) \le$ `max_divergence` (in bits). $0$ when $p = q$;
asymmetric (it weights by the **observed** distribution $p$).

```yaml
- type: kl_divergence
  expected: { "00": 0.5, "11": 0.5 }
  max_divergence: 0.05
```

Against the *ideal* `expected`, KL **diverges to infinity** when an observed outcome has zero
expected probability (leakage). It is therefore **automatically readout-aware**: on a real QPU
the backend attaches the device's published readout (assignment) calibration and KL transforms
`expected` through it so the divergence stays finite (it passed at 0.0064 bits on
`ibm_marrakesh`); on a simulator no calibration is attached, so the plain ideal is used. No
per-assertion configuration: the message is tagged `[readout-aware: ...]` when the transform
applied. The transform models measurement error only, so a large KL on hardware still signals
real distance, and the distance oracles remain the simplest gates. A diverged value is reported
and serialised as JSON `null`. See [ADR-0015](adr/0015-chi-square-simulator-only.md).

---

## `shannon_entropy`: Distribution Entropy

$$ H(p) = -\sum_{x} p(x)\,\log_2 p(x) \ \in [0, \log_2|\mathcal{D}|] $$

Bounds the entropy of the measured distribution, in bits: $0$ for a deterministic
outcome, $1.0$ for a balanced Bell pair, $2.0$ for a uniform 2-bit distribution.

```yaml
- type: shannon_entropy
  min: 0.9
  max: 1.1
```

Passes when the entropy lies within the provided `min`/`max` window (at least one is
required). Useful to assert a circuit produces the intended amount of randomness or
concentration without naming exact outcomes.

---

## `expectation_value`: Pauli-Z Product Expectation

$$ \langle Z_{q_0} Z_{q_1} \cdots \rangle = \sum_{x} p(x)\,(-1)^{\sum_i x_{q_i}} \ \in [-1, 1] $$

Reads a Pauli-Z product expectation off the computational-basis counts as a parity
expectation. Bit order is little-endian (qubit $q$ is character $n-1-q$ of a width-$n$
key). A perfect Bell pair gives $\langle Z_0 Z_1 \rangle = +1$; an anti-correlated
state gives $-1$.

```yaml
# window form
- type: expectation_value
  qubits: [0, 1]
  min: 0.95
# target form
- type: expectation_value
  qubits: [0, 1]
  equals: 1.0
  tolerance: 0.05
```

Passes when all provided constraints hold (`min` $\le \langle Z\cdots\rangle \le$ `max`,
and/or $|\langle Z\cdots\rangle - \text{equals}| \le$ `tolerance`; at least one is
required). Z-basis only; arbitrary-Pauli and entanglement-witness observables need
basis-change circuits and are future work (see ADR-0008).

---

## `most_frequent_outcome`: Modal Outcome

Asserts the **modal** measured bitstring (highest count) is a given state, optionally
above a probability.

```yaml
- type: most_frequent_outcome
  state: "11"
  min_probability: 0.7
```

Passes when the modal outcome equals `state` (and its probability $\ge$
`min_probability` if given). Ties are broken by the lexicographically smallest
bitstring for determinism. Ideal for algorithms with a single intended answer (e.g.
Grover's marked state).

---

## `differential`: Cross-Run Agreement (no `expected` needed)

Every oracle above compares against a declared, static `expected` distribution. `differential`
does not: it bounds the total variation distance between **this job's** measured counts $p$ and
**another job's** already-measured counts $r$ (named by `against_job`), so it needs no closed-form
answer at all:

$$ \mathrm{TVD}(p, r) = \tfrac{1}{2} \sum_{x} |p(x) - r(x)| \le \texttt{max\_distance} $$

```yaml
jobs:
  - name: baseline
    circuit: { format: qasm2, path: circuit.qasm }
    backend: { provider: local-aer, options: { method: statevector } }
    assertions:
      - type: allowed_states
        states: ["00", "11"]
        max_leakage: 0.0

  - name: cross-check
    circuit: { format: qasm2, path: circuit.qasm }
    backend: { provider: local-aer, options: { method: matrix_product_state } }
    assertions:
      - type: differential
        against_job: baseline    # must be declared EARLIER in this jobs: list
        max_distance: 0.03
```

Use it for a circuit whose correct output is not known in closed form (the point of running it
*is* computing that answer), or to gate that two backends, two optimization levels, or two
simulation methods agree, catching an implementation regression that a fixed-expected oracle
would not (both sides move together against a static target, so neither alone need cross a
threshold). Measured on the shipped example (`examples/bell-state-differential`, one Bell
circuit through Aer's `statevector` and `matrix_product_state` methods): TVD 0.0006; a circuit
with an injected `cx`->`cz` bug diverges from the correct one at TVD 0.502.

`against_job` **must name a job declared earlier** in the workflow's `jobs:` list (the runner
only has that job's counts once it has actually run). A name that does not resolve, self-references,
or names a later job fails closed with a message identifying the missing reference, rather than a
schema error, since a job's assertions cannot see their siblings at parse time. See
[ADR-0016](adr/0016-differential-oracle.md).

**Metamorphic testing needs no new assertion type.** A related "no expected needed" pattern,
algebraic invariants (e.g. $U \cdot U^{-1} = I$), is already fully expressible with existing
oracles: compose a circuit $U$ with its own exact inverse in one job, and bound the all-zeros
outcome with `allowed_states`/`state_probability`, needing no oracle for what $U$ itself
computes. See `examples/metamorphic-inverse` (a 3-qubit circuit through H/CX/RZ followed by
its inverse, measured at $P(000) = 1.0000$, 95% CI $[0.9995, 1.0000]$ at 8192 shots).

---

## `circuit_depth`: Circuit Depth (structural)

A static, output-independent check on the **authored** circuit's depth.

```yaml
- type: circuit_depth
  max: 50
```

Passes when the depth is within the provided `min`/`max` window (at least one is
required). This needs **no execution**: a job whose assertions are all structural runs
with no shots, no QPU time, and no backend. It bounds the circuit as written, not the
device-transpiled circuit.

---

## `gate_set`: Allowed Gate Set (structural)

Require the authored circuit to use only an allowed set of gate names. Measurement,
barrier, and similar structural operations are always permitted, so list only the
logical gates.

```yaml
- type: gate_set
  allowed: ["h", "cx", "rz", "sx"]
```

Passes when every logical gate used is in `allowed`. Useful to catch an unexpected gate
or to enforce a target device's basis before execution. Also static (no execution).

---

## Choosing oracles

| Goal | Use |
| --- | --- |
| General "does the distribution match?" | `distribution_tvd` (default) + `chi_square` (simulator) |
| Track closeness as one number over time | `hellinger_fidelity` |
| Information-theoretic distance to expected | `kl_divergence` (simulator; auto readout-aware on a QPU) |
| Algorithm produces a specific answer | `state_probability` or `most_frequent_outcome` |
| Track a correlation/parity observable | `expectation_value` ($\langle Z\cdots\rangle$) |
| Assert the right amount of randomness | `shannon_entropy` |
| Forbid impossible outcomes / bound error | `allowed_states` |
| No closed-form expected; compare two runs/backends instead | `differential` |
| Bound circuit complexity, no execution | `circuit_depth` (structural) |
| Enforce a gate set / device basis, no execution | `gate_set` (structural) |

Combine a **distance** oracle, a **hypothesis test**, and a **structural** oracle so
that no single failure mode goes unmeasured, as the
[Bell example](../examples/bell-state/workflow.yaml) does.

## Setting thresholds (statistical reality)

Sampling noise scales like $1/\sqrt{N}$. Per-bitstring standard error is roughly
$\sqrt{p(1-p)/N}$; at $N=8192$ and $p=0.5$ that's $\approx 0.0055$. Set distance
thresholds a few standard errors above expected noise, and prefer fixed `seed`s on
simulators to make pre-merge gates deterministic. Reserve looser thresholds for real
hardware, where device error, not sampling, dominates.

Rather than apply that formula by hand, `shotgate shots` computes a shot count directly
(ADR-0017):

```bash
# "How many shots for a 95% CI of +/-0.01 around a measured probability?"
shotgate shots --margin 0.01
# 9604 shots -> a 95% Wilson interval of +/-0.01 around p=0.5

# "How many shots to reliably (90% power) catch a 0.05 shift at alpha=0.01?"
shotgate shots --effect-size 0.05 --alpha 0.01 --power 0.9
# 5952 shots -> 90% power to detect a shift of 0.05 at alpha=0.01
```

Pass `--p` with `--margin` if the expected proportion is known and not near 0.5 (the default),
since a proportion nearer 0 or 1 needs fewer shots for the same absolute margin.
