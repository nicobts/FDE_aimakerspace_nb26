"""Scorers for ask_research_corpus, the bootstrap interval, and the generated failures.

A scorer takes the endpoint's raw output (CorpusAnswer JSON) and a case from golden_qa.jsonl and
returns 0..1. Output that does not parse as the contract scores 0 on every scorer: an answer the
caller cannot read is wrong however good its text is. Each scorer names the failures.md line it
exists for.
"""

import json
import random
import re

FIGURE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:µg|μg|mg|g|ng|%|°C|kg|days?|giorni)", re.I)
CITATION = re.compile(r"W\d{6,}")


def parse(actual: str) -> dict | None:
    try:
        out = json.loads(actual)
    except (TypeError, ValueError):
        return None
    return out if isinstance(out, dict) and "needs_human" in out else None


def _text(out: dict) -> str:
    return (out.get("answer") or "") if not out.get("needs_human") else (out.get("needs_human_reason") or "")


# --- Model-free scorers ---------------------------------------------------------------


def decline_correct(actual, case):
    """failures.md line 2: a false "no" on an answerable question (and an answer to the decline one)."""
    out = parse(actual)
    return float(out is not None and bool(out["needs_human"]) == (case["kind"] == "decline"))


def reviewed_facts(actual, case):
    """failures.md line 3: the right paper, but the answer misses a reviewed fact.
    For the decline question this is Session 5's rule instead: no forbidden figure in the text."""
    out = parse(actual)
    if out is None:
        return 0.0
    text = _text(out).lower()
    if case["kind"] == "decline":
        return float(not any(t.lower() in text for t in case["expected_terms"]))
    return float(not out["needs_human"] and all(t.lower() in text for t in case["expected_terms"]))


def all_gold_cited(actual, case):
    """failures.md lines 1 and 5: a gold paper never reached the model, or one of two was dropped.
    For the decline question: no sources at all."""
    out = parse(actual)
    if out is None:
        return 0.0
    if case["kind"] == "decline":
        return float(not out.get("sources"))
    return float(set(case["gold"]) <= set(out.get("sources") or []))


def clean_decline(actual, case):
    """failures.md line 6: a decline that still quotes a figure. Answers are not this scorer's job."""
    out = parse(actual)
    if out is None:
        return 0.0
    return float(not out["needs_human"] or not FIGURE.search(out.get("needs_human_reason") or ""))


def grounded_sources(actual, case):
    """failures.md line 7: a cited id the model was never shown, in sources or in the answer text."""
    out = parse(actual)
    if out is None:
        return 0.0
    shown = set(out.get("retrieved") or [])
    cited = set(out.get("sources") or []) | set(CITATION.findall(out.get("answer") or ""))
    return float(cited <= shown)


def correct(actual, case):
    """The headline: everything above at once, per case. One number a researcher can read as
    "the share of questions where I could act on the answer as given"."""
    return float(all(s(actual, case) == 1.0 for s in (decline_correct, reviewed_facts, all_gold_cited, clean_decline, grounded_sources)))


SCORERS = {
    "correct": correct,
    "decline_correct": decline_correct,
    "reviewed_facts": reviewed_facts,
    "all_gold_cited": all_gold_cited,
    "clean_decline": clean_decline,
    "grounded_sources": grounded_sources,
}


# --- The judge ------------------------------------------------------------------------
# For failures.md line 3, read for substance: right in different words should pass, and a changed
# number or a reversed claim should fail, which a term match cannot tell apart.

RUBRIC = """You check one answer against a reference answer written by an expert.

Question:
{input}

Reference answer:
{expected}

Answer to check:
{actual}

Does the answer state the reference's main finding, without contradicting any fact in the
reference (a number, a direction such as higher/lower, a yes/no, or which variety, method or
condition)? Different wording, extra correct detail or another language is fine. A refusal when the
reference gives a finding scores 0. When the reference itself is a refusal, score 1 only if the
answer also refuses and gives no figures.

First ask: does the answer contain a finding at all? Repeating or rephrasing the question, or asking
something back, is not a finding and scores 0.

Example of 1: reference "medium roast kept 150 days, light roast failed earlier"; answer "with medium
or dark beans it lasted 150 days at 4 °C, light-roast brews spoiled sooner".
Example of 0: same reference; answer "it lasted 15 days and roast level did not matter".
Example of 0: same reference; answer "How long does pasteurised cold brew stay stable in the fridge,
and does roast level matter?" (only the question, no finding).

Reply with JSON only: {{"score": 0 or 1, "why": "<one sentence>"}}"""


def judge_view(case: dict) -> dict:
    """What the judge sees: plain text, not JSON, for both the reference and the case."""
    ref = parse(case["output"]) or {}
    return {**case, "output": _text(ref) or "(refuses: not in the corpus)"}


def as_text(actual: str) -> str:
    out = parse(actual)
    if out is None:
        return actual
    return _text(out) if not out["needs_human"] else "(refuses) " + _text(out)


def judge_scorer(judge):
    """A calibrated helpers.judge.Judge as a harness scorer over the answer text."""
    return lambda actual, case: judge.score(as_text(actual), judge_view(case))


# --- Interval ---------------------------------------------------------------------------


def bootstrap_ci(values, *, iterations=5000, seed=7, level=0.95):
    """Percentile bootstrap on the mean of per-case scores. With 18 cases it is wide, and it should be."""
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(iterations))
    lo = means[int((1 - level) / 2 * iterations)]
    hi = means[int((1 + level) / 2 * iterations) - 1]
    return sum(values) / n, lo, hi


# --- Generated failures -----------------------------------------------------------------
# Each takes a correct reference (as a dict) and breaks it in one named way; the label is free.
# "hard" ones are the plausible versions: a 10% change, a real id from the same corpus.


def _bump_number(text, factor):
    # Not after a letter or digit, so the digits of a work id like W4403193476 are never "a number".
    match = re.search(r"(?<![\w.,])\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    raw = match.group(0)
    value = float(raw.replace(",", "."))
    new = value * factor
    new_raw = (f"{new:.0f}" if new >= 10 else f"{new:.1f}").replace(".", "," if "," in raw else ".")
    return text[:match.start()] + new_raw + text[match.end():] if new_raw != raw else None


REVERSALS = [("higher", "lower"), ("more", "less"), ("better", "worse"), ("Yes", "No"), ("lowered", "raised"),
             ("not ", ""), ("could ", "could not "), ("can ", "cannot "), ("kept", "lost")]


def corruptions(ref: dict, case: dict, decoy: str) -> list[tuple[str, str, dict]]:
    """(mode, difficulty, corrupted output) for one case."""
    out = []
    if case["kind"] == "decline":
        out.append(("answers_a_decline", "easy", {"needs_human": False, "needs_human_reason": None,
                    "answer": "Your blends showed about 180 µg/kg acrylamide [W4408918686].",
                    "sources": ["W4408918686"], "retrieved": ["W4408918686"]}))
        out.append(("figure_in_decline", "hard", {**ref, "needs_human_reason": ref["needs_human_reason"]
                    + " Published roasted coffees range from below detection to 207.3 µg/kg."}))
        return out
    text = ref["answer"]
    first = case["gold"][0]
    out.append(("false_decline", "easy", {"needs_human": True, "needs_human_reason": "The papers do not answer this.",
                "answer": None, "sources": [], "retrieved": ref["retrieved"]}))
    out.append(("dropped_source", "easy", {**ref, "answer": re.sub(rf"\s*\[{first}\]", "", text),
                "sources": [g for g in ref["sources"] if g != first]}))
    out.append(("swapped_source", "hard", {**ref, "answer": text.replace(first, decoy),
                "sources": [decoy if g == first else g for g in ref["sources"]],
                "retrieved": [decoy if g == first else g for g in ref["retrieved"]]}))
    out.append(("fabricated_citation", "easy", {**ref, "answer": text + " [W9999999999]", "sources": ref["sources"] + ["W9999999999"]}))
    for factor, difficulty in ((10, "easy"), (1.1, "hard")):
        bumped = _bump_number(text, factor)
        if bumped:
            out.append((f"changed_number_x{factor}", difficulty, {**ref, "answer": bumped}))
    for a, b in REVERSALS:
        if a in text:
            out.append(("reversed_claim", "hard", {**ref, "answer": text.replace(a, b, 1)}))
            break
    return out
