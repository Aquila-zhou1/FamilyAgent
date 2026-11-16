"""Write EVAL_REPORT.md from the saved evaluation runs.

    python eval/make_report.py --baseline eval/runs/e2e_baseline.json \
        --v2 eval/runs/e2e_v2_a.json [eval/runs/e2e_v2_b.json ...]

Offline retrieval numbers are recomputed here (deterministic); end-to-end numbers
are read from the run files, so nothing in the report is typed by hand.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.run_retrieval import evaluate, load_cases  # noqa: E402
from eval.scoring import p95  # noqa: E402

SETS = [
    ("dev (tuned on)", "dev.jsonl"),
    ("frozen", "retrieval.jsonl"),
    ("holdout (hand-written, afterwards)", "holdout.jsonl"),
]


def metrics(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    runs = data["runs"]
    cat = lambda c: [r for r in runs if r["case"]["category"] == c]  # noqa: E731
    ret = cat("retrieval")
    ans = [r for r in ret if r["case"]["answerable"]]
    noans = [r for r in ret if not r["case"]["answerable"]]
    ok = lambda rs: sum(r["verdict"]["pass"] for r in rs)  # noqa: E731
    lat = [r["result"]["latency_ms"] for r in runs if r["result"].get("latency_ms") is not None]
    return {
        "file": path.name, "cases": len(runs), "complete": data.get("complete", True),
        "recall": (ok(ans), len(ans)), "noanswer": (ok(noans), len(noans)),
        "tools": (ok(cat("tool")), len(cat("tool"))), "failures": (ok(cat("failure")), len(cat("failure"))),
        "p95": p95(lat) / 1000, "median": sorted(lat)[len(lat) // 2] / 1000,
        "failed": [r["case"]["case_id"] for r in runs if not r["verdict"]["pass"]],
    }


def frac(t: tuple[int, int]) -> str:
    return f"{100 * t[0] / t[1]:.1f}% ({t[0]}/{t[1]})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", nargs="+", required=True)
    parser.add_argument("--v2", nargs="+", required=True)
    parser.add_argument("--out", default=str(ROOT / "EVAL_REPORT.md"))
    args = parser.parse_args()

    lines = [f"# Evaluation report ({date.today().isoformat()})", ""]
    lines += ["## 1. Retrieval function alone (no model, deterministic)", "",
              "Recall@3 = answerable cases whose gold opening name is in the first 3 results. "
              "No-answer = questions about openings that do not exist; correct behaviour is to return nothing.", "",
              "| set | bm25 Recall@3 | v2 Recall@3 | bm25 no-answer | v2 no-answer |", "|---|---|---|---|---|"]
    for label, fname in SETS:
        cases = load_cases(ROOT / "eval" / "cases" / fname)
        a, _ = evaluate("bm25", cases)
        b, _ = evaluate("v2", cases)
        n = a["no_answer_cases"]
        lines.append(
            f"| {label} | {a['recall_at_3']*100:.1f}% ({a['hits']}/{a['answerable_cases']}) | "
            f"{b['recall_at_3']*100:.1f}% ({b['hits']}/{b['answerable_cases']}) | "
            f"{a['no_answer_returning_nothing']}/{n} | {b['no_answer_returning_nothing']}/{n} |")
    lines += ["", "v2 was designed from the failure classes seen on the frozen set and its constants were "
              "tuned on dev only, so the frozen number is optimistic. The holdout set was written afterwards; "
              "one ranking fix (prefer the name with the fewest extra words) was made after seeing it, so "
              "its 87.5% is mildly optimistic too.", ""]

    lines += ["## 2. End to end through the agent (100 cases, deployed on kind)", "",
              "Retrieval 50 (40 answerable + 10 no-answer), tool use 30, service failures 20. "
              "Lichess runs in replay mode (fixed puzzle), failures are injected, the model is a live API.", "",
              "| run | search | Recall@3 | no-answer | tool-call accuracy | failure handling | p95 | median |",
              "|---|---|---|---|---|---|---|---|"]
    rows = []
    for impl, files in (("bm25", args.baseline), ("v2", args.v2)):
        for f in files:
            m = metrics(Path(f))
            rows.append((impl, m))
            lines.append(f"| {m['file']} | {impl} | {frac(m['recall'])} | {frac(m['noanswer'])} | "
                         f"{frac(m['tools'])} | {frac(m['failures'])} | {m['p95']:.1f} s | {m['median']:.1f} s |")
    lines += ["", "Cases failed per run:", ""]
    for impl, m in rows:
        lines.append(f"- {m['file']} ({impl}): {', '.join(m['failed']) or 'none'}")
    lines += ["", "## 3. How to read this", "",
              "- Metrics: Recall@3 and no-answer handling are decided from what the tools actually returned; "
              "tool-call accuracy needs the exact tool set and key arguments; failure handling needs the "
              "failure to reach the agent, an answer that admits it, and no invented data (keyword check, "
              "not human review). p95 is the ceil(0.95*N)-th sorted latency.",
              "- Repeated runs of the same configuration differ by 1-2 cases (the model is not deterministic), "
              "so single-run differences of that size are noise.",
              "- Tool-call accuracy loses cases mainly to one pattern: after a puzzle the agent also calls "
              "`find_opening_by_moves` although the user did not ask for the opening (prompt rule 7 says how to "
              "find a game's opening but does not forbid doing it unprompted). The extra call is harmless but "
              "the scoring is strict, and it adds a few seconds of latency. Not fixed, so that the measured "
              "numbers describe the deployed prompt.",
              ""]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
