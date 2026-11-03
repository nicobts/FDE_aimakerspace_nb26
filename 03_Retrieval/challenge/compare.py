"""Measure the retrieval techniques against the labels and write results.md.

    uv run python 03_Retrieval/challenge/compare.py                 # everything
    uv run python 03_Retrieval/challenge/compare.py --only ranking  # no answer model, seconds
    uv run python 03_Retrieval/challenge/compare.py --embed-tokens  # also re-measure corpus embedding tokens

Three parts, cheapest first:
  1. ranking   each ranker alone: does every gold paper reach the top 5 / top 10? No model.
  2. agents    Session 5's loop and score(), unchanged except for the tools it is handed.
  3. endpoint  the shipped path (qa.answer_question): one retrieval, one model call.
Traces go to use_case/data/runs/ (gitignored); the table goes to results.md next to this file.
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "01_Product_Engineering" / "challenge"))
sys.path.insert(0, str(Path(__file__).parent))

import litellm  # noqa: E402

from helpers import nb  # noqa: E402
from scout.labels import load_labels, to_case  # noqa: E402
from scout.store import Store  # noqa: E402

LABELS = ROOT / "use_case" / "evals" / "retrieval.jsonl"
RESULTS = Path(__file__).parent / "results.md"
CHECKPOINT = ROOT / "use_case" / "data" / "runs" / "tc3_checkpoint.jsonl"  # one line per finished (technique, question)


def load_checkpoint():
    if not CHECKPOINT.exists():
        return {}
    done = {}
    for line in CHECKPOINT.read_text(encoding="utf-8").splitlines():
        if line:
            t = json.loads(line)
            done[(t["technique"], t["id"])] = t
    return done


def save_checkpoint(trace):
    # Written after every question, so a failed call (credit, network) costs one question, not the run.
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False) + "\n")


ROW_KEYS = ("id", "kind", "technique", "pass", "cited_expected_page", "cited_all_gold", "calls",
            "evidence_chars", "latency_s", "stopped", "gold_seen")
MAX_TURNS = 6

SYSTEM = (
    "Answer coffee R&D questions only from tool evidence, which comes from published research papers. "
    "Investigate before answering. Cite every work you use by its id in square brackets, for example "
    "[W4403193476]; when a question needs several papers, find and cite each. If the evidence does not "
    "answer the question, say so and give no figures: the corpus never holds the company's own products, "
    "blends or lab data. Answer in the language of the question, in at most 150 words."
)


# --- Session 5, unchanged in substance -------------------------------------------------

DECLINE_MARKERS = ("not ", "no ", "cannot", "can't", "unavailable", "does not", "doesn't", "isn't", "only covers", "no data")


def score(case, result):
    answer = result["answer"].lower()
    if case.get("must_decline"):
        passed = any(m in answer for m in DECLINE_MARKERS) and not any(t.lower() in answer for t in case["expected_terms"])
    else:
        passed = all(t.lower() in answer for t in case["expected_terms"])
    return {
        "pass": passed,
        "cited_expected_page": any(p.lower() in answer for p in case["expected_pages"]),
        # Session 5 accepts any one gold page; a multi-hop answer citing one of two has only half an answer.
        "cited_all_gold": all(p.lower() in answer for p in case["expected_pages"]),
        "calls": len(result["trace"]),
        "evidence_chars": result["evidence_chars"],
        "latency_s": round(result["latency_s"], 2),
        "stopped": result["stopped"],
    }


def ask_model(cfg, messages, tools):
    # OpenRouter reserves credit for max_tokens up front, and the default is the model's maximum (65,536).
    return litellm.completion(messages=messages, tools=tools, temperature=0, max_tokens=1500, timeout=600,
                              **llm_options(), **cfg.kwargs()).choices[0].message


def llm_options() -> dict:
    # Provider-specific knobs stay in config: for Ollama, {"num_ctx": 32768, "think": false}, because
    # the default context silently truncates a tool loop and thinking mode talks about tools instead of calling them.
    return json.loads(os.getenv("LLM_OPTIONS") or "{}")


def run_agent(cfg, question, tools, funcs, max_turns=MAX_TURNS):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    trace, chars, evidence = [], 0, []
    started = time.perf_counter()
    for _ in range(max_turns):
        msg = ask_model(cfg, messages, tools)
        calls = msg.tool_calls or []
        if not calls:
            return {"answer": (msg.content or "").strip(), "trace": trace, "evidence_chars": chars,
                    "latency_s": time.perf_counter() - started, "stopped": "answer", "evidence": evidence}
        shaped = [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": shaped})
        for call in shaped:
            name = call["function"]["name"]
            args = {}
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
                if name not in funcs:
                    raise KeyError(f"unknown tool {name}")
                result = str(funcs[name](**args))
            except Exception as exc:
                result = f"(tool error: {type(exc).__name__}: {exc})"
            chars += len(result)
            evidence.append(result)
            trace.append({"tool": name, "args": args, "chars": len(result)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return {"answer": "(max turns reached)", "trace": trace, "evidence_chars": chars,
            "latency_s": time.perf_counter() - started, "stopped": "max_turns", "evidence": evidence}


# --- The three parts ------------------------------------------------------------------


def ranking_table(labels, retrieval):
    """Recall of every gold paper at 5 and 10 chunks, per ranker, with no model in the way."""
    rows = []
    for name in ("bm25", "dense", "hybrid"):
        at5 = at10 = 0
        answerable = [l for l in labels if l["gold"]]
        for label in answerable:
            works = [hit["source"] for hit in retrieval.search(label["question"], k=10, technique=name)]
            at5 += set(label["gold"]) <= set(works[:5])
            at10 += set(label["gold"]) <= set(works)
        rows.append({"ranker": name, "all_gold@5": f"{at5}/{len(answerable)}", "all_gold@10": f"{at10}/{len(answerable)}"})
    top1 = {l["id"]: round(retrieval.dense_rank(l["question"], 1)[0][1], 3) for l in labels}
    return rows, top1


def gold_seen(label, texts):
    blob = "\n".join(texts)
    return all(g in blob for g in label["gold"]) if label["gold"] else None


def run_agents(cfg, labels, retrieval, techniques, done):
    rows, traces = [], []
    for technique in techniques:
        tools, funcs = retrieval.toolset(technique)
        for label in labels:
            if (f"agent-{technique}", label["id"]) in done:
                t = done[(f"agent-{technique}", label["id"])]
                rows.append({k: t[k] for k in ROW_KEYS}); traces.append(t)
                continue
            result = run_agent(cfg, label["question"], tools, funcs)
            row = {"id": label["id"], "kind": label["kind"], "technique": f"agent-{technique}",
                   **score(to_case(label), result), "gold_seen": gold_seen(label, result["evidence"])}
            rows.append(row)
            traces.append({**row, "answer": result["answer"], "trace": result["trace"]})
            save_checkpoint(traces[-1])
            print(f"  {row['technique']:13} {label['id']} pass={row['pass']!s:5} all_gold={row['cited_all_gold']!s:5} "
                  f"calls={row['calls']} chars={row['evidence_chars']} {row['latency_s']}s")
    return rows, traces


def run_endpoint(labels, qa, techniques, done):
    rows, traces = [], []
    for technique in techniques:
        for label in labels:
            if (f"endpoint-{technique}", label["id"]) in done:
                t = done[(f"endpoint-{technique}", label["id"])]
                rows.append({k: t[k] for k in ROW_KEYS}); traces.append(t)
                continue
            started = time.perf_counter()
            out = qa.answer_question(label["question"], technique=technique)
            latency = time.perf_counter() - started
            # The decline reason is what a user reads, so it is what gets scored.
            text = out.answer if not out.needs_human else f"NOT IN CORPUS: {out.needs_human_reason}"
            text += " " + " ".join(out.sources)
            result = {"answer": text, "trace": [{"tool": "retrieve"}], "evidence_chars": 0, "latency_s": latency, "stopped": "answer"}
            row = {"id": label["id"], "kind": label["kind"], "technique": f"endpoint-{technique}", **score(to_case(label), result),
                   "gold_seen": (set(label["gold"]) <= set(out.retrieved)) if label["gold"] else None}
            row["evidence_chars"] = len(qa.retrieval.format_hits(qa.retrieval.search(label["question"], k=5, technique=technique)))
            rows.append(row)
            traces.append({**row, **out.model_dump()})
            save_checkpoint(traces[-1])
            print(f"  {row['technique']:15} {label['id']} pass={row['pass']!s:5} all_gold={row['cited_all_gold']!s:5} {row['latency_s']}s")
    return rows, traces


def summarise(rows):
    by = {}
    for r in rows:
        by.setdefault(r["technique"], []).append(r)
    out = []
    for technique, rs in by.items():
        answerable = [r for r in rs if r["gold_seen"] is not None]
        out.append({
            "technique": technique,
            "pass": f"{sum(r['pass'] for r in rs)}/{len(rs)}",
            "cited (any gold)": f"{sum(r['cited_expected_page'] for r in answerable)}/{len(answerable)}",
            "cited (all gold)": f"{sum(r['cited_all_gold'] for r in answerable)}/{len(answerable)}",
            "calls (mean)": round(statistics.mean(r["calls"] for r in rs), 1),
            "evidence chars (mean)": round(statistics.mean(r["evidence_chars"] for r in rs)),
            "latency s (median)": round(statistics.median(r["latency_s"] for r in rs), 1),
            "stopped at max turns": sum(r["stopped"] == "max_turns" for r in rs),
        })
    return out


def md_table(rows):
    if not rows:
        return "_not run_\n"
    head = list(rows[0])
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    lines += ["| " + " | ".join(str(r[h]) for h in head) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def embed_corpus_tokens(cfg, retrieval, batch=64):
    """Re-embed every chunk once and add up the tokens the endpoint reports. Measured, not estimated."""
    texts = [c["text"] for c in retrieval.corpus().chunks]
    total = 0
    for i in range(0, len(texts), batch):
        response = litellm.embedding(input=texts[i:i + batch], timeout=600, **cfg.embed_kwargs())
        total += getattr(response.usage, "prompt_tokens", 0) or 0
    return total, len(texts)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=["ranking", "agents", "endpoint"])
    parser.add_argument("--agents", default="bm25,wiki,dense,hybrid")
    parser.add_argument("--endpoint", default="hybrid,bm25")
    parser.add_argument("--embed-tokens", action="store_true")
    parser.add_argument("--fresh", action="store_true", help="ignore the checkpoint and rerun every question")
    # BM25 and wiki agents need no embedding model, so they can run while it is still unavailable.
    parser.add_argument("--skip-ranking", action="store_true", help="skip the ranking table (needs embeddings)")
    args = parser.parse_args(argv)

    cfg = nb.bootstrap(require=("LLM_MODEL", "EMBED_MODEL"))
    import qa
    import retrieval

    labels = load_labels(LABELS, store=Store(ROOT / "use_case" / "data" / "scout.sqlite"))
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    print(f"{len(labels)} labels · {len(retrieval.corpus().chunks)} chunks · {len(retrieval.corpus().pages)} pages · model {cfg.llm_model}")

    ranking, top1 = ([], {}) if args.skip_ranking else ranking_table(labels, retrieval)
    print(md_table(ranking))
    rows, traces = [], []
    if args.fresh and CHECKPOINT.exists():
        CHECKPOINT.rename(CHECKPOINT.with_name(f"tc3_checkpoint_{stamp}.jsonl"))
    done = load_checkpoint()
    if done:
        print(f"resuming: {len(done)} finished questions in {CHECKPOINT.name}")
    if args.only in (None, "agents"):
        r, t = run_agents(cfg, labels, retrieval, args.agents.split(","), done)
        rows += r; traces += t
    if args.only in (None, "endpoint"):
        r, t = run_endpoint(labels, qa, args.endpoint.split(","), done)
        rows += r; traces += t

    runs = ROOT / "use_case" / "data" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"tc3_compare_{stamp}.json").write_text(json.dumps({"rows": rows, "traces": traces, "top1_cosine": top1},
                                                               ensure_ascii=False, indent=1), encoding="utf-8")
    embed = embed_corpus_tokens(cfg, retrieval) if args.embed_tokens else None

    if args.only is None:
        per_q = [{"id": r["id"], "kind": r["kind"], "technique": r["technique"], "pass": r["pass"],
                  "all gold cited": r["cited_all_gold"], "gold reached the model": r["gold_seen"],
                  "calls": r["calls"], "evidence chars": r["evidence_chars"], "latency s": r["latency_s"]} for r in rows]
        settings = [
            f"- Run: {stamp}, {len(labels)} labels from `use_case/evals/retrieval.jsonl`",
            f"- Answer model: `{cfg.llm_model}`, options {llm_options() or 'none'}, temperature 0; agent turn budget {MAX_TURNS}; Session 5's `run_agent` and `score`",
            f"- Corpus: {len(retrieval.corpus().pages)} papers, {len(retrieval.corpus().chunks)} chunks (one per abstract, card or 900-char full-text piece, 150 overlap)",
            f"- Embedding model: `{cfg.embed_model}`; dense = cosine over L2-normalised vectors (NumPy, no vector database)",
            "- Hybrid: reciprocal rank fusion of BM25 top 50 and dense top 50, RRF k = 60",
            f"- Endpoint: top 5 chunks, one answer call, decline gate at dense cosine < {qa.MIN_SIMILARITY}",
            f"- Query-side embedding tokens this run: {retrieval.EMBED_TOKENS['query']} (*measured*)",
        ]
        if embed:
            settings.append(f"- Corpus embedding: {embed[0]:,} tokens for {embed[1]:,} chunks (*measured*, one full re-embed)")
        RESULTS.write_text("\n".join([
            "# TC3 retrieval comparison", "",
            "Generated by `compare.py`; traces in `use_case/data/runs/` (gitignored).", "",
            "## Settings", "", *settings, "",
            "## Ranking only (no model): did every gold paper reach the top k chunks?", "", md_table(ranking),
            "## Results", "", md_table(summarise(rows)),
            "## Top-1 dense cosine per question (sets the decline gate)", "",
            md_table([{"id": k, "cosine": v} for k, v in top1.items()]),
            "## Per question", "", md_table(per_q),
        ]), encoding="utf-8")
        print(f"wrote {RESULTS}")
    print(md_table(summarise(rows)))


if __name__ == "__main__":
    main()
