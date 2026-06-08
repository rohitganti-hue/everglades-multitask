# Example — A Same-Domain 3-task EG-1 Bioinformatics Sprint

A real-world walkthrough drawn from an EG-1 bioinformatics expert's actual May 4–8 shipping batch. Anonymized; the task IDs reference approved tasks visible in the Failure Modes Bank.

> **Note on domain.** All 3 tasks in this example are EG-1 — same domain. This is the typical pattern: experts ship within their assigned domain, and the skill is configured to one `world_id` per session. The shared scaffolding wins (one `_shared/anndata_oracle_base.py` extending across all 3 drafts) only work because the drafts share a tool family. Cross-domain batching loses these wins and is not the default mode.

> **Note on structure.** Each draft below follows the canonical Everglades CLI structure: `problem.md`, `config.yaml`, `oracle/setup.py`, `solution/main.py` (+ `solution/shortcut.py`), `grader/grading_guide.md`, `golden/expected.json`, `requirements.txt`, `reasoning_trap.md`. The skill scaffolds + ships in this exact layout so drafts are bidirectionally compatible with the `stemcomp run` / `stemcomp grade` CLI sandbox.

## What the data shows (sequential, before tooling)

The expert created three EG-1 inverse tasks the same day — already trying to work in parallel:

| Task | Subdomain | Tool | Created | Approved | Round-trip |
|---|---|---|---|---|---|
| `u9541c9e` | ATAC-seq | PySAM | May 4 | May 5 | **1 day** |
| `47zn5f8f` | Single cell (AD biomarkers) | ScanPy | May 4 | May 8 | **4 days** |
| `l4qs273b` | Single-cell RNA velocity | scanpy + scVelo | May 4 | May 8 | **4 days** |

Without tooling, two of three tasks took 4 days to ship. That delay was almost entirely:

1. Serial Taiga 16-model runs (40 min each, no parallel dispatch)
2. Reviewer feedback round-trips with context-switching cost
3. Local iteration without preview signal — every iteration burned a Taiga run
4. AutoQC + leak-checking happening reactively after submission

## The April duplicate that the skill would have caught

Two earlier tasks in this expert's history (April 17–18):

| Task | Subdomain | Tool | Trap text |
|---|---|---|---|
| `xm0vffa1` | "Single cell" | scanpy | *"A common wrong path is to build one permissive integrated score…"* |
| `w49sa943` | "SingleCell" | scanpy | *"A common wrong path is to build one permissive integrated score…"* |

**Identical reasoning trap, near-identical subdomain.** These look like the same task pushed twice — both shipped, which means a wasted slot. The skill's `degeneracy.py` would have flagged this at scaffold time:

```
⚠ Sibling overlap detected:
  draft-2 (SingleCell, scanpy)  reasoning_trap entropy 87% match to draft-1
  Suggestion: differentiate the discriminating signal. draft-1 uses RNA-ATAC
              join; what does draft-2 do differently? Or are these the same task?
```

## The same May 4 batch with the skill

```
9:00 AM   > /everglades-ideate 3

Expert:
  1) EG-1, ATAC-seq, ALS iPSC subtype-specific signal vs covariates
  2) EG-1, single-cell biomarker, AD PBMC PANEL_B vs PANEL_A trap
  3) EG-1, RNA velocity inverse, colorectal cancer reversion candidate

Skill: all 3 are scanpy/AnnData. Scaffolds shared module
       _shared/anndata_oracle_base.py. Each draft extends it.

       Round-robin Playbook Steps 1-4 across all 3.
       (Asking Step 1 for all 3, then Step 2 for all 3, etc.)

9:25 AM   All 3 drafts at SCAFFOLDED.

9:40 AM   > /everglades-preview-batch
          Opus 4.7 × 8 × 3 = 24 parallel attempts. ~3 min wall-clock.

          draft-1 ATAC-seq:        2/8 ✓ IN RANGE
          draft-2 Single-cell-AD:  6/8 ✗ TOO EASY
                  → 6 of 6 passing attempts converged on PANEL_B in <3 queries
                  → Root cause: module_score mode returns the
                    answer-bearing statistic directly
                  → Strategy: split into 2 modes that each return raw
                    counts, force the model to aggregate
          draft-3 RNA velocity:    0/8 ✗ CHECK main.py
                  → 6 of 8 attempts errored on `scvelo.tl.velocity` call
                  → Likely missing argument

9:42 AM   > /everglades-focus draft-3
          Skill: main.py calls scvelo.tl.velocity() without the kinetics
                 argument required for an unspliced/spliced AnnData.
                 Auto-fix. Re-preview.
          Result: 2/8 ✓ IN RANGE

9:47 AM   > /everglades-focus draft-2
          Skill: shows the 6 passing transcripts. All 6 query module_score
                 first at t=0, back out PANEL_B directly.
                 Suggests: replace module_score with two modes —
                 panel_baseline_expression + perturbation_response —
                 model must combine to get the disease signature.
          Expert: edits oracle/setup.py with skill's guidance.
          Re-preview: 2/8 ✓ IN RANGE

10:00 AM  All 3 in range. > /everglades-export draft-1 (+ draft-2, draft-3)
          3 MANIFEST.md files written — each maps every draft file to its
          RLS form field. (The skill makes ZERO RLS/Taiga calls; everything
          after this is manual in the RLS web UI.)

10:02 AM  Expert opens https://studio.mercor.com/, creates 3 EG-1 tasks,
          and copy-pastes each draft's files per its MANIFEST, then clicks
          magic-star → STEM Software Runner on each. Taiga starts
          3 × 16-model runs in parallel. A few minutes of pasting + clicking.

10:35 AM  Results land in the RLS UI — the expert watches Taiga there
          (the skill can't see them):
            task-1  3/16 ✓ → Submit for Review (in the RLS UI)
            task-2  still running (~10 min ETA)
            task-3  still running (~15 min ETA)

          Link the shipped tasks back so the dashboard funnel updates:
            > /everglades-rls draft-1 --task-id <id> --status submitted

10:42 AM  task-2  4/16 ✓ → Submit for Review
            > /everglades-rls draft-2 --task-id <id> --status submitted

10:48 AM  task-3  5/16 ✗ — preview-vs-Taiga drift; harden draft-3 locally,
          re-export, and re-paste into the RLS form
```

3 tasks shipped (with 1 needing one more round) in **~1h 45m of active time** — vs **4 days** sequentially.

## Time math

| Phase | Sequential (actual) | Parallel (skill) |
|---|---|---|
| Scaffolding 3 tasks | ~45 min × 3 = 2h 15m | ~30 min total (shared base) |
| Local iteration | unknown — likely 1-2 hrs per task | ~30 min total (batch preview) |
| Taiga eval cycles | 3 × 40 min serial + 1-2 fix cycles per task = ~6-8 hrs | 1 parallel dispatch = 50 min |
| Reviewer revision | 2-3 days waiting + multiple round trips | 1 batched revision session |
| **Total active time** | **~10-15 hours over 4 days** | **~3 hours, single day** |

## The N = 6 portfolio case

This expert's 6 approved EG-1 tasks naturally re-organize into 3 sibling sets:

- **Workflow B batch 1**: ATAC-seq subtype + Single-cell-AD biomarker (siblings: both "ranked-by-largest-signal" trap family)
- **Workflow B batch 2**: RNA velocity + Spatial single-cell (siblings: both "naive trajectory inference" trap family)
- **Workflow B batch 3**: Multiomics QTL + the RNA-ATAC integration (siblings: both "permissive integrated score" trap family)

Three sibling sets, each shipped in a single focused day = **3 days total instead of 4 weeks**.

## Where the skill's wins come from

| Win | Mechanism |
|---|---|
| Shared scaffolding | All 3 May-4 tasks use scanpy/AnnData. Skill generates a shared `_shared/anndata_oracle_base.py` once, extends per-draft. |
| Preview catches "too easy" pre-Taiga | Opus 4.7 × 8 attempts via API. ~90s vs ~40 min of Taiga. |
| Parallel Taiga dispatch | Paste + magic-star all 3 tasks back-to-back in the RLS UI → 3 × 16-model runs execute in parallel (~50 min) instead of ~2+ hrs serial. (Manual clicks, but quick.) |
| Cross-task degeneracy check | Would have caught the April duplicate pair (xm0vffa1 + w49sa943) before either was shipped. |
| Transcript-driven hardening | Skill analyzes preview transcripts and points at the specific oracle mode that's leaking. Turns "5+/16 try again" into "split mode X". |
| Cross-task reviewer feedback patterns | When 2 of 3 tasks come back with the same class of feedback, the skill flags it as one calibration gap, not 3 fixes. |

## N-task scaling

| N tasks | Sequential wall-time | Parallel wall-time (skill) | Speedup |
|---|---|---|---|
| 1 | ~4 hrs | ~2.5 hrs | 1.6× |
| 3 | ~12 hrs | ~3 hrs | 4× |
| 5 | ~20 hrs | ~4 hrs | 5× |
| 7+ | ~28+ hrs | ~5 hrs | 5-6× (preview-batch tops out) |

**Sweet spot is 3-5 tasks per session.** At N=7+, Anthropic API rate limits and context window saturation start to bite. The skill defaults to recommending 3-4 drafts per session unless the expert explicitly forces more.
