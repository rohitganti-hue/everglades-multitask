"""Anthropic-API preview eval — Opus 4.7 × N attempts vs the local oracle/setup.py.

Reads:
  - problem.md             — the prompt the model sees
  - oracle/setup.py        — the hidden system (loaded via importlib)
  - golden/expected.json   — the golden answer + tolerance

Runs N parallel attempts via asyncio. Each attempt:
  - Loads the draft's problem.md as the user message
  - Defines two tools: query_oracle(mode, parameters) and submit_answer(value)
  - Routes query_oracle calls to oracle.setup.query_oracle
  - Records the transcript
  - On submit_answer, compares to golden/expected.json within tolerance

This matches the canonical Everglades CLI structure.

CLI:
  python3 preview.py <draft_dir>
  python3 preview.py <draft_dir> --attempts 8 --model claude-opus-4-7
  python3 preview.py <draft_dir1> <draft_dir2> ...        # batch
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import paths
from config import load as load_config

try:
    import anthropic
except ImportError:
    print(
        "anthropic SDK not installed. Run: pip install anthropic",
        file=sys.stderr,
    )
    sys.exit(2)


def load_oracle_module(draft_dir: Path, *, attempt_idx: int | None = None):
    """Dynamic-import the draft's oracle/setup.py with a UNIQUE module name.

    Each preview attempt gets its own fresh module instance — module-level
    globals (budget counters, seeded RNGs) start independent per attempt.
    Critical correctness fix: previously all 8 concurrent attempts shared one
    oracle module, sharing the `_used` counter and `_RNG` seed. That meant
    8 attempts collectively saw ~30 queries (~3.75 each) instead of 30 each,
    and once the shared budget tripped every attempt got "budget exceeded".

    Pass `attempt_idx` from run_attempt() to get the per-attempt isolation;
    omit it for one-off CLI use where global state doesn't matter.
    """
    oracle_path = paths.oracle_setup(draft_dir)
    if not oracle_path.exists():
        raise FileNotFoundError(f"No oracle/setup.py at {oracle_path}")
    # Unique module name per attempt so importlib gives a distinct namespace
    suffix = f"_a{attempt_idx}" if attempt_idx is not None else ""
    spec = importlib.util.spec_from_file_location(
        f"oracle_setup_{draft_dir.name}{suffix}", oracle_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {oracle_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Try query_oracle first, fall back to handle_query (some Everglades
    # oracles use the latter — empirically observed on Task_58odc515, etc.)
    if not hasattr(mod, "query_oracle"):
        if hasattr(mod, "handle_query"):
            mod.query_oracle = mod.handle_query
        else:
            raise AttributeError(
                f"{oracle_path} has no query_oracle or handle_query function"
            )
    return mod


def load_expected(draft_dir: Path):
    p = paths.expected_json(draft_dir)
    if not p.exists():
        raise FileNotFoundError(f"No golden/expected.json at {p}")
    return json.loads(p.read_text())


def load_problem(draft_dir: Path):
    p = paths.problem_md(draft_dir)
    if not p.exists():
        raise FileNotFoundError(f"No problem.md at {p}")
    return p.read_text()


from grading import check_answer  # single shared grader — see scripts/grading.py


TOOLS = [
    {
        "name": "query_oracle",
        "description": (
            "Query the hidden system. The oracle returns raw observations "
            "(not judgments). Available modes are listed via "
            "query_oracle(mode='help', parameters={})."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string"},
                "parameters": {"type": "object"},
            },
            "required": ["mode"],
        },
    },
    {
        "name": "submit_answer",
        "description": "Submit your final answer for this task.",
        "input_schema": {
            "type": "object",
            "properties": {"value": {}},
            "required": ["value"],
        },
    },
]


async def run_attempt(
    client: anthropic.AsyncAnthropic,
    *,
    attempt_idx: int,
    problem: str,
    draft_dir: Path,
    expected: dict,
    model: str,
    max_steps: int = 30,
    max_tokens_per_turn: int = 16384,
) -> dict:
    """One Opus 4.7 attempt against the local oracle.

    Loads a FRESH oracle module instance per attempt (unique sys.modules slot)
    so module-level state — budget counters, seeded RNGs — start independent.

    max_tokens_per_turn: bumped from 4096 -> 16384 after empirical validation
    (2026-05-28) showed that hard Everglades inverse tasks (e.g. Task_893naaf9)
    can produce 30k+ tokens of reasoning before submit_answer. The 4096 cap
    caused 8/8 attempts to truncate mid-reasoning and never submit, falsely
    appearing as "0/8 IN_RANGE" when the model was actually still working.
    """
    # Fresh per-attempt oracle (P0 fix — see load_oracle_module docstring).
    oracle_mod = load_oracle_module(draft_dir, attempt_idx=attempt_idx)
    messages = [{"role": "user", "content": problem}]
    transcript = []
    queries_used = 0
    submitted = None
    error = None
    for step in range(max_steps):
        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=max_tokens_per_turn,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            error = f"API error step {step}: {e}"
            break
        transcript.append(
            {
                "step": step,
                "stop_reason": resp.stop_reason,
                "content_summary": [
                    {"type": b.type, "preview": (
                        b.text[:200] if b.type == "text" else
                        (b.name if b.type == "tool_use" else str(b)[:80])
                    )}
                    for b in resp.content
                ],
            }
        )

        if resp.stop_reason != "tool_use":
            break

        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "submit_answer":
                submitted = block.input.get("value")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Answer recorded. Task complete.",
                })
            elif block.name == "query_oracle":
                queries_used += 1
                try:
                    result = oracle_mod.query_oracle(
                        block.input.get("mode"),
                        block.input.get("parameters", {}),
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str)[:8000],
                    })
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Oracle error: {e}",
                        "is_error": True,
                    })

        if submitted is not None:
            break

        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": tool_results})

    passed = submitted is not None and check_answer(submitted, expected)
    return {
        "attempt": attempt_idx,
        "passed": passed,
        "submitted": submitted,
        "queries_used": queries_used,
        "transcript_steps": len(transcript),
        "transcript": transcript,
        "error": error,
    }


async def run_preview(draft_dir: Path, *, attempts: int, model: str) -> dict:
    cfg = load_config(require_anthropic=True)
    client = anthropic.AsyncAnthropic(api_key=cfg["anthropic_api_key"])
    # Probe-import once up-front to surface ImportErrors / missing deps early.
    load_oracle_module(draft_dir)
    expected = load_expected(draft_dir)
    problem = load_problem(draft_dir)

    print(f"  preview: {draft_dir.name} × {attempts} ({model})", file=sys.stderr)
    t0 = time.time()
    results = await asyncio.gather(
        *[
            run_attempt(
                client,
                attempt_idx=i,
                problem=problem,
                draft_dir=draft_dir,
                expected=expected,
                model=model,
            )
            for i in range(attempts)
        ]
    )
    elapsed = time.time() - t0
    passes = sum(1 for r in results if r["passed"])
    summary = {
        "draft": draft_dir.name,
        "model": model,
        "attempts": attempts,
        "passes": passes,
        "pass_rate": passes / attempts,
        "elapsed_s": round(elapsed, 1),
        "attempts_detail": results,
        "ran_at": datetime.utcnow().isoformat() + "Z",
    }
    runs = paths.runs_dir(draft_dir)
    runs.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    (runs / f"preview_{ts}.json").write_text(json.dumps(summary, default=str, indent=2))
    return summary


def classify(pass_rate: float) -> str:
    """Classify a proxy pass rate.

    Threshold design validated against Taiga ground-truth distribution
    (10 approved Everglades tasks, 2026-05-28): 80% of approved tasks land
    at <=25% on the 16-model Taiga eval. Proxy (Opus 4.7 x 8) skews slightly
    more permissive than Taiga because Opus is among the strongest models in
    the 16-model ensemble. The strict <=2/8 (25%) IN_RANGE bar gives a margin
    of safety: a task barely clearing the proxy gate will most likely land
    comfortably under Taiga's 4/16 = 25% cutoff.
    """
    if pass_rate >= 0.5:
        return "TOO_EASY"          # 4+/8 -> likely 5+/16 on Taiga, definitely harden
    if pass_rate >= 0.375:
        return "BORDERLINE"        # 3/8 -> ambiguous; expert can override with --force
    if pass_rate > 0:
        return "IN_RANGE"          # 1-2/8 -> proceed to Taiga
    return "CHECK_MAIN_OR_ORACLE"  # 0/8 -> likely main.py / oracle.py is broken


async def main_async():
    # Pull defaults from config.json (~/.everglades/config.json) so users can
    # set preview_model / preview_attempts there and have them take effect.
    # Previously these were hardcoded argparse defaults and changing the config
    # had no effect — config writes were dead.
    try:
        cfg = load_config()
        default_model = cfg.get("preview_model") or "claude-opus-4-7"
        default_attempts = cfg.get("preview_attempts") or 8
    except SystemExit:
        default_model = "claude-opus-4-7"
        default_attempts = 8
    p = argparse.ArgumentParser()
    p.add_argument("drafts", nargs="+", help="Draft directories (one or more)")
    p.add_argument("--attempts", type=int, default=default_attempts)
    p.add_argument("--model", default=default_model)
    args = p.parse_args()

    draft_paths = [Path(d).expanduser().resolve() for d in args.drafts]
    summaries = await asyncio.gather(
        *[run_preview(d, attempts=args.attempts, model=args.model) for d in draft_paths]
    )

    print("\n" + "=" * 78)
    print(f"PREVIEW EVAL · {args.model} × {args.attempts} attempts per draft")
    print("=" * 78)
    for s in summaries:
        cls = classify(s["pass_rate"])
        sym = {"TOO_EASY": "✗", "BORDERLINE": "⚠", "IN_RANGE": "✓", "CHECK_MAIN_OR_ORACLE": "✗"}[cls]
        print(
            f"\n  {sym} {s['draft']:30s}  passes: {s['passes']}/{s['attempts']}"
            f"  ({s['pass_rate']*100:.0f}%)  [{cls}]  {s['elapsed_s']}s"
        )
        non_pass = [a for a in s["attempts_detail"] if not a["passed"]]
        if non_pass:
            from collections import Counter
            submitted_vals = Counter(str(a["submitted"])[:60] for a in non_pass)
            for val, cnt in submitted_vals.most_common(3):
                print(f"      {cnt}× submitted: {val}")
    print()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
