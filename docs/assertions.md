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
- **Simulator-only as a hardware gate.** Declaring the *ideal* distribution as `expected`
  puts zero probability on a real device's error states, so any leakage forces rejection
  regardless of `significance`: on `ibm_fez` (Bell, 4096 shots) `chi_square` returned
  p-value 0.0000 on counts whose TVD (0.1350) and fidelity (0.8650) passed noise-aware
  gates. Gate hardware with the distance and structural oracles instead; mechanism and
  measurements in the
  [hardware baseline](hardware-validation.md#9-measured-baseline-ibm_fez-2026-06-11)
  and [ADR-0006](adr/0006-hardware-oracle-policy.md).
- **Making it hardware-capable with `readout_error`.** Supply a per-qubit readout
  (assignment) error model and the oracle transforms `expected` through it before
  comparing, giving the test nonzero mass on the device's error states. The same
  `ibm_fez` Bell counts then pass: statistic $1.5\times10^{17}\to 5.51$, p-value
  $0\to 0.138$ at `significance` 0.01. The parameters come from device calibration, not
  the counts under test, so the gate stays an honest hypothesis test (see
  [ADR-0010](adr/0010-noise-aware-expected-distribution.md)).

  ```yaml
  - type: chi_square
    expected: { "00": 0.5, "11": 0.5 }     # the ideal, noiseless distribution
    readout_error: { p0: 0.07, p1: 0.075 } # P(1|0), P(0|1) per qubit, from calibration
    significance: 0.01
  ```

  The same `readout_error` block works on `kl_divergence`.
- **`readout_error: auto` (recommended for portable workflows).** Instead of writing the
  readout numbers by hand, let the oracle read the calibration the run actually used. The
  backend attaches it: the `ibm` backend reads it from the device's published properties
  (averaged over the active qubits), and `local-aer` reports its `noise` block's readout
  parameters. A **noiseless simulator** reports no calibration, so `auto` falls back to the
  ideal `expected`, i.e. the **plain** test. So one workflow gates with the plain
  `chi_square` on a simulator and the device-calibrated one on a QPU, with no per-device
  editing (see [ADR-0013](adr/0013-auto-calibrated-readout.md)).

  ```yaml
  - type: chi_square
    expected: { "00": 0.5, "11": 0.5 }
    readout_error: auto      # ideal on a noiseless sim; device calibration on a QPU
    significance: 0.01
  ```

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

Like `chi_square`, KL **diverges to infinity** when `expected` assigns probability 0
to an outcome that was observed (leakage), so it is **simulator-oriented** unless
`expected` carries nonzero mass on the device's error states. A diverged value is
reported and serialised as JSON `null`.

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
| Information-theoretic distance to expected | `kl_divergence` (simulator, like `chi_square`) |
| Algorithm produces a specific answer | `state_probability` or `most_frequent_outcome` |
| Track a correlation/parity observable | `expectation_value` ($\langle Z\cdots\rangle$) |
| Assert the right amount of randomness | `shannon_entropy` |
| Forbid impossible outcomes / bound error | `allowed_states` |
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
