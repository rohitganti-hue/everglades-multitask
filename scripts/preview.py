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


def load_oracle_module(draft_dir: Path):
    """Dynamic-import the draft's oracle/setup.py."""
    oracle_path = paths.oracle_setup(draft_dir)
    if not oracle_path.exists():
        raise FileNotFoundError(f"No oracle/setup.py at {oracle_path}")
    spec = importlib.util.spec_from_file_location(
        f"oracle_setup_{draft_dir.name}", oracle_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {oracle_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "query_oracle"):
        raise AttributeError(f"{oracle_path} has no query_oracle function")
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


def check_answer(submitted, expected: dict) -> bool:
    target = expected.get("answer")
    tol = expected.get("tolerance", 0)
    try:
        s = float(submitted)
        t = float(target)
        if tol == 0:
            return s == t
        return abs(s - t) <= abs(t) * tol if t != 0 else abs(s) <= tol
    except (TypeError, ValueError):
        pass
    if isinstance(submitted, str) and isinstance(target, str):
        return submitted.strip().lower() == target.strip().lower()
    return submitted == target


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
    oracle_mod,
    expected: dict,
    model: str,
    max_steps: int = 30,
    max_tokens_per_turn: int = 16384,
) -> dict:
    """One Opus 4.7 attempt against the local oracle.

    max_tokens_per_turn: bumped from 4096 -> 16384 after empirical validation
    (2026-05-28) showed that hard Everglades inverse tasks (e.g. Task_893naaf9)
    can produce 30k+ tokens of reasoning before submit_answer. The 4096 cap
    caused 8/8 attempts to truncate mid-reasoning and never submit, falsely
    appearing as "0/8 IN_RANGE" when the model was actually still working.
    """
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
    cfg = load_config()
    client = anthropic.AsyncAnthropic(api_key=cfg["anthropic_api_key"])
    oracle_mod = load_oracle_module(draft_dir)
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
                oracle_mod=oracle_mod,
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
    p = argparse.ArgumentParser()
    p.add_argument("drafts", nargs="+", help="Draft directories (one or more)")
    p.add_argument("--attempts", type=int, default=8)
    p.add_argument("--model", default="claude-opus-4-7")
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
