# Technical Challenge 7 — Memory, and evals that test it

> **Read first:** [`use_case/CHARTER.md`](../../use_case/CHARTER.md).

Add memory to your application, plus evals that test the memory **directly**.
Testing the whole app and hoping the memory works doesn't count.

<table>
  <tr><td width="110"><strong>Outcome</strong></td>
  <td>Memory that demonstrably works, and three tests that would catch it when it stops.</td></tr>
  <tr><td><strong>Due</strong></td>
  <td>End of Week 7.</td></tr>
</table>

---

## Part 1 — Pick one kind, and say why

You do not need all three. Most applications need one, and choosing is part of
the work:

- **Semantic**, if your users have stable facts your app keeps asking for.
- **Procedural**, if your app solves the same kind of problem again and again
  and works it out from scratch each time.
- **Episodic**, if anyone will ever ask "why did it do that?" In a regulated
  firm, they will.

Write down your choice, and the kinds you rejected, in `use_case/decisions.md`.
**If your app does not need memory, that is a valid answer.** Say so, with the
reason, and build the smallest version anyway so you have measured the thing
you are declining.

## Part 2 — Build it

SQLite is the recommended default. It is transactional, does full-text search,
is one file, and has no server. Reach for a vector store only if you can say
what search by meaning buys you that full-text search (FTS) does not.

**Handle the staleness problem explicitly.** Facts change. Supersede-on-write
keeps one live entry per subject, and it is the default we recommend.
Session 13 shows what happens without it.

## Part 3 — Three tests, in the Week 4 harness

"The app seems to remember" is not a test. These tests target the memory:

1. **Staleness.** Store a fact, change it, and assert the current value comes
   back and the old one does not.
2. **Cost saving.** Run a task twice, measure steps or tokens, and assert
   attempt two is cheaper. This is the metric a business understands.
3. **Truthfulness.** Have the agent do something, ask it to explain, and assert
   the explanation matches **your** log of what happened. The model's account
   of itself is not the log.

**If your app has any notion of users, add the leakage test.** Two users ask
the same question. Assert neither sees the other's facts.

---

## Submission

- [ ] One kind of memory, implemented, with the choice and rejects in `decisions.md`.
- [ ] Staleness handled explicitly. Say which of recency / supersede / validity
      windows you used.
- [ ] Three memory tests in `use_case/evals/`, running with everything else.
- [ ] The leakage test, if you have users.
- [ ] A before/after on your Week 4 numbers. **Memory can make things worse.**
      A wrong fact retrieved confidently is worse than no fact, and you should
      find out whether that happened in your app.

**Strongly recommended**

- [ ] Measure recall quality at 10, 100, and 1,000 entries. The curve tells you
      when FTS stops being enough.
- [ ] One spec file, from Session 14, for a real piece of your work.

---

## If you get stuck

**"My app has no memory need."** Good, say so with a reason. Then build
semantic memory for one user preference anyway. It takes ten minutes, and it
means your "we don't need it" is measured.

**"The memory makes answers worse."** That is a real and common result. A
retrieved wrong fact pushes out correct reasoning. Work out whether it is
retrieval (the wrong entry) or staleness (the right entry, out of date). The
fixes are completely different.

**"I can't measure the procedural saving."** Count anything: tool calls, model
calls, turns, seconds. An imperfect proxy you actually measure beats a perfect
metric you don't.

**"My episodic explanations are plausible but I can't verify them."** Then you
have found the important failure. Write episodic entries from **observed
events**. Log the tool call that happened, not the model's description of it.

---

## My submission

**The short version.** My app now remembers what reviewers decided about a paper. The customer asked
for this in the Week 6 meeting. It is **semantic memory**: one live verdict per paper in SQLite. The
memory never enters the prompt, so it can change a warning but cannot change what the model writes.

| Deliverable | Answer | Where |
| --- | --- | --- |
| One kind of memory, with the rejects | Semantic. Episodic, procedural and a vector store rejected | [`memory.py`](../../01_Product_Engineering/challenge/memory.py), [`decisions.md`](../../use_case/decisions.md) Week 7 |
| Staleness | **Supersede-on-write**, enforced by a partial unique index, plus an approval tied to a hash of the text it judged | `record_verdict`, `apply` |
| Three memory tests, with everything else | Staleness, cost saving, truthfulness, in `run.py`; each also runs against a memory broken on purpose | [`memory_scenarios.py`](../../use_case/evals/memory_scenarios.py), [`memory.jsonl`](../../use_case/evals/memory.jsonl) |
| Leakage | Scoped: the app has no user identity, so verdicts are team-wide by design and the test asserts one person's question never reaches another | same file |
| Before/after on Week 4 | `correct` 0.72 → 0.72, below | [`memory_results.json`](memory_results.json) |
| Recall at 10, 100, 1,000 (recommended) | below | [`measure_memory.py`](measure_memory.py) |
| One spec file (recommended) | Nine rules and one command that exits 0 or fails | [`spec_review_memory.md`](spec_review_memory.md) |
| Still runs in Docker | Image `fde-app:tc7`: a question asked twice became one review item, and a verdict cleared it, inside the container | [`Dockerfile`](../../01_Product_Engineering/challenge/Dockerfile) |

### The tests

| Test | What it asserts | The broken memory it must catch | Real | Caught broken |
| --- | --- | --- | --- | --- |
| Staleness | A changed verdict replaces the old one; one live entry; history kept; an approval expires when the text changes | Reads the first verdict ever given | pass | yes |
| Cost saving | Two asks make one review item; after the verdict, two more asks make none | Stores verdicts, never reads them | pass | yes |
| Truthfulness | The explanation names exactly the checks and papers in our log; an invented reason is rejected | Explains with a plausible story | pass | yes |
| Leakage | The verdict is shared; the other person's question is not | Shows what colleagues asked | pass | yes |

The cost test measures **reviewer work**, not tokens: the model call costs the same either way.

### Before and after

| | `correct` | Note |
| --- | --- | --- |
| Week 4 baseline | 0.72, 95% CI [0.50, 0.89] | not overwritten |
| Week 6 run | 0.67, 95% CI [0.44, 0.89] | one question lower |
| **Week 7 run** | **0.72, 95% CI [0.50, 0.89]** | failed q03, q04, q11, u01, u04 |
| **Replay** of the saved Week 4 answers, a third resting on a rejected paper | **0.72 → 0.72** | 0 of 18 changed, 8 now carry a warning |

`run.py` reported a **REGRESSION** on the Week 7 run: `decline_correct` and `reviewed_facts` each lost
one question. That run used an empty memory that does not enter the prompt, and the replay, which
isolates the memory, changed nothing. To see whether the drop was real I ran the same system five more
times ([`regression_check.json`](regression_check.json)):

| Score | Week 4 baseline | Five runs, mean | Range |
| --- | --- | --- | --- |
| `correct` | 0.72 | 0.74 | 0.67 to 0.78 |
| `decline_correct` | 1.00 | 0.99 | 0.94 to 1.00 |
| `reviewed_facts` | 0.83 | 0.81 | 0.72 to 0.89 |

The gate said PASS three times and REGRESSION twice on the same code, so with 18 questions and a 0.02
tolerance it fires on ordinary model variation. No question got consistently worse, but two weak spots
are real: **q08** was wrongly declined in one run of five although the right paper was retrieved, and
**q03** (Italian) missed a reviewed fact in three of five. The Week 4 baseline is a single run, so this
shows no sign of a regression rather than proving there is none. **Memory can still make things worse
here:** a reviewer who wrongly approves a poisoned paper silences its warning until the text changes.

### Recall

Hit = the exact note in the top 5, 50 queries (10 at the smallest size), synthetic English notes.

| Entries | Same words | Italian query | Search | Lookup by paper id |
| --- | --- | --- | --- | --- |
| 10 | 1.00 | 1.00 | 1.3 ms | 0.8 ms |
| 100 | 1.00 | 0.82 | 1.4 ms | 1.1 ms |
| 1,000 | 1.00 | **0.14** | 3.5 ms | 1.3 ms |

Speed is not the limit, language is. The main lookup, by paper id, is unaffected. Cross-language search
over notes is the specific reason I would add embeddings.

### Can the model explain itself?

Asked why an answer was flagged, five runs each on local `qwen3.5:9b`, scored against our log: **0 of 5
without the log** (it invented a "Citation Validity Check"), **1 of 5 with the log** (the substance was
usually right, the exact check names were not), **5 of 5 for the explanation built from the log in
code**. I tightened the prompt to ask for exact names after a first run scored 0 of 5 with the log. So
explanations come from the log, written by code from observed events.

### Limits

Verdicts can be written by anyone with shell access, and the reviewer's name is not authenticated. The
store holds researchers' questions, with retention still to be agreed with the DPO. Reviewing is a
command line. And the feedback improves warnings and saves review time; it does not improve the answers
yet. Excluding a poisoned paper from retrieval is the next step, and needs its own before/after.

### How to reproduce

```bash
# watch it work: no model, a throwaway database
uv run --project 01_Product_Engineering/challenge python 07_Memory/challenge/demo_memory.py
# the memory tests alone
uv run --project 01_Product_Engineering/challenge python use_case/evals/run.py --no-endpoint --no-injection
# everything: Week 4, memory, injection (local models in .env)
python use_case/evals/run.py
# before/after, recall curve, explanation experiment
python 07_Memory/challenge/measure_memory.py
```
