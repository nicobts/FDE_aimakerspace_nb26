"""Hand-score human_scores.jsonl in the terminal: one answer at a time, pass or fail, and why.

    python use_case/evals/hand_score.py

Judge each answer as the researcher would: could they act on it as given? Decide before looking at
any scorer. Rows already scored are skipped; quit with q and resume later. Then
`python use_case/evals/run.py --judge` reports the judge's agreement with you.
"""

import json
import sys
from pathlib import Path

PATH = Path(__file__).with_name("human_scores.jsonl")


def show(row):
    out = json.loads(row["actual"])
    print("\n" + "=" * 78)
    print(f"[{row['id']}]  {row['input']}\n")
    if out.get("needs_human"):
        print(f"DECLINED: {out.get('needs_human_reason')}")
    else:
        print(out.get("answer"))
    print(f"\nsources: {', '.join(out.get('sources') or []) or '-'}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if row.get("pass") is not None:
            continue
        show(row)
        verdict = ""
        while verdict not in ("y", "n", "q"):
            verdict = input("\nWould you act on this answer as given? [y/n, q to stop] ").strip().lower()
        if verdict == "q":
            break
        row["pass"] = verdict == "y"
        while not row.get("why"):
            row["why"] = input("Why, in one sentence: ").strip()
        PATH.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    done = sum(r.get("pass") is not None for r in rows)
    print(f"\n{done} of {len(rows)} scored, {sum(bool(r.get('pass')) for r in rows)} pass.")


if __name__ == "__main__":
    main()
