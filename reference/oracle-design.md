# The Oracle: Design Guide (skill-internal reference)

**The oracle is an instrument, not a grader.**

## Four design principles

### 1. Returns observations, not judgments

```python
# ❌ Grader-like (bad)
def handle_query(mode, params):
    if mode == "check_topology":
        return {"correct": params["topology"] == HIDDEN_TOPOLOGY}

# ✅ Instrument-like (good)
def handle_query(mode, params):
    if mode == "s_parameters":
        return {"freq_GHz": ..., "s21_dB": ...}
```

### 2. Has multiple modes

Multi-mode oracles force the model to *choose* which observation is
informative. One-mode = no decision.

### 3. Has a help mode that doesn't help

Lists modes + parameter signatures. Does NOT recommend a mode. Does NOT
explain what each measures in physics terms (that's a method-name leak).

### 4. Has noise that defeats trivial inference

Gaussian + 1/f + shot + systematic offsets — match noise to domain. Pure
clean signal makes inverse problems trivial.

## Budget design

Set a budget so a careful solver can investigate but brute-force can't. Typical:
20–50 queries. The oracle should track and refuse calls beyond budget.

## Anti-patterns (skill will lint for these)

- `check_*`, `validate_*`, `is_correct` modes → grader pattern
- Returning the hidden parameter directly (even derived)
- One mode that returns everything
- Mode names that describe the physics ("check_q_factor")
- "hint" fields in returns
- No budget
- Identical noise across mode calls (use seeded RNG that varies)

## Skill lint output

`/everglades-lint <draft>` checks oracle.py for:

- `check_*` / `validate_*` patterns (grader, not instrument)
- Hidden-parameter leak — a `return` that hands back a `HIDDEN_PARAMS` value
- Missing `help` mode
- No budget enforcement
- Missing noise injection

And problem.md for:

- Method-name leaks (DMRG, AlphaFold2, ΔSCF, ...)
- Canonical-target tokens (formaldehyde, 2D Ising critical, ...)
- Strategy hints ("start by measuring ...")
- Missing `submit_answer` instruction
