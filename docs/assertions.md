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

## Choosing oracles

| Goal | Use |
| --- | --- |
| General "does the distribution match?" | `distribution_tvd` (default) + `chi_square` (simulator) |
| Track closeness as one number over time | `hellinger_fidelity` |
| Algorithm produces a specific answer | `state_probability` |
| Forbid impossible outcomes / bound error | `allowed_states` |

Combine a **distance** oracle, a **hypothesis test**, and a **structural** oracle so
that no single failure mode goes unmeasured, as the
[Bell example](../examples/bell-state/workflow.yaml) does.

## Setting thresholds (statistical reality)

Sampling noise scales like $1/\sqrt{N}$. Per-bitstring standard error is roughly
$\sqrt{p(1-p)/N}$; at $N=8192$ and $p=0.5$ that's $\approx 0.0055$. Set distance
thresholds a few standard errors above expected noise, and prefer fixed `seed`s on
simulators to make pre-merge gates deterministic. Reserve looser thresholds for real
hardware, where device error, not sampling, dominates.
