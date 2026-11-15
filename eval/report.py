"""Print the headline metrics of one saved end-to-end run.

    python eval/report.py eval/runs/e2e_baseline.json [--show-failed]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.scoring import p95  # noqa: E402


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}% ({n}/{d})" if d else "n/a"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_file")
    parser.add_argument("--show-failed", action="store_true")
    args = parser.parse_args()

    data = json.loads(Path(args.run_file).read_text(encoding="utf-8"))
    runs = data["runs"]
    by_cat = defaultdict(list)
    for r in runs:
        by_cat[r["case"]["category"]].append(r)

    ret = by_cat["retrieval"]
    answerable = [r for r in ret if r["case"]["answerable"]]
    no_answer = [r for r in ret if not r["case"]["answerable"]]
    tools, fails = by_cat["tool"], by_cat["failure"]
    latencies = [r["result"]["latency_ms"] for r in runs if r["result"].get("latency_ms") is not None]

    print(f"run: {data['label']}   cases: {len(runs)}")
    print(f"Recall@3 (through the agent):   {pct(sum(r['verdict']['pass'] for r in answerable), len(answerable))}")
    print(f"  no-answer questions handled:  {pct(sum(r['verdict']['pass'] for r in no_answer), len(no_answer))}")
    print(f"Tool-call accuracy:             {pct(sum(r['verdict']['pass'] for r in tools), len(tools))}")
    print(f"Failure handling:               {pct(sum(r['verdict']['pass'] for r in fails), len(fails))}")
    print(f"p95 latency (all cases):        {p95(latencies) / 1000:.1f} s   (median {sorted(latencies)[len(latencies) // 2] / 1000:.1f} s)")
    for cat, items in by_cat.items():
        lat = [r["result"]["latency_ms"] for r in items if r["result"].get("latency_ms") is not None]
        print(f"  p95 {cat:<10} {p95(lat) / 1000:.1f} s")
    errors = [r for r in runs if r["result"].get("error")]
    print(f"cases with a run error: {len(errors)}")

    if args.show_failed:
        print("\nFAILED:")
        for r in runs:
            if not r["verdict"]["pass"]:
                print(f"- {r['case']['case_id']}: {r['case']['question'][:70]}\n    {r['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
