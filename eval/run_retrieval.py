"""Retrieval-only evaluation: Recall@3 of an implementation on a case file.

No model call and no network, so the result is exactly repeatable.

    python eval/run_retrieval.py --impl bm25
    python eval/run_retrieval.py --impl substring --cases eval/cases/dev.jsonl

Recall@3 = answerable cases whose gold opening name appears among the first
three results / all answerable cases. Cases with no answer are listed
separately and are not part of the denominator.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from familyagent.openings import db  # noqa: E402
from familyagent.openings.retrieve import IMPLEMENTATIONS, retrieve  # noqa: E402

K = 3


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate(impl: str, cases: list[dict]) -> tuple[dict, list[dict]]:
    conn = db.build()
    results = []
    for case in cases:
        top = retrieve(conn, case["question"], impl=impl, limit=K)
        names = [r["name"] for r in top]
        results.append({
            "case_id": case["case_id"],
            "type": case["type"],
            "question": case["question"],
            "gold_name": case["gold_name"],
            "retrieved": names,
            "hit": bool(case["answerable"]) and case["gold_name"] in names,
        })

    answerable = [r for r, c in zip(results, cases) if c["answerable"]]
    by_type = defaultdict(lambda: [0, 0])
    for r in answerable:
        by_type[r["type"]][0] += r["hit"]
        by_type[r["type"]][1] += 1
    hits = sum(r["hit"] for r in answerable)
    no_answer = [r for r, c in zip(results, cases) if not c["answerable"]]
    summary = {
        "impl": impl,
        "k": K,
        "answerable_cases": len(answerable),
        "hits": hits,
        "recall_at_3": round(hits / len(answerable), 4) if answerable else None,
        "by_type": {t: {"hits": h, "cases": n} for t, (h, n) in by_type.items()},
        "no_answer_cases": len(no_answer),
        "no_answer_returning_nothing": sum(not r["retrieved"] for r in no_answer),
    }
    return summary, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--impl", required=True, choices=sorted(IMPLEMENTATIONS))
    parser.add_argument("--cases", default=str(ROOT / "eval" / "cases" / "retrieval.jsonl"))
    parser.add_argument("--show-misses", action="store_true")
    args = parser.parse_args()

    cases_path = Path(args.cases)
    summary, results = evaluate(args.impl, load_cases(cases_path))

    out_dir = ROOT / "eval" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"retrieval_{cases_path.stem}_{args.impl}.json"
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump({"summary": summary, "cases": results}, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"impl: {args.impl}   cases: {cases_path.name}")
    print(f"Recall@{K}: {summary['hits']}/{summary['answerable_cases']} = {summary['recall_at_3']:.1%}")
    for case_type, s in summary["by_type"].items():
        print(f"  {case_type:<24} {s['hits']}/{s['cases']}")
    print(f"no-answer cases returning nothing: "
          f"{summary['no_answer_returning_nothing']}/{summary['no_answer_cases']}")
    if args.show_misses:
        for r in results:
            if r["gold_name"] and not r["hit"]:
                print(f"MISS {r['case_id']} [{r['type']}] {r['question']!r}\n"
                      f"     gold: {r['gold_name']}\n     got:  {r['retrieved']}")
    print(f"written: {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
