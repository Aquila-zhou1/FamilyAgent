"""End-to-end evaluation: runs all cases through the deployed agent and saves the raw results.

Prerequisites (see plan/CHESS_ITERATIONS.md, iteration 5):
  - cluster up, LICHESS_MODE=replay and EVAL_FAULTS=true in the ConfigMap, pods Ready
  - nothing else: the runner starts its own `kubectl port-forward` processes on free
    ports (so stale forwards left over from restarts cannot break the run).
    Pass --web / --lichess-admin only to use forwards you manage yourself.

    python eval/run_e2e.py --label baseline
    python eval/report.py eval/runs/e2e_baseline.json

Fault cases run in groups: first the in-process faults (switched through the lichess
server's /_fault endpoint), then the "service down" cases (the Deployment is scaled
to 0 with kubectl and always scaled back to 1 at the end).
"""

import argparse
import json
import socket
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


class Forward:
    """A `kubectl port-forward svc/<name>` on a free local port, owned by this run."""

    def __init__(self, service: str, remote_port: int) -> None:
        self.service, self.remote_port = service, remote_port
        self.proc: subprocess.Popen | None = None
        self.port = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "Forward":
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.proc = subprocess.Popen(
            ["kubectl", "-n", NS, "port-forward", f"svc/{self.service}", f"{self.port}:{self.remote_port}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"kubectl port-forward svc/{self.service} exited; is the pod Ready?")
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
                return self
            except OSError:
                time.sleep(0.5)
        raise RuntimeError(f"port-forward to svc/{self.service} did not come up in 20 s")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def preflight(web: str, admin: str | None) -> None:
    """Fail in seconds, not after 80 cases, if the cluster is not in the state the run needs."""
    r = httpx.get(f"{web}/healthz", timeout=10)
    r.raise_for_status()
    if admin:
        r = httpx.get(f"{admin}/_fault", timeout=10)
        if r.status_code != 200:
            raise RuntimeError("mcp-lichess has no /_fault endpoint: set EVAL_FAULTS=true in the ConfigMap and restart it")


def save(out: Path, label: str, runs: list[dict], complete: bool) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"label": label, "complete": complete, "runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8")


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
    parser.add_argument("--web", default=None, help="use an existing forward instead of starting one")
    parser.add_argument("--lichess-admin", default=None, help="use an existing forward instead of starting one")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--only", choices=["retrieval", "tool", "failure"], help="run one category")
    args = parser.parse_args()

    retrieval, tools, failures = load("retrieval.jsonl"), load("tools.jsonl"), load("failures.jsonl")
    for c in retrieval:
        c["category"] = "retrieval"
    wanted = lambda cat: args.only in (None, cat)  # noqa: E731
    out = ROOT / "eval" / "runs" / f"e2e_{args.label}.json"

    forwards: list[Forward] = []
    runs: list[dict] = []

    def run(case: dict) -> None:
        runs.append(run_case(web, case, args.timeout))
        save(out, args.label, runs, complete=False)  # a crash later keeps everything so far

    try:
        web = args.web
        if web is None:
            forwards.append(Forward("web", 8000).start())
            web = forwards[-1].url
        admin = args.lichess_admin
        if wanted("failure") and admin is None:
            forwards.append(Forward("mcp-lichess", 8002).start())
            admin = forwards[-1].url
        preflight(web, admin if wanted("failure") else None)
        if admin:
            set_fault(admin, "none")  # start from a known state

        if wanted("retrieval"):
            print(f"retrieval ({len(retrieval)})")
            for c in retrieval:
                run(c)
        if wanted("tool"):
            print(f"tool use ({len(tools)})")
            for c in tools:
                run(c)

        if wanted("failure"):
            in_process = [c for c in failures if c["fault"] in ("timeout", "rate_limited", "http_500", "malformed")]
            no_fault = [c for c in failures if c["fault"] == "invalid_id"]
            down = {d: [c for c in failures if c["fault"] == f"{d}_down"] for d in ("openings", "lichess")}
            print(f"failures ({len(failures)})")
            try:
                for mode in ("timeout", "rate_limited", "http_500", "malformed"):
                    set_fault(admin, mode)
                    for c in in_process:
                        if c["fault"] == mode:
                            run(c)
                set_fault(admin, "none")
                for c in no_fault:
                    run(c)
            finally:
                try:
                    set_fault(admin, "none")
                except Exception as exc:  # noqa: BLE001
                    print(f"WARNING: could not reset the fault mode: {exc}")
            for dep, name in (("mcp-openings", "openings"), ("mcp-lichess", "lichess")):
                scale(dep, 0)
                try:
                    for c in down[name]:
                        run(c)
                finally:
                    scale(dep, 1)
    finally:
        for f in forwards:
            f.stop()

    save(out, args.label, runs, complete=True)
    passed = sum(r["verdict"]["pass"] for r in runs)
    print(f"\n{passed}/{len(runs)} cases passed. Saved {out}\nNext: python eval/report.py {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
