"""Score ask_research_corpus against the QA goldens. The whole interface:

    python use_case/evals/run.py                 # echo, oracle, endpoint; compare to baseline.json
    python use_case/evals/run.py --judge         # also calibrate the judge and add its column
    python use_case/evals/run.py --synthetic     # also score the generated failures (detection table)
    python use_case/evals/run.py --save          # write this run as the new baseline.json

The endpoint needs the corpus (use_case/data, gitignored) and the models named in .env
(LLM_MODEL, EMBED_MODEL, ...). JUDGE_MODEL names the judge; it must not be LLM_MODEL.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "01_Product_Engineering" / "challenge"))
sys.path.insert(0, str(HERE))

from helpers import harness as H  # noqa: E402
from helpers import nb  # noqa: E402
import harness as E  # noqa: E402

GOLDEN = HERE / "golden_qa.jsonl"
SYNTHETIC = HERE / "synthetic.jsonl"
BASELINE = HERE / "baseline.json"
DEFAULT_JUDGE = "ollama_chat/hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M"


def load_cases():
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


def table(rows, columns):
    head = "| system | " + " | ".join(columns) + " |"
    sep = "| --- |" + " --- |" * len(columns)
    body = [f"| {name} | " + " | ".join(f"{means.get(c, float('nan')):.2f}" for c in columns) + " |" for name, means in rows]
    return "\n".join([head, sep, *body])


def make_judge(cfg, cases):
    from helpers.judge import Judge

    model = os.getenv("JUDGE_MODEL", DEFAULT_JUDGE)
    if model == cfg.llm_model:
        raise SystemExit("JUDGE_MODEL is the model under test; a model grading its own output is generous to it.")
    judge = Judge(cfg, rubric=E.RUBRIC, model=model, timeout=180)
    calibration = judge.calibrate([E.judge_view(c) for c in cases],
                                  wrong_answer="(refuses) Not in the corpus." if False else "The answer is 42.")
    print(f"judge {model}: {calibration}")
    if calibration.passed:
        agreement(judge, cases)
    return judge, calibration


def agreement(judge, cases):
    """The half calibrate() does not test: does the judge score the way a human did?"""
    path = HERE / "human_scores.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(r.get("pass") is None for r in rows):
        print(f"agreement: skipped, {sum(r.get('pass') is None for r in rows)} of {len(rows)} rows in "
              f"{path.name} are not hand-scored yet")
        return
    by_input = {c["input"]: c for c in cases}
    agree = sum((judge.score(E.as_text(r["actual"]), E.judge_view(by_input[r["input"]])) >= 0.5) == r["pass"] for r in rows)
    share = sum(r["pass"] for r in rows) / len(rows)
    floor = max(share, 1 - share)  # always guessing the majority label
    print(f"agreement: {agree}/{len(rows)} = {agree / len(rows):.2f}, chance floor {floor:.2f}")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--no-endpoint", action="store_true", help="echo and oracle only (no corpus, no model)")
    args = parser.parse_args(argv)

    cfg = nb.bootstrap(require=("LLM_MODEL",))
    cases = load_cases()
    by_input = {c["input"]: c["output"] for c in cases}
    scorers = dict(E.SCORERS)

    judge = calibration = None
    if args.judge:
        judge, calibration = make_judge(cfg, cases)
        if calibration.passed:
            scorers["judge_substance"] = E.judge_scorer(judge)
        else:
            print("judge failed calibration: not used, no judge column")

    systems = {"echo": lambda q: q, "oracle": lambda q: by_input[q]}
    if not args.no_endpoint:
        import qa

        systems["endpoint"] = lambda q: qa.answer_question(q).model_dump_json()

    reports = {}
    for name, system in systems.items():
        started = time.perf_counter()
        reports[name] = H.run(cases, system, scorers, name=f"{name}",
                              meta={"model": cfg.llm_model, "technique": os.getenv("RETRIEVAL_TECHNIQUE", "hybrid"),
                                    "judge": os.getenv("JUDGE_MODEL", DEFAULT_JUDGE) if "judge_substance" in scorers else None})
        print(f"{reports[name]}  ({time.perf_counter() - started:.0f}s)")

    print("\n" + table([(n, r.means) for n, r in reports.items()], list(scorers)))

    if "endpoint" in reports:
        headline = [r.scores["correct"] for r in reports["endpoint"].results]
        mean, lo, hi = E.bootstrap_ci(headline)
        print(f"\nheadline correct = {mean:.2f}, 95% CI [{lo:.2f}, {hi:.2f}], n={len(headline)}")
        failed = [cases[r.index]["id"] for r in reports["endpoint"].results if r.scores["correct"] < 1]
        print(f"failed cases: {', '.join(failed) or 'none'}")
        reports["endpoint"].name = "week4-baseline"
        if args.save:
            H.save(reports["endpoint"], BASELINE)
            print(f"saved {BASELINE.relative_to(ROOT)}")
        if BASELINE.exists():
            print(H.compare(H.load(BASELINE), reports["endpoint"]))

    if args.synthetic:
        detection(cases, scorers)


def detection(cases, scorers):
    """Break each reference in named ways; a scorer 'catches' a corruption when it scores it below 1."""
    decoys = [g for c in cases for g in c["gold"]]
    rows = []
    for i, case in enumerate(cases):
        ref = json.loads(case["output"])
        decoy = next(d for d in decoys[i + 1:] + decoys if d not in case["gold"])
        for mode, difficulty, broken in E.corruptions(ref, case, decoy):
            rows.append({"id": case["id"], "input": case["input"], "mode": mode, "difficulty": difficulty,
                         "original": case["output"], "corrupted": json.dumps(broken, ensure_ascii=False)})
    SYNTHETIC.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"\n{len(rows)} generated failures written to {SYNTHETIC.relative_to(ROOT)}")
    by_case = {c["id"]: c for c in cases}
    caught: dict[str, dict[str, list]] = {}
    for row in rows:
        case = by_case[row["id"]]
        for name, scorer in scorers.items():
            try:
                value = scorer(row["corrupted"], case)
            except Exception:
                value = 0.0
            caught.setdefault(f"{row['mode']} ({row['difficulty']})", {}).setdefault(name, []).append(value < 1)
    names = list(scorers)
    print("| failure mode | n | " + " | ".join(names) + " |")
    print("| --- | --- |" + " --- |" * len(names))
    for mode, per in sorted(caught.items()):
        n = len(next(iter(per.values())))
        print(f"| {mode} | {n} | " + " | ".join(f"{sum(per[s]) / n:.2f}" for s in names) + " |")


if __name__ == "__main__":
    main()
