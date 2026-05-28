"""Anthropic-API preview eval — Opus 4.7 × N attempts vs a local oracle.py.

Runs N parallel attempts via asyncio. Each attempt:
  - Loads the draft's problem.md as the user message
  - Defines two tools: query_oracle(mode, parameters) and submit_answer(value)
  - Routes query_oracle calls to the local oracle.py module
  - Records the transcript
  - On submit_answer, compares to expected.json within tolerance

CLI:
  python3 preview.py <draft_dir>
  python3 preview.py <draft_dir> --attempts 8 --model claude-opus-4-7
  python3 preview.py <draft_dir> --batch <draft1> <draft2> <draft3>

This is the cheapest, fastest signal an expert can get on whether their task
will pass the ≤4/16 Taiga bar — typically catches "too easy" and "broken"
in ~3 minutes vs ~40 minutes for a real Taiga 16-model run.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from config import load as load_config

# Anthropic SDK
try:
    import anthropic
except ImportError:
    print(
        "anthropic SDK not installed. Run: pip install anthropic",
        file=sys.stderr,
    )
    sys.exit(2)


def load_oracle_module(draft_dir: Path):
    """Dynamic-import the draft's oracle.py."""
    oracle_path = draft_dir / "oracle.py"
    if not oracle_path.exists():
        raise FileNotFoundError(f"No oracle.py at {oracle_path}")
    spec = importlib.util.spec_from_file_location(
        f"oracle_{draft_dir.name}", oracle_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {oracle_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "query_oracle"):
        raise AttributeError(f"{oracle_path} has no query_oracle function")
    return mod


def load_expected(draft_dir: Path):
    expected_path = draft_dir / "expected.json"
    if not expected_path.exists():
        raise FileNotFoundError(f"No expected.json at {expected_path}")
    with expected_path.open() as f:
        return json.load(f)


def load_problem(draft_dir: Path):
    p = draft_dir / "problem.md"
    if not p.exists():
        raise FileNotFoundError(f"No problem.md at {p}")
    return p.read_text()


def check_answer(submitted, expected: dict) -> bool:
    """Compare submitted answer to expected.json within tolerance."""
    target = expected.get("answer")
    tol = expected.get("tolerance", 0)
    # Numeric tolerance
    try:
        s = float(submitted)
        t = float(target)
        if tol == 0:
            return s == t
        # relative tolerance
        return abs(s - t) <= abs(t) * tol if t != 0 else abs(s) <= tol
    except (TypeError, ValueError):
        pass
    # String exact (case-insensitive)
    if isinstance(submitted, str) and isinstance(target, str):
        return submitted.strip().lower() == target.strip().lower()
    # JSON / structured equality
    return submitted == target


TOOLS = [
    {
        "name": "query_oracle",
        "description": (
            "Query the hidden system. The oracle returns raw observations "
            "(not judgments). Available modes are listed via query_oracle(mode='help', parameters={})."
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
) -> dict:
    """Run one Anthropic agent attempt against the local oracle.

    Returns: {attempt, passed, submitted, transcript, queries_used, error}
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
                max_tokens=4096,
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
            # Done reasoning without submit; no answer
            break

        # Process tool calls
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "submit_answer":
                submitted = block.input.get("value")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Answer recorded. Task complete.",
                    }
                )
            elif block.name == "query_oracle":
                queries_used += 1
                try:
                    result = oracle_mod.query_oracle(
                        block.input.get("mode"),
                        block.input.get("parameters", {}),
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str)[:8000],
                        }
                    )
                except Exception as e:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Oracle error: {e}",
                            "is_error": True,
                        }
                    )

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
    # Save
    runs_dir = draft_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    (runs_dir / f"preview_{ts}.json").write_text(json.dumps(summary, default=str, indent=2))
    return summary


def classify(pass_rate: float) -> str:
    if pass_rate >= 0.5:
        return "TOO_EASY"
    if pass_rate >= 0.25:
        return "BORDERLINE"
    if pass_rate > 0:
        return "IN_RANGE"
    return "CHECK_MAIN_OR_ORACLE"


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
        # Show failure patterns
        non_pass = [a for a in s["attempts_detail"] if not a["passed"]]
        if non_pass:
            from collections import Counter
            submitted_vals = Counter(str(a["submitted"])[:60] for a in non_pass)
            top = submitted_vals.most_common(3)
            for val, cnt in top:
                print(f"      {cnt}× submitted: {val}")
    print()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
