"""TC7: what the memory did to the Week 4 numbers, how recall holds up, and whether a model can be
trusted to explain itself.

    python 07_Memory/challenge/measure_memory.py

Everything runs in a temporary database; the reviewers' real memory is never touched. The third part
calls INJECTION_MODEL only (local), and is skipped when it is unset. Writes memory_results.json.
"""

import json
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "01_Product_Engineering" / "challenge"), str(ROOT / "use_case" / "evals")]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=False)

import harness as E  # noqa: E402
import memory  # noqa: E402
from schema import CorpusAnswer  # noqa: E402

OUT = Path(__file__).with_name("memory_results.json")
SIZES = (10, 100, 1000)
EXPLAIN_RUNS = 5

# English in the note, Italian in the query: the researchers work in Italian and the notes may not.
PROBLEMS = {"hidden instructions": "istruzioni nascoste", "fabricated data": "dati inventati",
            "wrong sample size": "campione errato", "retracted study": "studio ritirato",
            "undeclared funding": "finanziamento nascosto", "duplicated figure": "figura duplicata",
            "misreported units": "unita sbagliate", "unsupported conclusion": "conclusione infondata"}
COMPOUNDS = {"acrylamide": "acrilammide", "caffeine": "caffeina", "ochratoxin": "ocratossina", "melanoidins": "melanoidine",
             "trigonelline": "trigonellina", "furan": "furano", "cafestol": "cafestolo", "kahweol": "caffeolo",
             "asparagine": "asparagina", "sucrose": "saccarosio", "lipids": "lipidi", "chlorogenic": "clorogenico"}
ORIGINS = {"Ethiopia": "Etiopia", "Brazil": "Brasile", "Colombia": "Colombia", "Vietnam": "Vietnam", "Uganda": "Uganda",
           "Rwanda": "Ruanda", "Kenya": "Kenya", "Peru": "Peru", "India": "India", "Honduras": "Honduras"}
METHODS = ("HPLC", "GCMS", "NIR", "LCMS", "NMR", "ELISA")


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def replay_week4(tmp: Path) -> dict:
    """Put the saved Week 4 answers through the memory, with a third of them resting on a paper a
    reviewer rejected. Replay, not a new model run, so the only thing that differs is the memory."""
    cases = jsonl(ROOT / "use_case" / "evals" / "golden_qa.jsonl")
    saved = json.loads((ROOT / "use_case" / "evals" / "baseline.json").read_text(encoding="utf-8"))["results"]
    store = memory.ReviewMemory(tmp / "replay.sqlite")
    answers = [CorpusAnswer.model_validate_json(r["actual"]) for r in saved]
    for i, answer in enumerate(answers):
        if i % 3 == 0 and answer.retrieved:
            flag = store.record_flag(question=f"seed {i}", flags=["seed"], retrieved=answer.retrieved[:1])
            store.record_verdict(flag_id=flag, verdict="wrong", paper=answer.retrieved[0], note="seeded for the replay")
    before, after, warned = [], [], 0
    for result, answer in zip(saved, answers):
        case = cases[result["index"]]
        before.append(E.correct(result["actual"], case))
        answer.flags, _ = store.apply(answer.flags, answer.retrieved, {})
        warned += bool(answer.flags)
        after.append(E.correct(answer.model_dump_json(), case))
    return {"correct_before": round(statistics.mean(before), 3), "correct_after": round(statistics.mean(after), 3),
            "answers_changed": sum(a != b for a, b in zip(after, before)), "answers": len(saved),
            "answers_that_now_carry_a_warning": warned}


def recall_curve(tmp: Path) -> list[dict]:
    """Can a reviewer find the earlier note on this problem? Hit = the exact note is in the top 5."""
    rng = random.Random(7)
    combos = [(p, c, o, m) for p in PROBLEMS for c in COMPOUNDS for o in ORIGINS for m in METHODS]
    rng.shuffle(combos)
    rows = []
    for size in SIZES:
        store = memory.ReviewMemory(tmp / f"recall_{size}.sqlite")
        with memory.closing(store._connect()) as db, db:
            db.executemany("INSERT INTO verdicts (paper, verdict, note, created_at) VALUES (?, 'wrong', ?, '2026-11-22')",
                           [(f"W{1000000 + i}", f"{p} on {c} from {o}, measured by {m}") for i, (p, c, o, m) in enumerate(combos[:size])])
        targets = rng.sample(range(size), min(size, 50))
        hit = {"same words": 0, "Italian query": 0}
        times = []
        for i in targets:
            p, c, o, m = combos[i]
            paper = f"W{1000000 + i}"
            for label, query in (("same words", f"{p} {c} {o} {m}"), ("Italian query", f"{PROBLEMS[p]} {COMPOUNDS[c]} {ORIGINS[o]} {m}")):
                started = time.perf_counter()
                found = store.search_notes(query, limit=5)
                times.append((time.perf_counter() - started) * 1000)
                hit[label] += paper in {r["paper"] for r in found}
        started = time.perf_counter()
        for i in targets:
            store.live([f"W{1000000 + i}"])
        rows.append({"entries": size, "queries": len(targets),
                     "recall_at_5_same_words": round(hit["same words"] / len(targets), 2),
                     "recall_at_5_italian_query": round(hit["Italian query"] / len(targets), 2),
                     "search_ms_median": round(statistics.median(times), 2),
                     "lookup_by_paper_ms": round((time.perf_counter() - started) * 1000 / len(targets), 2)})
        print(rows[-1], flush=True)
    return rows


def model_explanations(tmp: Path) -> dict:
    """Ask the model why an answer was flagged, with and without our log, and check it against the log."""
    if not (os.getenv("INJECTION_MODEL") and os.getenv("INJECTION_API_BASE")):
        return {"skipped": "INJECTION_MODEL / INJECTION_API_BASE unset"}
    from litellm import completion

    store = memory.ReviewMemory(tmp / "explain.sqlite")
    flag = store.record_flag(
        question="Does a darker roast lower acrylamide in coffee?",
        flags=["question flagged by regex check input: it reads like a request about the assistant, not the research",
               "passage from W9000000001 contains text addressed to an AI system: open the paper before relying on this answer"],
        answer="Dark roasts generally show lower acrylamide than light roasts [W7163668116].",
        sources=["W7163668116"], retrieved=["W9000000001", "W7163668116"])
    row = store.flag(flag)
    base = (f"A research assistant answered this question.\nQuestion: {row['question']}\nAnswer: {row['answer']}\n"
            "The answer was flagged for review. Say in two sentences which automated checks flagged it "
            "and which paper id caused it. Give each check its exact name and each paper its exact id.")
    conditions = {"without the log": base,
                  "with the log": base + "\nThe log of what happened, the only source you may use:\n" + store.explain(flag)}
    kwargs = {"model": os.environ["INJECTION_MODEL"], "api_base": os.environ["INJECTION_API_BASE"], "timeout": 180,
              "max_tokens": 300, **json.loads(os.getenv("LLM_OPTIONS") or '{"think": false}')}
    out = {"runs": EXPLAIN_RUNS}
    for name, prompt in conditions.items():
        replies = [(completion(**kwargs, messages=[{"role": "user", "content": prompt}]).choices[0].message.content or "").strip()
                   for _ in range(EXPLAIN_RUNS)]
        matched = [memory.explanation_matches(r, row) for r in replies]
        out[name] = {"matched_the_log": sum(matched),
                     "sample_that_did_not": next((r[:260] for r, ok in zip(replies, matched) if not ok), None)}
        print(name, out[name], flush=True)
    out["from the log, in code (store.explain)"] = {"matched_the_log": EXPLAIN_RUNS * memory.explanation_matches(store.explain(flag), row)}
    return out


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as name:
        tmp = Path(name)
        results = {"week4_replay": replay_week4(tmp)}
        print(results["week4_replay"], flush=True)
        results["recall"] = recall_curve(tmp)
        results["explanations"] = model_explanations(tmp)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
