# 5 Strategies to Stump LLMs (skill-internal reference)

When preview shows pass rate ≥3/8 (TOO_EASY), apply these in order:

## Strategy 1 — Hide the method, not the science

Describe operationally; never name methods. Catches: retrieval.

- ❌ "Compute via ΔSCF with MOM constraints"
- ✅ "Use a self-consistent procedure for the excited state that preserves the chosen orbital occupation"

## Strategy 2 — Hide the target

Pick scientifically valid but non-canonical examples. Catches: memorization.

- ❌ Formaldehyde n→π*, 2D Ising at T_c, repressilator at Elowitz parameters
- ✅ Donor-substituted heterocycle, 1D chain with unusual coupling ratio

## Strategy 3 — Narrow-boolean validators (final-answer only)

For final-answer validators (NOT the observation oracle), return
accepted/rejected with no diagnostic. Catches: per-component search.

## Strategy 4 — Force convention commitments

Tolerance tight enough that the default-convention answer fails. Catches:
default-convention drift.

- "Standard deviation using the n−1 denominator"
- "Vertical excitation at GS equilibrium geometry, not relaxed"

## Strategy 5 — Compositional difficulty

Submit all components together; no per-stage feedback. Catches: per-stage
checkpointing.

- Topology + component values in one submission
- All 6 orbital elements as a single tuple

## Skill mapping

The skill suggests fixes based on the preview transcript:

- All passing attempts converged on one mode → Strategy 1 (mode leaks the
  method) or Strategy 3 (oracle is acting as a grader)
- Passing attempts used a canonical literature value → Strategy 2
- Passing attempts used the wrong convention (but the tolerance accepted it)
  → Strategy 4
- Passing attempts solved sub-pieces sequentially with per-piece feedback →
  Strategy 5
