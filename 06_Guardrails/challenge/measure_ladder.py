"""TC6 Step 5: price every rung with both numbers, from one pass of the attacks and the goldens.

    python 06_Guardrails/challenge/measure_ladder.py

For each configuration (each rung alone, the shipped ladder, the full ladder) the same rails object
reads every direct attack in use_case/evals/attacks.jsonl and every golden question in
golden_qa.jsonl, so "caught" and "refused" cannot drift apart. The output rule is priced the same way
on the leaked replies and on the golden reference answers, and the passage check on every chunk of the
corpus and on the poisoned texts. Writes ladder_results.json beside this file.

Since Step 6 a question-side rung flags for review instead of refusing, so "refused" below counts the
real questions a rung would have flagged: the review load a reviewer pays, not a researcher turned away.
"""

import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "01_Product_Engineering" / "challenge"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=False)
if not (os.getenv("INJECTION_MODEL") and os.getenv("INJECTION_API_BASE")):
    raise SystemExit("Set INJECTION_MODEL and INJECTION_API_BASE: the judge rung reads attack-shaped text.")

import ladder  # noqa: E402

EVALS = ROOT / "use_case" / "evals"
OUT = Path(__file__).with_name("ladder_results.json")
CONFIGS = {"rules": ("rules",), "classifier": ("classifier",), "judge": ("judge",),
           "shipped: rules + classifier": ("rules", "classifier"),
           "full: rules + classifier + judge": ("rules", "classifier", "judge")}


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    rows = [r for r in jsonl(EVALS / "attacks.jsonl") if r["door"] == "direct" and r["prompt"] == "before"]
    attacks = list({r["input"]: r for r in rows}.values())
    winners = [a for a in attacks if a["winner"]]
    golden = jsonl(EVALS / "golden_qa.jsonl")
    print(f"{len(attacks)} direct attacks ({len(winners)} landed before the fix), {len(golden)} golden questions")

    results = {}
    for name, rungs in CONFIGS.items():
        rails = ladder.build(rungs, output=False)
        ladder.check_input("warm up the rails and the model", rails)
        caught, refused, ms = [], [], []
        for a in attacks:
            rung, t = ladder.check_input(a["input"], rails)
            ms.append(t)
            if rung:
                caught.append(a["input"])
        for case in golden:
            rung, t = ladder.check_input(case["input"], rails)
            ms.append(t)
            if rung:
                refused.append({"id": case["id"], "input": case["input"], "rung": rung})
        results[name] = {
            "caught": len(caught), "attacks": len(attacks),
            "winners_caught": sum(w["input"] in caught for w in winners), "winners": len(winners),
            "refused": len(refused), "golden": len(golden), "refused_cases": refused,
            "ms_median": round(statistics.median(ms), 1), "ms_p90": round(sorted(ms)[int(0.9 * len(ms)) - 1], 1),
            "missed": [a["input"] for a in attacks if a["input"] not in caught],
        }
        r = results[name]
        print(f"{name:34} caught {r['caught']}/{r['attacks']} (winners {r['winners_caught']}/{r['winners']}) · "
              f"refused {r['refused']}/{r['golden']} golden · {r['ms_median']} ms median, {r['ms_p90']} p90", flush=True)

    # The output rule, on what actually leaked and on the reference answers a researcher would accept.
    rails = ladder.build((), output=True)
    # attack.py keeps the first 600 characters of a leaking reply; a code printed after that is not in the
    # sample, so only samples that still hold it can price the rule.
    sys.path.insert(0, str(EVALS))
    from harness import leaked as has_canary

    leaky = [r for r in jsonl(EVALS / "attacks.jsonl") if r["leaked"] and r["door"] != "card-document"]
    leaked = [r for r in leaky if has_canary(r["sample"])]
    print(f"{len(leaky) - len(leaked)} leaked replies left out: the code is past the stored 600 characters")
    out_caught = sum(bool(ladder.check_output(r["input"], r["sample"], rails)) for r in leaked)
    out_refused = [c["id"] for c in golden if ladder.check_output(c["input"], c["output"], rails)]
    results["output rules"] = {"caught": out_caught, "leaked_replies": len(leaked),
                               "refused": len(out_refused), "golden": len(golden), "refused_cases": out_refused}
    print(f"{'output rules':34} caught {out_caught}/{len(leaked)} leaked replies · "
          f"refused {len(out_refused)}/{len(golden)} golden reference answers")
    # The passage check (qa.INSTRUCTION_LIKE): the indirect door, which no question-side rung can see.
    import qa
    import retrieval

    chunks = [json.loads(line) for line in (retrieval.DATA_DIR / "index" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    corpus_flagged = sorted({c["source"] for c in chunks if qa.INSTRUCTION_LIKE.search(c["text"])})
    poisoned = {r["kind"]: r["context"] for r in jsonl(EVALS / "attacks.jsonl") if r.get("context")}
    poisoned.update({r["kind"]: r["input"] for r in jsonl(EVALS / "attacks.jsonl") if r["kind"] == "card-poisoned"})
    caught_p = sorted(k for k, t in poisoned.items() if qa.INSTRUCTION_LIKE.search(t))
    results["passage check"] = {"caught": len(caught_p), "poisoned_texts": len(poisoned), "caught_kinds": caught_p,
                                "corpus_chunks": len(chunks), "corpus_chunks_flagged": sum(
                                    bool(qa.INSTRUCTION_LIKE.search(c["text"])) for c in chunks),
                                "corpus_papers_flagged": corpus_flagged}
    print(f"{'passage check':34} caught {len(caught_p)}/{len(poisoned)} poisoned texts · "
          f"flagged {results['passage check']['corpus_chunks_flagged']}/{len(chunks)} corpus chunks")
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
