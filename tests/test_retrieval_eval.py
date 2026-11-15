"""Retrieval entry point, case files and evaluator."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from familyagent.openings import db
from familyagent.openings.retrieve import retrieve

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval" / "cases"


def load(name: str) -> list[dict]:
    with (CASES / name).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_retrieval", ROOT / "eval" / "run_retrieval.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def conn():
    return db.build()


def test_retrieve_implementations_differ_on_a_sentence(conn):
    question = "What are the moves of the Scandinavian Defense: Panov Transfer?"
    assert retrieve(conn, question, impl="substring") == []
    names = [r["name"] for r in retrieve(conn, question, impl="bm25")]
    assert "Scandinavian Defense: Panov Transfer" in names


def test_retrieve_rejects_unknown_impl(conn):
    with pytest.raises(ValueError):
        retrieve(conn, "Sicilian Defense", impl="nope")


def test_retrieve_handles_punctuation_only(conn):
    assert retrieve(conn, "?!", impl="bm25") == []


def test_case_files_are_well_formed():
    frozen, dev = load("retrieval.jsonl"), load("dev.jsonl")
    assert len(frozen) == 50 and len(dev) == 15
    assert sum(c["answerable"] for c in frozen) == 40
    assert all(c["answerable"] for c in dev)

    ids = [c["case_id"] for c in frozen + dev]
    assert len(ids) == len(set(ids))
    questions = [c["question"] for c in frozen + dev]
    assert len(questions) == len(set(questions))

    with db.DEFAULT_CSV.open(encoding="utf-8", newline="") as f:
        ids_by_name: dict[str, list[int]] = {}
        for row in csv.DictReader(f):
            ids_by_name.setdefault(row["name"], []).append(int(row["id"]))
    for case in frozen + dev:
        if case["answerable"]:
            assert case["gold_ids"] == sorted(ids_by_name[case["gold_name"]])
        else:
            assert case["gold_name"] is None and case["gold_ids"] == []


def test_dev_and_frozen_sets_share_no_gold_opening():
    frozen = {c["gold_name"] for c in load("retrieval.jsonl") if c["answerable"]}
    dev = {c["gold_name"] for c in load("dev.jsonl")}
    assert frozen.isdisjoint(dev)


@pytest.mark.parametrize("impl, hits", [("substring", 9), ("bm25", 24)])
def test_baseline_recall_is_reproducible(impl, hits):
    runner = load_runner()
    cases = runner.load_cases(CASES / "retrieval.jsonl")
    first, _ = runner.evaluate(impl, cases)
    second, _ = runner.evaluate(impl, cases)
    assert first == second
    assert (first["hits"], first["answerable_cases"]) == (hits, 40)
