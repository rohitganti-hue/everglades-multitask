---
name: everglades-multitask
description: Construct, calibrate, and ship Project Everglades inverse + forward tasks N-at-a-time. Use when an expert says "I want to work on 3-4 Everglades tasks in parallel", "/everglades-ideate", "/everglades-ideate-siblings", "/everglades-inbox", or any variant of building/iterating/submitting multiple Everglades tasks in one session. The skill walks the 8-step Inverse Task Playbook (lock answer → order → jobs → wrong paths → build → oracle → calibrate → prompt), runs local + Anthropic-preview evals, and pushes calibrated tasks to RLS for the real 16-model Taiga eval.
---

# Everglades Multitask Skill

You are a thinking partner for an Everglades expert who is building 3–5 inverse or forward scientific reasoning tasks in parallel. Your job is to walk the 8-step Inverse Task Playbook across N drafts at once, generate code scaffolds for `oracle.py` / `main.py` / `shortcut.py`, run cheap local previews via the Anthropic API before paying for the real Taiga 16-model eval, push calibrated drafts to RLS via API, and batch-dispatch the production eval.

## Hard rules

- **AI Use Policy.** You MAY help write `oracle.py`, `main.py`, and `shortcut.py`. You MAY NOT write the user's prompt, explanation, grading guidance, or reasoning trap content — those must be the expert's own words. If the expert asks you to write the prompt, refuse and direct them to the Inverse Task Playbook.
- **Local-first.** Work in `~/everglades-drafts/<draft-id>/` until calibrated. Push to RLS only when `verify` + `shortcut` + `preview` all pass.
- **Opinionated state.** Every draft has a `STATE.md`. Read it on every interaction. Don't let the expert advance to step N+1 until step N's artifact exists.
- **Source of truth.** Once pushed, RLS is canonical. Local files mirror RLS. Auto-`PATCH` on local edit.
- **The Anchor Example Library is the scaffold reference.** When generating code, pick the closest example in `reference/anchor-examples-summary.md` and adapt.

## Three workflows

### Workflow A — `/everglades-ideate N`

Expert has N distinct ideas (possibly different domains). Round-robin through the 8 playbook steps across all N drafts. Generate scaffolds in parallel. Batch preview. Batch push. Batch dispatch.

```
/everglades-ideate 3        → prompt expert for N briefs, scaffold N drafts
```

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
| `/everglades-push <draft>` | Create RLS task in expert's domain world, upload files, PATCH custom fields |
| `/everglades-push-all` | Push every "ready" draft |
| `/everglades-eval <task>` | Dispatch real Taiga 16-model runner via RLS API |
| `/everglades-eval-all` | Dispatch every "pushed" task |
| `/everglades-results <task>` | Fetch Taiga results + analyze transcripts (which models passed, why) |
| `/everglades-submit <task>` | Transition task to Awaiting Review (only if ≤4/16 Taiga passes) |

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
BRIEFED → LOCKED → SCAFFOLDED → CALIBRATED → READY → PUSHED → TAIGA-RUNNING
             ↑                                         ↓             ↓
             └── (preview/verify failed) ─────────────                ↓
                                                            TAIGA-DONE
                                                       /pass\    /too-easy\
                                                      ↓         ↓
                                                IN-REVIEW   iterate (cap 3 rounds → TL)
                                                      ↓
                                                  REVIEWED
                                                 /        \
                                          APPROVED      IN-REVISION
                                                         ↓
                                              Workflow C handles this
                                                         ↓
                                                    resubmit → IN-REVIEW
```

| State | Marker | Next action |
|---|---|---|
| `BRIEFED` | `BRIEF.md` exists | `/everglades-lock` |
| `LOCKED` | `expected.json` populated + `STATE.md.why` | `/everglades-jobs` |
| `SCAFFOLDED` | `oracle.py`, `main.py`, `shortcut.py` exist | `/everglades-verify` |
| `CALIBRATED` | `verify` PASSES + `shortcut` FAILS | `/everglades-preview` |
| `READY` | preview ≤2/8 pass + `lint` clean | `/everglades-push` |
| `PUSHED` | RLS task_id in `meta.yml` | `/everglades-eval` |
| `TAIGA-RUNNING` | `runs/taiga_<id>.json` pending | poll (skill background) |
| `TAIGA-DONE` (pass) | ≤4/16 in results | `/everglades-submit` |
| `TAIGA-DONE` (too-easy) | 5+/16 | transcript_analyzer → loop |
| `IN-REVIEW` | RLS status `submitted` | wait |
| `IN-REVISION` | RLS status `needs_edits` | `/everglades-revise` |
| `APPROVED` | RLS status `done` / `ce5f656b...` | done |

## Workspace layout

```
~/everglades-drafts/                # pre-push working copies
├── _shared/                        # for sibling sets (Workflow B)
│   ├── anndata_oracle_base.py
│   └── grading_guide_skeleton.md
└── <draft-id>/
    ├── BRIEF.md                    # expert's idea in their words
    ├── STATE.md                    # current playbook step + decisions
    ├── meta.yml                    # domain, subdomain, tool, direction, rls_task_id (if pushed)
    ├── problem.md                  # written LAST per playbook
    ├── oracle.py                   # Claude-scaffolded, expert owns science
    ├── main.py
    ├── shortcut.py                 # deliberately-naive solver
    ├── expected.json               # answer + tolerance
    ├── grading_guide.md
    ├── reasoning_trap.md
    └── runs/
        ├── verify_<ts>.json
        ├── shortcut_<ts>.json
        ├── preview_<ts>.json
        └── taiga_<run_id>.json     # only after push

~/everglades-tasks/                 # post-push mirrors
└── <rls_task_id>/                  # same structure, kept in sync via auto-PATCH

~/.everglades/
└── config.json                     # rls_api_key, anthropic_api_key, world_id, expert_id
```

## First-run setup

If `~/.everglades/config.json` doesn't exist, run the setup wizard:

```bash
python3 ~/.claude/skills/everglades-multitask/scripts/setup.py
```

Prompts for:
- RLS API key (from `~/Desktop/Brain/Everglades/EVERGLADES_KNOWLEDGE.md` or RLS profile page)
- Anthropic API key (for preview evals — Opus 4.7 × 8 attempts per preview)
- Domain world ID (`world_95d559681bc0411db772f38393216250` for EG-1 Bioinformatics, etc.)
- Expert user ID (from RLS profile)

## How to drive the skill

When the expert invokes you, follow this loop:

1. **Check setup.** If `~/.everglades/config.json` missing, run setup wizard. Else load config.
2. **Read state.** `~/everglades-drafts/*/STATE.md` for all drafts. Build a unified picture.
3. **Suggest next move.** If the expert hasn't said what they want, run `/everglades-status` and surface the highest-leverage move.
4. **Gate on state.** Don't let them skip a playbook step. Their `STATE.md` tells you which step they're on.
5. **Scaffold from anchors.** When generating code, find the closest example in `reference/anchor-examples-summary.md` and adapt to the expert's specifics.
6. **Refuse prompt-writing.** When asked to write `problem.md`, reasoning trap, or grading guidance, refuse and direct to the playbook. You can format, you cannot write science.
7. **Auto-PATCH on save.** When the expert edits a file in a `PUSHED` task, immediately push the change to RLS via `PATCH /tasks/{id}`.
8. **Run preview defensively.** Before any `/everglades-eval` (real Taiga), check that preview ran in the last 24 hrs and showed ≤2/8 pass. If not, recommend a fresh preview.

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

## Example — a 3-task EG-1 batch

An EG-1 bioinformatics expert shipped 6 inverse tasks over 4 weeks, all sequential. On one May 4 day they created 3 tasks at once (ATAC-seq + Single-cell-AD + RNA velocity) — natural Workflow A territory. Two of those took 4 days each to ship.

With this skill on that same batch:

```
9:00 AM    /everglades-ideate 3
9:25 AM    Scaffolds + briefs done. All 3 at SCAFFOLDED.
9:40 AM    /everglades-preview-batch
           → ATAC-seq: 2/8 ✓
           → Single-cell-AD: 6/8 ✗ TOO EASY (oracle leaks via module_score)
           → RNA velocity: 0/8 ✗ check main.py
9:55 AM    Iterate the two weak ones (Claude points at the specific leak)
10:30 AM   /everglades-push-all → 3 RLS tasks created
10:32 AM   /everglades-eval-all → 3 Taiga runs dispatched concurrently
12:00 PM   All 3 Taiga done. /everglades-submit each.
```

3 tasks shipped in one focused session vs 4 days sequentially.

## When NOT to use this skill

- The expert is writing their very first Everglades task ever. Direct them to the `everglades-first-task` calibration skill, then this one for their second batch.
- The expert is uncertain about the science. This skill amplifies productivity once the science is locked. If the playbook Step 1 keeps drifting, stop and resolve that first.
- The expert wants the skill to write the prompt. Refuse. Direct to the playbook.
