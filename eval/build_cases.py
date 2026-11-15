"""Generate the retrieval evaluation cases from the openings dataset.

Deterministic: the same seed and dataset always give the same files.
Run once, review, commit, and then treat the case files as frozen.

    python eval/build_cases.py

Outputs
    eval/cases/retrieval.jsonl   50 cases: 40 answerable + 10 with no answer
    eval/cases/dev.jsonl         15 answerable cases for tuning only

The gold answer of a case is an opening *name*. A result counts as correct
when its name equals the gold name (several rows can share one name because
the same opening is reached by different move orders).
"""

import csv
import json
import random
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "familyagent" / "data" / "openings.csv"
CASES_DIR = ROOT / "eval" / "cases"
SEED = 20261114

# (type, count in the frozen set, count in the dev set)
PLAN = [
    ("name_exact", 5, 2),          # the opening name alone
    ("name_in_question", 7, 3),    # the exact name inside a sentence
    ("name_typo", 6, 2),           # one misspelled word
    ("name_informal", 6, 2),       # reordered, shortened or plain-ASCII name
    ("moves_san_in_question", 5, 2),  # '1. e4 c5 2. Nf3' inside a sentence
    ("moves_uci_in_question", 3, 1),  # 'e2e4 c7c5' inside a sentence
    ("moves_san_bare", 4, 1),      # 'e4 c5 Nf3' alone, no move numbers
    ("moves_beyond_book", 4, 2),   # a known line plus further moves
]

NAME_TEMPLATES = [
    "What are the moves of the {x}?",
    "Can you show me the {x}?",
    "How does the {x} start?",
    "What is the ECO code for the {x}?",
    "Tell me about the {x}.",
]
MOVE_TEMPLATES = [
    "Which opening is {x}?",
    "What is this opening called: {x}",
    "I played {x} - what opening is that?",
    "Name the opening after {x}.",
]

NO_ANSWER_QUESTIONS = [
    "What are the moves of the Flying Hippo Countergambit?",
    "Show me the Zanzibar Wall Defense.",
    "How does the Quantum Knight System start?",
    "Tell me about the Reykjavik Lemon Gambit.",
    "What is the ECO code for the Triple Rook Shuffle Opening?",
    "Can you show me the Moonlight Bishop Attack?",
    "What are the moves of the Kowalczyk-Tanaka Accelerated Hedgehog Trap?",
    "How does the Glass Pawn Defense start?",
    "Tell me about the Upside-Down Queen Gambit.",
    "Show me the Marmalade Variation of the Sandwich Opening.",
]


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def make_typo(name: str, rng: random.Random) -> str | None:
    """Misspell one word of six or more letters: swap, drop or double a letter."""
    words = name.split(" ")
    candidates = [i for i, w in enumerate(words) if len(w) >= 6 and w.isalpha()]
    if not candidates:
        return None
    i = rng.choice(candidates)
    w = words[i]
    pos = rng.randrange(1, len(w) - 2)
    kind = rng.choice(["swap", "drop", "double"])
    if kind == "swap" and w[pos] != w[pos + 1]:
        w = w[:pos] + w[pos + 1] + w[pos] + w[pos + 2:]
    elif kind == "drop":
        w = w[:pos] + w[pos + 1:]
    else:
        w = w[:pos] + w[pos] + w[pos:]
    words[i] = w
    return " ".join(words)


def make_informal(name: str, rng: random.Random) -> str | None:
    """How people actually type names: reordered, shortened, or plain ASCII."""
    options = []
    if ": " in name:
        family, rest = name.split(": ", 1)
        first = rest.split(", ")[0]
        if rest == first:  # exactly one variation level
            options.append(f"{first} of the {family}")
            short_family = family.replace(" Defense", "").replace(" Opening", "").replace(" Game", "")
            short_first = first.replace(" Variation", "").replace(" Defense", "")
            if short_family != family or short_first != first:
                options.append(f"{short_family} {short_first}")
    plain = strip_accents(name).replace("'", "").replace("-", " ").replace(":", "").replace(",", "").lower()
    if plain != name.lower():
        options.append(plain)
    if "Defense" in name:
        options.append(name.replace("Defense", "Defence"))
    return rng.choice(options) if options else None


def san_tokens(pgn: str) -> list[str]:
    return [t for t in pgn.split() if not t.endswith(".")]


def to_pgn(tokens: list[str]) -> str:
    parts = []
    for i, tok in enumerate(tokens):
        if i % 2 == 0:
            parts.append(f"{i // 2 + 1}.")
        parts.append(tok)
    return " ".join(parts)


def main() -> int:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    rng = random.Random(SEED)
    by_uci = {r["uci"]: r for r in rows}

    def order_free_key(tokens: list[str]) -> tuple:
        """Same moves in a different order give the same key (a transposition)."""
        return (tuple(sorted(tokens[0::2])), tuple(sorted(tokens[1::2])))

    book_keys = {order_free_key(san_tokens(r["pgn"])) for r in rows}
    rows_by_name = defaultdict(list)
    for r in rows:
        rows_by_name[r["name"]].append(r)

    pool = rows[:]
    rng.shuffle(pool)
    used_names: set[str] = set()

    def take(predicate):
        """Next unused row (by opening name) that satisfies the predicate."""
        for r in pool:
            if r["name"] in used_names:
                continue
            made = predicate(r)
            if made:
                used_names.add(r["name"])
                return r, made
        raise RuntimeError("ran out of candidate rows")

    def build(case_type: str, n: int) -> list[dict]:
        out = []
        for k in range(n):
            if case_type == "name_exact":
                r, q = take(lambda r: r["name"])
            elif case_type == "name_in_question":
                r, q = take(lambda r: NAME_TEMPLATES[k % len(NAME_TEMPLATES)].format(x=r["name"]))
            elif case_type == "name_typo":
                r, typo = take(lambda r: make_typo(r["name"], rng))
                q = typo if k % 2 == 0 else NAME_TEMPLATES[k % len(NAME_TEMPLATES)].format(x=typo)
            elif case_type == "name_informal":
                r, informal = take(lambda r: make_informal(r["name"], rng))
                q = informal if k % 2 == 0 else NAME_TEMPLATES[k % len(NAME_TEMPLATES)].format(x=informal)
            elif case_type == "moves_san_in_question":
                r, q = take(lambda r: 4 <= len(r["uci"].split()) <= 14
                            and MOVE_TEMPLATES[k % len(MOVE_TEMPLATES)].format(x=r["pgn"]))
            elif case_type == "moves_uci_in_question":
                r, q = take(lambda r: 4 <= len(r["uci"].split()) <= 12
                            and MOVE_TEMPLATES[k % len(MOVE_TEMPLATES)].format(x=r["uci"]))
            elif case_type == "moves_san_bare":
                r, q = take(lambda r: 4 <= len(r["uci"].split()) <= 12
                            and " ".join(san_tokens(r["pgn"])))
            elif case_type == "moves_beyond_book":
                # Play a longer book line for a few moves past a known opening:
                # the answer is the deepest known opening on the way.
                def beyond(long_row):
                    uci = long_row["uci"].split()
                    san = san_tokens(long_row["pgn"])
                    for cut in range(len(uci) - 1, 3, -1):
                        for depth in range(cut, 2, -1):
                            # Between the known opening and the last played move,
                            # no position may be a book line, not even by a
                            # different move order; otherwise the gold is arguable.
                            if order_free_key(san[:depth]) not in book_keys:
                                continue
                            base = by_uci.get(" ".join(uci[:depth]))
                            if (base is None or depth == cut or cut - depth > 3
                                    or base["name"] in used_names):
                                break
                            return base, to_pgn(san[:cut])
                    return None

                made = None
                for long_row in pool:
                    made = beyond(long_row)
                    if made:
                        break
                if not made:
                    raise RuntimeError("no beyond-book candidate")
                r, played = made
                used_names.add(r["name"])
                q = MOVE_TEMPLATES[k % len(MOVE_TEMPLATES)].format(x=played)
            else:
                raise ValueError(case_type)
            out.append({
                "type": case_type,
                "question": q,
                "answerable": True,
                "gold_name": r["name"],
                "gold_ids": sorted(int(x["id"]) for x in rows_by_name[r["name"]]),
            })
        return out

    frozen, dev = [], []
    for case_type, n_frozen, n_dev in PLAN:
        frozen += build(case_type, n_frozen)
        dev += build(case_type, n_dev)

    for q in NO_ANSWER_QUESTIONS:
        frozen.append({"type": "no_answer", "question": q, "answerable": False,
                       "gold_name": None, "gold_ids": []})

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    for filename, prefix, cases in [("retrieval.jsonl", "R", frozen), ("dev.jsonl", "D", dev)]:
        with (CASES_DIR / filename).open("w", encoding="utf-8", newline="\n") as f:
            for i, case in enumerate(cases, 1):
                record = {"case_id": f"{prefix}{i:03d}", "category": "retrieval", **case}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{filename}: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
