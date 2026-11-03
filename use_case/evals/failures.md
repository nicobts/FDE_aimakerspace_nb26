# What goes wrong: the failure taxonomy

Read from the **108 real traces** of the Week 3 comparison (run 2026-11-03, local `qwen3.5:9b`,
18 labelled questions × 4 agents + 2 endpoint paths; traces in `use_case/data/runs/`, gitignored).
**48 of the 108 were failures** (pass false, or an answerable question without every gold paper
cited). For the shipped endpoint alone (`endpoint-hybrid`, 18 traces): **4 failures**.

A trace was read, given one sentence, and the sentences were grouped. Ranked by count over all
108; the shipped endpoint's count is in brackets.

| # | Failure | Count (shipped) | Example trace | Caught by |
| --- | --- | --- | --- | --- |
| 1 | **A gold paper never reaches the model** - retrieval missed it, so the answer cannot cite or use it (mostly the second paper of a multi-hop question, and the Italian question for BM25) | 18 (1) | `endpoint-hybrid:q04`: W4405184446 (truncated abstract) not in the top 5 | `all_gold_cited` |
| 2 | **No retrieval at all** - an agent answered or declined without a single search; on u04 it said "no evidence in the corpus" when the paper is there | 10 (0) | `agent-hybrid:u04`, every agent on `q03` | `decline_correct` (a false "no" on an answerable question) |
| 3 | **The gold paper reached the model, but the answer misses a reviewed fact** - right paper, incomplete finding | 9 (2) | `endpoint-hybrid:q11` never says "americano"; `endpoint-hybrid:u01` never gives the 300 mg/L | `reviewed_facts`, and the judge |
| 4 | **Wiki tool misuse** - a whole sentence passed to `grep_wiki` as a pattern, "(no matches)", gave up | 7 (0) | `agent-wiki:q08` | not scored: agent-only, the wiki is not shipped |
| 5 | **Multi-hop half answer** - both gold papers reached the model, one was used | 4 (1) | `endpoint-hybrid:q06` used the Uganda study, dropped Rwanda | `all_gold_cited` |
| 6 | **A decline that still quotes a figure** - the right refusal, with a number from an unrelated paper in the reason | 1 (0) | `endpoint-bm25:q10` "< LOD to 207.3 µg/kg" | `clean_decline` |
| 8 | **Misattributed citation** - found in the baseline run, after the 108: figures from the gold paper credited to another retrieved paper, with the conclusion reversed ("può aumentare" where the study found no significant increase) | 1 in the baseline run | `q03` in `baseline.json`: W7214237096 cited for W7127046736's 3.51 µg/kg | `all_gold_cited` only; `grounded_sources` cannot, the wrong paper was shown |
| 7 | **A cited id the model was never shown** - not observed in the 108; the endpoint drops such ids, so this is a regression guard, exercised by the generated failures | 0 (0) | - | `grounded_sources` |

**What the counts say.** The shipped path's failures are retrieval (line 1, 5) and incompleteness
(line 3), not invention: no trace cited a paper it was not shown. Lines 2 and 4 are why the agents
were rejected in Week 3. The real failure rate of the shipped endpoint (4 of 18) is too low to
test a detector on, which is why `synthetic.jsonl` exists.

**Run-to-run variance.** `q03` passed in the Week 3 run and failed in the baseline run, same
endpoint, same question: `qa.py` does not fix the temperature, so one run of 18 is one sample.

**What I noticed about my own criteria.** "Misses a reviewed fact" is strict by design: `q11`'s
answer is right in substance and fails only because the reviewed term "americano" is absent. The
label was not changed after seeing the answer. A judge that reads for substance is the check on
whether that strictness is fair (see the judge's separation in the README).
