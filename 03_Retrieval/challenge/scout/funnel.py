"""The funnel's cheap stages: similarity to the focus, model triage, and the pick of works to card."""

import json

import numpy as np

import helpers.llm

# Fixed prefix first, variable part last: providers cache on the prefix, and a screen makes hundreds of these calls.
TRIAGE_PROMPT = """You screen coffee-research papers for a researcher. Judge the paper below against the researcher's focus.

Reply with exactly one JSON object and nothing else, with these keys:
- "relevance": 1 = background only, 2 = worth reading, 3 = act on it, judged against the focus
- "reason": under 20 words explaining the score
- "is_study": true when the text reports a study, review or meta-analysis; false for an editorial, news item or marketing

Researcher's focus:
{focus}

Title: {title}

Abstract:
{abstract}
"""


def _text(work: dict) -> str:
    # A work without an abstract should not reach here, but the title alone beats failing the batch.
    abstract = work.get("abstract")
    return f"{work['title']}\n{abstract}" if abstract else work["title"]


def similarity_to_focus(embedder, works: list[dict], *, focus: str) -> dict[str, float]:
    if not works:
        # An embedder may raise or return a 1-D empty array for no texts; nothing to rank anyway.
        return {}
    # Separate calls keep the focus out of the per-work embedding cache and out of the works' batch.
    focus_vec = np.asarray(embedder.embed([focus]))[0]
    vecs = np.asarray(embedder.embed([_text(w) for w in works]))
    # Embedder output is unit-normalised, so the dot product is the cosine; clamp away float noise and negatives.
    sims = np.clip(vecs @ focus_vec, 0.0, 1.0)
    return {w["id"]: float(s) for w, s in zip(works, sims)}


def triage_work(
    cfg,
    work: dict,
    *,
    focus: str,
    model: str | None = None,
    stats: helpers.llm.CallStats | None = None,
    chat=helpers.llm.chat,
) -> dict | None:
    prompt = TRIAGE_PROMPT.format(focus=focus, title=work["title"], abstract=work.get("abstract") or "")
    # Only forward what was set, so an injected chat need not accept either.
    kwargs = {k: v for k, v in (("model", model), ("stats", stats)) if v is not None}
    reply = chat(cfg, prompt, **kwargs)
    start, end = reply.find("{"), reply.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        data = json.loads(reply[start : end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    relevance, is_study = data.get("relevance"), data.get("is_study")
    # Strict on purpose: bool("false") is True and a stray 5 would outrank every real 3, so a loose reply is dropped, not guessed at.
    if isinstance(relevance, bool) or not isinstance(relevance, (int, float)):
        return None
    # Range first: float() of a huge int would raise OverflowError.
    if not 1 <= relevance <= 3 or not float(relevance).is_integer():
        return None
    if not isinstance(is_study, bool):
        return None
    return {"relevance": int(relevance), "reason": str(data.get("reason", "")), "is_study": is_study}


def is_eligible(work: dict) -> bool:
    return bool(
        not work.get("is_retracted") and work.get("tier") != "metadata"
        and work.get("triage") and work["triage"].get("is_study")
    )


def rank_key(work: dict) -> tuple:
    return (-work["triage"]["relevance"], -(work.get("similarity") or 0.0))


def select_for_cards(works: list[dict], *, n: int = 10) -> list[dict]:
    # sorted() is stable, so equal scores keep input order and the pick is deterministic.
    return sorted((w for w in works if is_eligible(w)), key=rank_key)[:n]
