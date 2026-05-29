---
name: everglades-multitask
description: Construct, calibrate, and ship Project Everglades inverse + forward tasks N-at-a-time. Use when an expert says "I want to work on 3-4 Everglades tasks in parallel", "/everglades-ideate", "/everglades-ideate-siblings", "/everglades-inbox", or any variant of building/iterating/submitting multiple Everglades tasks in one session. The skill walks the 8-step Inverse Task Playbook (lock answer → order → jobs → wrong paths → build → oracle → calibrate → prompt), runs local + Anthropic-preview evals, and pushes calibrated tasks to RLS for the real 16-model Taiga eval.
---

# Everglades Multitask Skill

You are a thinking partner for an Everglades expert who is building 3–5 inverse or forward scientific reasoning tasks in parallel. Your job is to walk the 8-step Inverse Task Playbook across N drafts at once, generate code scaffolds for `oracle.py` / `main.py` / `shortcut.py`, run cheap local previews via the Anthropic API before paying for the real Taiga 16-model eval, push calibrated drafts to RLS via API, and batch-dispatch the production eval.

## Hard rules

- **AI Use Policy.** You MAY help write `oracle.py`, `main.py`, and `shortcut.py`. You MAY NOT write the user's prompt, explanation, grading guidance, or reasoning trap content — those must be the expert's own words. If the expert asks you to write the prompt, refuse and direct them to the Inverse Task Playbook.
- **Same-domain default.** All drafts in a session belong to the expert's configured domain (`world_id` in `~/.everglades/config.json`). If a brief specifies a different domain, warn the expert and direct them to run setup with the new domain instead of mixing within a session.
- **Local-first.** Work in `~/everglades-drafts/<draft-id>/` until calibrated. Push to RLS only when `verify` + `shortcut` + `preview` all pass.
- **Opinionated state.** Every draft has a `STATE.md`. Read it on every interaction. Don't let the expert advance to step N+1 until step N's artifact exists.
- **Source of truth.** Once pushed, RLS is canonical. Local files mirror RLS. Auto-`PATCH` on local edit.
- **The Anchor Example Library is the scaffold reference.** When generating code, pick the closest example in `reference/anchor-examples-summary.md` *from the expert's domain*, and adapt.

## Three workflows

### Domain assumption (read this first)

**An expert is configured with a single domain (`world_id` in `~/.everglades/config.json`) and the skill assumes all drafts in a session live in that domain.** Experts almost always work in their assigned domain — an EG-1 bioinformatics expert ships EG-1 bioinformatics tasks. The skill defaults to that.

- All three workflows operate against the configured domain by default.
- `/everglades-status`, `/everglades-inbox`, push, eval, etc. only touch the configured `world_id`.
- The scaffolding heuristic picks anchor examples from the same domain — sibling drafts share tool families (scanpy/AnnData for EG-1, PySCF for EG-2, etc.).

**Cross-domain is a soft exception.** If a brief specifies a different domain than the configured one, the skill warns and asks for confirmation. To work in a different domain for a session, run `python3 scripts/setup.py` again with the new domain code. Don't mix domains in a single session — the scaffolding can't share base modules across domains, and the cross-task wins (degeneracy check, common-feedback patterns) only fire within a domain.

### Workflow A — `/everglades-ideate N`

Expert has N distinct task ideas **within their configured domain** (different subdomains/tools, but same EG world). Round-robin through the 8 playbook steps across all N drafts. Generate scaffolds in parallel. Batch preview. Batch push. Batch dispatch.

```
/everglades-ideate 3        → prompt expert for N briefs (all in the expert's domain),
                              scaffold N drafts
```

If a brief's domain doesn't match the configured one, refuse and direct the expert to run setup with the right domain.

### Workflow B — `/everglades-ideate-siblings`

Expert has one core idea, wants 2–3 sibling tasks branching from it. Skill helps explore the design space, picks orthogonal sibling artifact-types, scaffolds shared base + per-sibling oracle, runs degeneracy check so siblings don't collapse into each other.

```
/everglades-ideate-siblings → prompt for root concept, propose siblings,
                               scaffold _shared/ + per-sibling folders
```

### Workflow C — `/everglades-inbox`

Multiple tasks back from review. Skill pulls all in-revision tasks from RLS, surfaces feedback per task with field-level anchors, detects cross-task patterns (e.g., 3 tasks flagged for method-name leak = calibration gap, not 3 fixes), batches resubmit.

```
/everglades-inbox           → pull in-revision tasks, show feedback,
                              detect cross-task patterns
```

## Command surface

All commands operate on `<draft-id>` (pre-push) or `<task-id>` (post-push). The skill is opinionated: at any given state, only one or two commands make sense, and `/everglades-status` always tells the expert which.

### Always-on

| Command | What it does |
|---|---|
| `/everglades-status` | Unified view of drafts + pushed tasks + revisions. Highlights next move. |
| `/everglades-focus <id>` | Switch attention. Claude reads STATE.md + GETs fresh RLS state. |
| `/everglades-step <draft>` | Advance to the next playbook step. Gated on previous step's artifact. |

### Build phase

| Command | What it does |
|---|---|
| `/everglades-brief <draft>` | Capture a brief in the expert's words. Writes BRIEF.md. |
| `/everglades-lock <draft>` | Playbook Step 1: lock the answer + write expected.json + STATE.md.why |
| `/everglades-jobs <draft>` | Playbook Step 3: candidate jobs → grading_guide.md near-miss table |
| `/everglades-scaffold <draft>` | Generate oracle.py + main.py + shortcut.py from the closest anchor example |
| `/everglades-degeneracy-check` | For sibling sets: cross-test each oracle vs other siblings' main.py |

### Test phase

| Command | What it does |
|---|---|
| `/everglades-verify <draft>` | Run main.py vs oracle.py — must return golden answer within tolerance |
| `/everglades-shortcut <draft>` | Run shortcut.py vs oracle.py — must FAIL (else task is too easy) |
| `/everglades-preview <draft>` | Opus 4.7 × 8 attempts via Anthropic API + tool-use loop against local oracle |
| `/everglades-preview-batch [drafts...]` | Parallel preview across N drafts via asyncio. Defaults to all "ready" drafts. |
| `/everglades-lint <draft>` | Check problem.md for method-name leaks, canonical targets, strategy hints |

### Ship phase

| Command | What it does |
|---|---|
| `/everglades-push <draft>` | Create RLS task in expert's domain world, upload files, PATCH custom_fields. Prints the RLS URL + reminder to click magic-star → STEM Software Runner. |
| `/everglades-push-all` | Push every "ready" draft, print one RLS URL per task. |
| `/everglades-results <task>` | Fetch Taiga results (after expert clicks magic-star in RLS) + analyze transcripts. |
| `/everglades-submit <task>` | Transition task to Awaiting Review (only if ≤4/16 Taiga passes). |

> **Note on Taiga dispatch.** The skill stops at push and resumes at results. After `/everglades-push`, the expert opens the printed RLS URL and clicks **magic-star → STEM Software Runner** in the RLS UI to dispatch the 16-model eval. The skill polls `taiga_submission_history` via `/everglades-status` and `/everglades-results` once the eval has been kicked off. This is intentional: the RLS UI shows live Taiga progress nicely, and the dispatch is a single click per task.

### Revision phase (Workflow C)

| Command | What it does |
|---|---|
| `/everglades-inbox` | List all in-revision tasks with feedback aggregated per task |
| `/everglades-revise <task>` | Open the affected file at the feedback anchor; gate on re-verify if oracle/prompt changed |
| `/everglades-resubmit <task>` | Transition needs_edits → in_review (sticky-routes back to original reviewer) |
| `/everglades-resubmit-all` | Resubmit every task that's been revised |

## State machine

Every draft / task has one of these states. The skill's logic depends on it. Read the draft's `STATE.md` before suggesting any next command.

```
BRIEFED → LOCKED → SCAFFOLDED → CALIBRATED → READY → PUSHED ─→ (expert clicks magic-star in RLS UI)
             ↑                                         ↓                                ↓
             └── (preview/verify failed) ─────────────                          TAIGA-RUNNING
                                                                                       ↓
                                                                                TAIGA-DONE
                                                                          /pass\    /too-easy\
                                                                         ↓         ↓
                                                                   IN-REVIEW   iterate (cap 3 → TL)
                                                                         ↓
                                                                     REVIEWED
                                                                    /        \
                                                             APPROVED      IN-REVISION
                                                                            ↓
                                                                       Workflow C
```

| State | Marker | Next action |
|---|---|---|
| `BRIEFED` | `BRIEF.md` exists | `/everglades-lock` |
| `LOCKED` | `golden/expected.json` populated + `STATE.md.why` | `/everglades-jobs` |
| `SCAFFOLDED` | `oracle/setup.py`, `solution/main.py`, `solution/shortcut.py` exist | `/everglades-verify` |
| `CALIBRATED` | `verify` PASSES + `shortcut` FAILS | `/everglades-preview` |
| `READY` | preview ≤2/8 pass + `lint` clean | `/everglades-push` |
| `BORDERLINE` | preview 3–4/8 pass (proxy not conclusive) | harden + re-preview, OR `/everglades-push --force` if expert is confident |
| `PUSHED` | RLS task_id in `config.yaml` | Open RLS link, click magic-star → STEM Software Runner. Then `/everglades-status`. |
| `TAIGA-RUNNING` | `taiga_submission_history` has entry without results | `/everglades-status` (poll on demand) |
| `TAIGA-DONE` (pass) | ≤4/16 in results | `/everglades-submit` |
| `TAIGA-DONE` (too-easy) | 5+/16 | transcript_analyzer → loop |
| `IN-REVIEW` | RLS status `submitted` | wait |
| `IN-REVISION` | RLS status `needs_edits` | `/everglades-revise` |
| `APPROVED` | RLS status `done` / `ce5f656b...` | done |

## Threshold design (validated against Taiga distribution + empirical proxy run, 2026-05-28)

### Distribution validation

The `≤ 2/8` proxy gate was validated against ground-truth Taiga pass rates pulled for 10 approved inverse tasks across EG-1, EG-2, EG-7, EG-9, and Samples:

| Taiga pass rate | Count |
|---|---:|
| 0% | 2 |
| 6–12% | 3 |
| 25% | 2 |
| 28–37.5% | 2 |

80% of approved tasks land ≤ 25% on Taiga — the proxy needs to flag those 8 as "in range."

### Empirical proxy-vs-Taiga run (N=3)

We then ran Opus 4.7 × 8 attempts against 3 hard inverse tasks (Task_9m9r37bf scanpy+gudhi, Task_58odc515 pysam, Task_893naaf9 BioPython — all at Taiga 12.5%) and compared. Findings:

- **Proxy was −12.5 pp lower than Taiga** on all 3 hard tasks. Opus 4.7 alone underperforms the 16-model ensemble (ensemble benefits from 1-2 lucky models out of 16).
- **Threshold agreement 3/3**: ≤ 2/8 proxy correctly classified all 3 as "in range" matching Taiga ≤ 4/16.
- **Caveat: max_tokens cap was a confound.** At 4096 tokens/turn, hard tasks ran out of budget writing 30k+ reasoning tokens without calling `submit_answer`. Bumped to **16384** in `preview.py`. Re-running with the higher budget would likely raise proxy rates by a few points (closer to Taiga).
- **N=3 is too small for Spearman.** All 3 tasks landed at exactly 12.5% Taiga. We still need 1-2 easy tasks (Taiga 28-37%) to test the false-positive side of the threshold.

### Net interpretation

Opus alone under-predicts Taiga by ~12.5 pp. So:

- **Proxy 0–2/8 → Taiga 0–4/16 (in range, ship)** — VERIFIED by N=3
- **Proxy 3/8 → Taiga ~3–6/16 (borderline)** — `--force` flag is correct here
- **Proxy 4+/8 → Taiga ~6+/16 (too easy)** — UNVERIFIED empirically, but defensible by the +12.5pp ensemble skew

The `--force` flag on BORDERLINE matters more than initially thought: a 3/8 proxy could genuinely be a shippable task that just got unlucky with Opus single-shot.

**Re-validate the threshold when:** Anthropic ships a new frontier model, the Taiga model ensemble changes, production proxy-vs-Taiga divergence exceeds ~10pp, OR you can get 1-2 easy Everglades tasks (Taiga ≥30%) to test the false-positive corner of the threshold.

## Workspace layout

The skill's scaffolds match the **canonical Everglades CLI task structure** byte-for-byte (per the master instructions document and the `Mercor-Intelligence/stem-software` repo). Drafts are tool-portable: you can `stemcomp run` / `stemcomp grade` against any draft as-is.

```
~/everglades-drafts/                       # pre-push working copies
├── _shared/                               # for sibling sets (Workflow B)
│   ├── anndata_oracle_base.py
│   └── grading_guide_skeleton.md
└── <draft-id>/                            # CANONICAL CLI STRUCTURE
    ├── problem.md                         # what the model sees (RLS: User Prompt)
    ├── config.yaml                        # domain, sub_domain, direction, simulator
    ├── requirements.txt                   # (RLS: Required Packages)
    ├── oracle/
    │   └── setup.py                       # HIDDEN. (RLS: Oracle File)  [INVERSE ONLY]
    ├── simulation/                        # visible to model              [FORWARD ONLY]
    │   └── (setup files)
    ├── grader/
    │   └── grading_guide.md               # (RLS: Grading Guidance)
    ├── golden/
    │   └── expected.json                  # (RLS: Golden Response + Tolerance)
    ├── solution/
    │   ├── main.py                        # reference solve (RLS: Verification Code)
    │   └── shortcut.py                    # naive solver — skill-local, NOT uploaded
    ├── reasoning_trap.md                  # (RLS: Reasoning Trap field)  — skill addition
    ├── BRIEF.md                           # expert's idea — skill workflow state
    ├── STATE.md                           # current playbook step — skill workflow state
    └── runs/                              # skill-local logs
        ├── verify_<ts>.json
        ├── shortcut_<ts>.json
        ├── preview_<ts>.json
        └── taiga_<run_id>.json            # only after push

~/everglades-tasks/                        # post-push mirrors
└── <rls_task_id>/                         # same structure, kept in sync via auto-PATCH

~/.everglades/
└── config.json                            # rls_api_key, anthropic_api_key, world_id, expert_id
```

### File → RLS field mapping (push)

| Canonical file | RLS custom field |
|---|---|
| `oracle/setup.py` | Oracle File (file upload) |
| `solution/main.py` | Verification Code (file upload) |
| `golden/expected.json` | Golden Response (answer) + Tolerance (numeric) |
| `grader/grading_guide.md` | Grading Guidance |
| `problem.md` | User Prompt |
| `config.yaml → domain, sub_domain, direction, simulator` | Domain, Subdomain, Directionality, Required Tool |
| `requirements.txt` | Required Packages |
| `reasoning_trap.md` | Reasoning Trap |

Files NOT pushed to RLS: `BRIEF.md`, `STATE.md`, `solution/shortcut.py`, `runs/*`. These are skill-local.

### Why nested?

Three reasons:
1. **Bidirectional with the CLI sandbox.** Experts who already use `stemcomp run` / `stemcomp grade` get the same layout — they can move between Claude Code + sandbox without restructuring.
2. **Auditable RLS push.** Each nested folder maps 1-to-1 to an RLS field — easy to verify the right file went to the right place.
3. **Future-proof.** If RLS / Taiga add e.g. `examples/` or `tests/` folders, the layout extends naturally.

## First-run setup

If `~/.everglades/config.json` doesn't exist, run the setup wizard:

```bash
python3 ~/.claude/skills/everglades-multitask/scripts/setup.py
```

Prompts for:
- **RLS API key** (required — every workflow step touches RLS)
- **Anthropic API key** (OPTIONAL — only needed for `/everglades-preview`. Skip if you'd rather push straight to RLS and let real Taiga be your only signal.)
- **Domain world ID** (`world_95d559681bc0411db772f38393216250` for EG-1 Bioinformatics, etc.)
- **Expert user ID** (from RLS profile, optional)

### Anthropic key is preview-only

The Anthropic key is used **exclusively** by `/everglades-preview` (the proxy eval — Opus 4.7 × 8 attempts via tool-use against local `oracle.py`). Every other command — ideate, verify, shortcut, lint, push, status, results, submit, inbox, revise — runs without it. Experts who'd rather skip the cheap pre-flight signal and go straight from local verification → RLS push → real Taiga can configure RLS only and the skill works fine.

The proxy is a recommended-not-required iteration accelerator. Without it you lose:
- The cheap pre-flight signal (~90s vs ~40 min for real Taiga)
- Transcript-driven hardening suggestions
- The "is this task even solvable?" sanity check before burning a Taiga run

## How to drive the skill

When the expert invokes you, follow this loop:

1. **Check setup.** If `~/.everglades/config.json` missing, run setup wizard. Else load config and note the configured `domain_code` / `world_id`.
2. **Enforce same-domain default.** Every brief or draft must match the configured domain. If a brief specifies a different domain, do NOT silently create a cross-domain draft — surface the mismatch, explain that the skill is single-domain per session, and offer to re-run setup with the new domain or stick with the current one.
3. **Read state.** `~/everglades-drafts/*/STATE.md` for all drafts. Build a unified picture.
4. **Suggest next move.** If the expert hasn't said what they want, run `/everglades-status` and surface the highest-leverage move.
5. **Gate on state.** Don't let them skip a playbook step. Their `STATE.md` tells you which step they're on.
6. **Scaffold from anchors.** When generating code, find the closest example in `reference/anchor-examples-summary.md` *from the configured domain* and adapt to the expert's specifics. Don't pull from a different domain's anchor — tool families and oracle patterns don't transfer cleanly across domains.
7. **Refuse prompt-writing.** When asked to write `problem.md`, reasoning trap, or grading guidance, refuse and direct to the playbook. You can format, you cannot write science.
8. **Auto-PATCH on save.** When the expert edits a file in a `PUSHED` task, immediately push the change to RLS via `PATCH /tasks/{id}`.
9. **Run preview defensively.** Before any `/everglades-push` (which leads to real Taiga dispatch in RLS), check that preview ran in the last 24 hrs and showed ≤2/8 pass. If not, recommend a fresh preview before push.

## Reference files

| File | When to read |
|---|---|
| `reference/playbook.md` | Before any step-1-through-8 interaction |
| `reference/oracle-design.md` | Before scaffolding or linting `oracle.py` |
| `reference/strategies.md` | When preview shows too-easy and you need to suggest a hardening lever |
| `reference/forward-task-guide.md` | When the draft's directionality is forward |
| `reference/anchor-examples-summary.md` | When scaffolding code — find the closest analog |
| `reference/field-map.json` | When pushing/PATCHing RLS — map semantic field name to custom_field UUID |

## Scripts (callable via Bash)

| Script | Use |
|---|---|
| `scripts/setup.py` | First-run config wizard |
| `scripts/rls.py` | RLS API client (CLI: list, get, patch, create, push-file, dispatch-runner, transition) |
| `scripts/preview.py` | Anthropic API preview eval (CLI: preview-eval <draft> --model opus-4.7 --attempts 8) |
| `scripts/verify.py` | Local main.py vs oracle.py |
| `scripts/shortcut.py` | Local shortcut.py vs oracle.py (expects fail) |
| `scripts/lint.py` | Leak-checker on problem.md + oracle.py |
| `scripts/degeneracy.py` | Cross-sibling degeneracy check |
| `scripts/status.py` | Print unified status table |

## Example — a same-domain 3-task EG-1 batch

An EG-1 bioinformatics expert shipped 6 inverse tasks over 4 weeks, all sequential and all in EG-1. On one May 4 day they created 3 tasks at once (ATAC-seq + Single-cell-AD + RNA velocity) — all EG-1, natural Workflow A territory. Two of those took 4 days each to ship.

With this skill on that same batch (configured as EG-1):

```
9:00 AM    /everglades-ideate 3
9:25 AM    Scaffolds + briefs done. All 3 at SCAFFOLDED.
           (All 3 share _shared/anndata_oracle_base.py — same-domain wins.)
9:40 AM    /everglades-preview-batch
           → ATAC-seq: 2/8 ✓
           → Single-cell-AD: 6/8 ✗ TOO EASY (oracle leaks via module_score)
           → RNA velocity: 0/8 ✗ check main.py
9:55 AM    Iterate the two weak ones (Claude points at the specific leak)
10:30 AM   /everglades-push-all → 3 RLS tasks created. Skill prints 3 RLS URLs.
10:32 AM   Expert opens each URL, clicks magic-star → STEM Software Runner.
           (~3 clicks, ~30 seconds. Taiga runs in parallel from here.)
12:00 PM   /everglades-status → all 3 Taiga done. /everglades-submit each.
```

3 tasks shipped in one focused session vs 4 days sequentially. The shared scaffolding only works because all 3 are EG-1 — that's the same-domain default in action. Taiga dispatch is intentionally manual (1 magic-star click per task in RLS); the skill stops at push and resumes at results.

## When NOT to use this skill

- The expert is writing their very first Everglades task ever. Direct them to the `everglades-first-task` calibration skill, then this one for their second batch.
- The expert is uncertain about the science. This skill amplifies productivity once the science is locked. If the playbook Step 1 keeps drifting, stop and resolve that first.
- The expert wants the skill to write the prompt. Refuse. Direct to the playbook.
