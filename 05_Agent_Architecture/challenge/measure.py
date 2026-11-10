"""Measure three ways of reaching the same search capability, and write results.md.

    uv run --group week3 python 05_Agent_Architecture/challenge/measure.py
    uv run --group week3 python 05_Agent_Architecture/challenge/measure.py --repeats 3

Three ways (01_Product_Engineering/challenge): the shipped pipeline, a tool loop, the subagent.
Two requests from the labels: one that needs a single search, one whose question has several parts.
Two sizes: demo scale (each passage cut to 200 characters) and the real response the endpoint sends
the model (passages up to retrieval.PASSAGE_CHARS). Four numbers per run, as in Session 10: model
calls, capability calls, seconds, tokens. Traces go to use_case/data/runs/ (gitignored).
"""

import argparse
import datetime
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "01_Product_Engineering" / "challenge"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")  # the shell wins over .env, so a local model can be chosen per run

import agent  # noqa: E402
import retrieval  # noqa: E402

LABELS = ROOT / "use_case" / "evals" / "retrieval.jsonl"
RESULTS = Path(__file__).parent / "results.md"
TRACES = ROOT / "use_case" / "data" / "runs" / "tc5_measure.jsonl"
REQUESTS = {"1 search": "q08", "several searches": "q13"}
DEMO_PASSAGE_CHARS = 200
SIZES = {"demo": DEMO_PASSAGE_CHARS, "real": None}


class CountingSearch:
    """The capability, counted: how often it ran and how many bytes each call handed to a model."""

    def __init__(self, *, passage_chars: int | None):
        self.passage_chars = passage_chars
        self.calls = 0
        self.response_bytes: list[int] = []

    def __call__(self, query: str, *, k: int = 5, technique: str = "hybrid") -> list[dict]:
        self.calls += 1
        hits = retrieval.search(query, k=k, technique=technique)
        if self.passage_chars:
            hits = [{**hit, "text": hit["text"][:self.passage_chars]} for hit in hits]
        self.response_bytes.append(len(retrieval.format_hits(hits).encode("utf-8")))
        return hits


def measure(way: str, case: dict, *, passage_chars: int | None) -> dict:
    meter, search = agent.Meter(), CountingSearch(passage_chars=passage_chars)
    started = time.perf_counter()
    result = agent.WAYS[way](case["question"], search=search, meter=meter)
    gold = case.get("gold") or []
    return {
        "way": way, "id": case["id"],
        "model calls": meter.calls,
        "capability calls": search.calls,
        "seconds": round(time.perf_counter() - started, 1),
        "tokens": meter.tokens,
        "tool calls per turn": meter.tool_calls_per_turn,
        "bytes per response": round(statistics.mean(search.response_bytes)) if search.response_bytes else 0,
        "gold cited": f"{sum(page in result.sources for page in gold)}/{len(gold)}",
        "declined": result.needs_human,
        "answer": result.answer or result.needs_human_reason,
    }


def table(rows: list[dict], columns: list[str]) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines += ["| " + " | ".join(str(row[c]) for c in columns) + " |" for row in rows]
    return "\n".join(lines)


def median_row(runs: list[dict]) -> dict:
    """One row per (way, request, size): the median of the repeats on each number."""
    row = dict(runs[0])
    for key in ("model calls", "capability calls", "seconds", "tokens", "bytes per response"):
        row[key] = statistics.median(run[key] for run in runs)
        row[key] = int(row[key]) if row[key] == int(row[key]) else round(row[key], 1)
    row["tokens, all runs"] = ", ".join(str(run["tokens"]) for run in runs)
    return row


def searched(run: dict) -> bool:
    # An attempt where the model answered without calling the capability is declined by agent.py
    # and costs almost nothing, so it would flatter the way's numbers. It is counted, then re-measured.
    return run["capability calls"] > 0


MAX_SKIPS = 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()

    # The labels file opens with a header row that has no id.
    rows = map(json.loads, filter(None, LABELS.read_text(encoding="utf-8").splitlines()))
    cases = {row["id"]: row for row in rows if "id" in row}
    retrieval.corpus()  # load the index before the clock starts, so the first run is not charged for it
    retrieval.embed_query("warm up")

    # Every finished run is kept, so a run that is interrupted (a local model is slow) picks up
    # where it stopped. Delete the trace file to measure from scratch.
    TRACES.parent.mkdir(parents=True, exist_ok=True)
    done = [json.loads(line) for line in TRACES.read_text(encoding="utf-8").splitlines() if line] if TRACES.exists() else []
    rows = []
    with TRACES.open("a", encoding="utf-8") as traces:
        for size, passage_chars in SIZES.items():
            for label, case_id in REQUESTS.items():
                for way in agent.WAYS:
                    attempts = [r for r in done if (r["size"], r["request"], r["way"]) == (size, label, way)]
                    while sum(searched(r) for r in attempts) < args.repeats and len(attempts) < args.repeats + MAX_SKIPS:
                        run = {"size": size, "request": label, **measure(way, cases[case_id], passage_chars=passage_chars)}
                        traces.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), **run}, ensure_ascii=False) + "\n")
                        traces.flush()
                        attempts.append(run)
                        print({k: v for k, v in run.items() if k != "answer"}, flush=True)
                    runs = [r for r in attempts if searched(r)][:args.repeats] or attempts[:args.repeats]
                    rows.append({**median_row(runs), "skipped the search": f"{sum(not searched(r) for r in attempts)} of {len(attempts)}"})

    numbers = ["way", "model calls", "capability calls", "seconds", "tokens"]
    out = [f"# TC5 measurement\n\nModel `{os.getenv('LLM_MODEL')}`, {datetime.date.today()}, "
           f"{'median of ' + str(args.repeats) + ' runs' if args.repeats > 1 else 'one run'} per cell. "
           f"All numbers *measured* by `measure.py`.\n"]
    for size in SIZES:
        cut = f"passages cut to {DEMO_PASSAGE_CHARS} characters" if size == "demo" else f"passages as shipped, up to {retrieval.PASSAGE_CHARS:,} characters"
        out.append(f"## {size.capitalize()} scale ({cut})\n")
        for label, case_id in REQUESTS.items():
            part = [r for r in rows if r["size"] == size and r["request"] == label]
            out.append(f"**{label}** ({case_id}: {cases[case_id]['question']})\n")
            extra = ["bytes per response", "tool calls per turn", "gold cited", "skipped the search"] +(["tokens, all runs"] if args.repeats > 1 else [])
            out.append(table(part, numbers + extra) + "\n")
    RESULTS.write_text("\n".join(out), encoding="utf-8")
    print(f"\nwrote {RESULTS}")


if __name__ == "__main__":
    main()
