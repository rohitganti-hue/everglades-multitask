# Inverse Task Playbook — 8 steps

Compressed for skill-internal reference. Full version on the Everglades Hub.

**An inverse task is not a normal task with the answer hidden. It is a small
investigation. The solver can see the evidence, but not the rule that makes
one answer right and the others wrong.**

## Step 1 — Lock the answer first

Write the exact answer + the logic that makes it the only answer you would
stand behind. Hidden parts of the task depend on it. If the answer keeps
changing while you build, stop — task is not stable.

**Artifact:** `expected.json` populated + `STATE.md` "why this is the only
answer" section.

## Step 2 — Decide the order of decisions

What must be true first? What comes after? What is later evidence not allowed
to outweigh?

**Artifact:** `STATE.md` "Order of decisions" section.

## Step 3 — Give each candidate a job

For each plausible wrong answer, one sentence on why it loses. At least one
should look good at first glance.

**Artifact:** `grading_guide.md` near-miss table populated.

## Step 4 — Plan the wrong paths

Catalogue the shortcuts a weak solver will take. For each: which wrong answer
does it produce + why.

**Artifact:** `shortcut.py` scaffolded (the most likely naive solver).

## Step 5 — Build the files

`oracle.py` + `main.py` + `shortcut.py`. The skill scaffolds; the expert owns
the science. **Per AI Use Policy, Claude can help with code; expert writes the
science.**

**Artifact:** all 3 Python files runnable.

## Step 6 — Design the oracle and the budget

The oracle returns observations, not judgments. Multiple modes. Help mode that
doesn't recommend. Budget tight enough that brute-force loses. Domain-realistic
noise.

See: `oracle-design.md`.

## Step 7 — Calibrate

Run `main.py` against `oracle.py` → must pass.
Run `shortcut.py` against `oracle.py` → must FAIL.
Vary the oracle's noise seed and re-run `main.py` → must still pass within tolerance
(the answer must not drift with the seed — canonical robustness check).
Run `/everglades-preview` (Opus 4.7 × 8 attempts) → target ≤2/8 pass rate.

The local preview is a **proxy** for the canonical gate — the real Taiga 16-model eval
(STEM Software Runner in RLS), where **≤4/16 must pass**. Preview ≤2/8 predicts ≤4/16.

**Approve only if (a) careful passes, (b) shortcuts fail for the reasons you
intended, (c) preview is in range.**

## Step 8 — Write the prompt last

Give the model what it needs to reason, not how to reason. No method names.
No quantitative anchors. No strategy hints. Lint it before pushing.

**Artifact:** `problem.md`.

---

## Skill gating

The skill won't let you advance past a step until its artifact exists. State
sequence:

```
BRIEFED → LOCKED → JOBS → SCAFFOLDED → CALIBRATED → READY → EXPORTED
```

Each transition has a specific command and a specific check. `EXPORTED` is the terminal
local state — after it, the expert pastes into the RLS UI and dispatches Taiga manually.
