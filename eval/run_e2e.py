"""End-to-end evaluation: runs all cases through the deployed agent and saves the raw results.

Prerequisites (see plan/CHESS_ITERATIONS.md, iteration 5):
  - cluster up, LICHESS_MODE=replay and EVAL_FAULTS=true in the ConfigMap, mcp-lichess restarted
  - kubectl -n chess port-forward svc/web 8000:8000 &
  - kubectl -n chess port-forward svc/mcp-lichess 8002:8002 &

    python eval/run_e2e.py --label baseline
    python eval/report.py eval/runs/e2e_baseline.json

Fault cases run in groups: first the in-process faults (switched through the lichess
server's /_fault endpoint), then the "service down" cases (the Deployment is scaled
to 0 with kubectl and always scaled back to 1 at the end).
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.scoring import score  # noqa: E402

CASES = ROOT / "eval" / "cases"
NS = "chess"


def load(name: str) -> list[dict]:
    with (CASES / name).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def kubectl(*args: str) -> None:
    subprocess.run(["kubectl", "-n", NS, *args], check=True, capture_output=True, text=True)


def scale(deployment: str, replicas: int) -> None:
    kubectl("scale", f"deployment/{deployment}", f"--replicas={replicas}")
    if replicas:
        kubectl("rollout", "status", f"deployment/{deployment}", "--timeout=90s")
    else:
        time.sleep(4)  # let the Service drop the endpoint


def set_fault(admin: str, mode: str) -> None:
    r = httpx.post(f"{admin}/_fault", json={"mode": mode}, timeout=10)
    r.raise_for_status()


def ask(web: str, question: str, timeout: float) -> dict:
    try:
        r = httpx.post(f"{web}/agent/chess/ask", json={"question": question, "lang": "en"}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001 - a transport failure is a failed case, not a crash
        return {"answer": "", "tool_calls": [], "unavailable_servers": [],
                "error": f"{type(exc).__name__}: {exc}", "latency_ms": None}


def run_case(web: str, case: dict, timeout: float) -> dict:
    result = ask(web, case["question"], timeout)
    retries = 0
    # A dropped connection to the model API is infrastructure noise, not agent behaviour:
    # retry up to twice and record how many retries were needed.
    while retries < 2 and str(result.get("error") or "").startswith(("APIConnectionError", "APITimeoutError")):
        retries += 1
        time.sleep(2)
        result = ask(web, case["question"], timeout)
    result["retries"] = retries
    verdict = score(case, result)
    mark = "PASS" if verdict["pass"] else "FAIL"
    print(f"  {mark} {case['case_id']} {result.get('latency_ms')} ms  {case['question'][:60]}", flush=True)
    return {"case": case, "result": result, "verdict": verdict}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True, help="name of this run, e.g. baseline or v2")
    parser.add_argument("--web", default="http://localhost:8000")
    parser.add_argument("--lichess-admin", default="http://localhost:8002")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--only", choices=["retrieval", "tool", "failure"], help="run one category")
    args = parser.parse_args()

    retrieval, tools, failures = load("retrieval.jsonl"), load("tools.jsonl"), load("failures.jsonl")
    for c in retrieval:
        c["category"] = "retrieval"
    wanted = lambda cat: args.only in (None, cat)  # noqa: E731

    runs: list[dict] = []
    if wanted("retrieval"):
        print(f"retrieval ({len(retrieval)})")
        runs += [run_case(args.web, c, args.timeout) for c in retrieval]
    if wanted("tool"):
        print(f"tool use ({len(tools)})")
        runs += [run_case(args.web, c, args.timeout) for c in tools]

    if wanted("failure"):
        in_process = [c for c in failures if c["fault"] in ("timeout", "rate_limited", "http_500", "malformed")]
        no_fault = [c for c in failures if c["fault"] == "invalid_id"]
        down = {d: [c for c in failures if c["fault"] == f"{d}_down"] for d in ("openings", "lichess")}
        print(f"failures ({len(failures)})")
        try:
            for mode in ("timeout", "rate_limited", "http_500", "malformed"):
                set_fault(args.lichess_admin, mode)
                runs += [run_case(args.web, c, args.timeout) for c in in_process if c["fault"] == mode]
            set_fault(args.lichess_admin, "none")
            runs += [run_case(args.web, c, args.timeout) for c in no_fault]
        finally:
            try:
                set_fault(args.lichess_admin, "none")
            except Exception as exc:  # noqa: BLE001
                print(f"WARNING: could not reset the fault mode: {exc}")
        for dep, name in (("mcp-openings", "openings"), ("mcp-lichess", "lichess")):
            scale(dep, 0)
            try:
                runs += [run_case(args.web, c, args.timeout) for c in down[name]]
            finally:
                scale(dep, 1)

    out = ROOT / "eval" / "runs" / f"e2e_{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"label": args.label, "runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8")
    passed = sum(r["verdict"]["pass"] for r in runs)
    print(f"\n{passed}/{len(runs)} cases passed. Saved {out}\nNext: python eval/report.py {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
