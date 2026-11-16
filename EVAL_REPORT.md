# Evaluation report (2026-11-16)

## 1. Retrieval function alone (no model, deterministic)

Recall@3 = answerable cases whose gold opening name is in the first 3 results. No-answer = questions about openings that do not exist; correct behaviour is to return nothing.

| set | bm25 Recall@3 | v2 Recall@3 | bm25 no-answer | v2 no-answer |
|---|---|---|---|---|
| dev (tuned on) | 60.0% (9/15) | 100.0% (15/15) | 0/5 | 5/5 |
| frozen | 60.0% (24/40) | 100.0% (40/40) | 0/10 | 10/10 |
| holdout (hand-written, afterwards) | 56.2% (9/16) | 87.5% (14/16) | 0/4 | 4/4 |

v2 was designed from the failure classes seen on the frozen set and its constants were tuned on dev only, so the frozen number is optimistic. The holdout set was written afterwards; one ranking fix (prefer the name with the fewest extra words) was made after seeing it, so its 87.5% is mildly optimistic too.

## 2. End to end through the agent (100 cases, deployed on kind)

Retrieval 50 (40 answerable + 10 no-answer), tool use 30, service failures 20. Lichess runs in replay mode (fixed puzzle), failures are injected, the model is a live API.

| run | search | Recall@3 | no-answer | tool-call accuracy | failure handling | p95 | median |
|---|---|---|---|---|---|---|---|
| e2e_baseline.json | bm25 | 92.5% (37/40) | 90.0% (9/10) | 93.3% (28/30) | 100.0% (20/20) | 13.5 s | 5.9 s |
| e2e_v2_a.json | v2 | 90.0% (36/40) | 100.0% (10/10) | 86.7% (26/30) | 100.0% (20/20) | 17.6 s | 6.4 s |
| e2e_v2_b.json | v2 | 92.5% (37/40) | 100.0% (10/10) | 90.0% (27/30) | 100.0% (20/20) | 15.5 s | 5.8 s |

Cases failed per run:

- e2e_baseline.json (bm25): R008, R013, R015, R042, T006, T008
- e2e_v2_a.json (v2): R002, R008, R015, R017, T002, T003, T006, T008
- e2e_v2_b.json (v2): R002, R008, R015, T002, T003, T006

## 3. How to read this

- Metrics: Recall@3 and no-answer handling are decided from what the tools actually returned; tool-call accuracy needs the exact tool set and key arguments; failure handling needs the failure to reach the agent, an answer that admits it, and no invented data (keyword check, not human review). p95 is the ceil(0.95*N)-th sorted latency.
- Repeated runs of the same configuration differ by 1-2 cases (the model is not deterministic), so single-run differences of that size are noise.
- Tool-call accuracy loses cases mainly to one pattern: after a puzzle the agent also calls `find_opening_by_moves` although the user did not ask for the opening (prompt rule 7 says how to find a game's opening but does not forbid doing it unprompted). The extra call is harmless but the scoring is strict, and it adds a few seconds of latency. Not fixed, so that the measured numbers describe the deployed prompt.