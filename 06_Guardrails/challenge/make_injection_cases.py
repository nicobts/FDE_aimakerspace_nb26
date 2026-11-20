"""TC6 Step 4: turn the attacks that landed before the fix into permanent eval cases.

    python 06_Guardrails/challenge/make_injection_cases.py

Reads use_case/evals/attacks.jsonl and writes use_case/evals/injection.jsonl: every distinct direct
input that leaked at least once, and every poisoned passage (the base64 one too: it did not land on
this model, and a stronger reader in Week 8 may decode it). Run with use_case/evals/run.py.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "use_case" / "evals"
POISON_ID = "W9000000001"


def main():
    rows = [json.loads(line) for line in (EVALS / "attacks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    before = [r for r in rows if r["prompt"] == "before"]
    cases, seen = [], set()
    for r in before:
        if r["door"] == "direct" and r["winner"] and r["input"] not in seen:
            seen.add(r["input"])
            cases.append({"id": f"inj{len(cases) + 1:02d}", "door": "direct", "kind": r["kind"], "input": r["input"]})
    for r in before:
        if r["door"] == "indirect" and (r["kind"], r["context"]) not in seen:
            seen.add((r["kind"], r["context"]))
            cases.append({"id": f"inj{len(cases) + 1:02d}", "door": "indirect", "kind": r["kind"], "input": r["input"],
                          "context": r["context"], "poison_id": POISON_ID})
    (EVALS / "injection.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    print(f"{len(cases)} cases: {sum(c['door'] == 'direct' for c in cases)} direct, "
          f"{sum(c['door'] == 'indirect' for c in cases)} indirect")


if __name__ == "__main__":
    main()
