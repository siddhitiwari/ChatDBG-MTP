#!/usr/bin/env python3
"""
ChatDBG Evaluation Harness

Runs post-mortem analysis on benchmark programs and reports accuracy metrics.

Usage:
    python eval/run_eval.py
    python eval/run_eval.py --variant baseline
    python eval/run_eval.py --variant with_repo
    python eval/run_eval.py --benchmark testme_zero_division
    python eval/run_eval.py --output results.json
"""
import argparse
import json
import os
import sys

# Ensure src/ is importable when run from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from eval.runner import generate_crash_log, run_analysis
from eval.scorer import score_result

BENCHMARK_FILE = os.path.join(os.path.dirname(__file__), "benchmarks.json")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_benchmarks() -> list[dict]:
    with open(BENCHMARK_FILE) as f:
        return json.load(f)


def run_one(benchmark: dict, variant: str) -> dict:
    script = os.path.join(PROJECT_ROOT, benchmark["script"])

    print(f"  generating crash log ...", end=" ", flush=True)
    crash_log = generate_crash_log(script)
    if crash_log is None:
        return {"error": "script did not crash or timed out"}
    print("ok")

    repo_path = PROJECT_ROOT if variant == "with_repo" else None

    print(f"  running analysis ({variant}) ...", end=" ", flush=True)
    result = run_analysis(crash_log, repo_path=repo_path)
    print("ok")

    scores = score_result(benchmark, result)
    return {
        "benchmark_id": benchmark["id"],
        "variant": variant,
        "description": benchmark["description"],
        **scores,
    }


def print_report(results: list[dict]) -> None:
    print(f"\n{'=' * 84}")
    print("  ChatDBG Evaluation Report")
    print(f"{'=' * 84}")
    print(
        f"  {'Benchmark':<28} {'Variant':<11} {'Exc':>4} {'KW%':>5} "
        f"{'Fix':>4} {'Test':>5} {'FixOK':>6} {'Tok':>6} {'Cost':>7} {'Time':>6}"
    )
    print(f"  {'-' * 80}")

    for r in results:
        bid = r.get("benchmark_id", "?")[:28]
        var = r.get("variant", "?")[:11]

        if "error" in r:
            print(f"  {bid:<28} {var:<11}  ERROR: {r['error']}")
            continue

        exc  = "Y" if r.get("exception_match") else ("N" if r.get("exception_match") is False else "-")
        kw   = f"{r['keyword_score']:.0%}" if r.get("keyword_score") is not None else "-"
        fix  = "Y" if r.get("fix_proposed") else "N"
        test = "Y" if r.get("test_generated") else "N"
        fok  = "Y" if r.get("fix_correct") else ("N" if r.get("fix_correct") is False else "-")
        tok  = str(r.get("tokens", 0))
        cost = f"${r.get('cost', 0):.3f}"
        time = f"{r.get('time', 0):.1f}s"

        print(
            f"  {bid:<28} {var:<11} {exc:>4} {kw:>5} "
            f"{fix:>4} {test:>5} {fok:>6} {tok:>6} {cost:>7} {time:>6}"
        )

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="ChatDBG Evaluation Harness")
    parser.add_argument(
        "--variant",
        choices=["baseline", "with_repo", "all"],
        default="all",
        help="Configuration variant to test (default: all)",
    )
    parser.add_argument("--benchmark", help="Run only this benchmark ID")
    parser.add_argument("--output", default="eval_results.json", help="JSON output file")
    args = parser.parse_args()

    benchmarks = load_benchmarks()
    if args.benchmark:
        benchmarks = [b for b in benchmarks if b["id"] == args.benchmark]
        if not benchmarks:
            print(f"No benchmark with id: {args.benchmark}")
            sys.exit(1)

    variants = ["baseline", "with_repo"] if args.variant == "all" else [args.variant]

    all_results = []
    for benchmark in benchmarks:
        for variant in variants:
            print(f"\n[{benchmark['id']}] variant={variant}")
            row = run_one(benchmark, variant)
            all_results.append(row)

    print_report(all_results)

    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"Full results saved to {args.output}")


if __name__ == "__main__":
    main()
