"""Answer a researcher's question from the paper corpus, naming the papers it came from.

retrieve -> gate -> one model call -> parse the citations. Narrow with something cheap
(the ranker), read with something slow (the model), and the model only ever sees the top k.
"""

import json
import os
import re

from litellm import completion

import retrieval
from schema import CorpusAnswer

# Chosen by the TC3 comparison (03_Retrieval/challenge/results.md); change it there first.
TECHNIQUE = os.getenv("RETRIEVAL_TECHNIQUE", "hybrid")
# Labelled questions scored 0.69-0.85 at top 1, off-domain ones (VPN, capitals, revenue) 0.27-0.37,
# near-domain ones (tea, chocolate) 0.50-0.55: the gate drops only the clearly off-domain.
MIN_SIMILARITY = float(os.getenv("RETRIEVAL_MIN_SIMILARITY", "0.45"))
DECLINE = "NOT IN CORPUS:"

# The rules every way of answering shares (agent.py reuses them), so the ways differ only in how
# the model reaches the passages, not in what it is told to do with them.
RULES = (
    "Cite every claim with the work id in square brackets, "
    "for example [W4403193476]. When a question needs several papers, use and cite each of them. "
    f"If the passages do not answer the question, reply with one line that starts with '{DECLINE}' "
    "followed by the reason, and give no figures. The corpus holds published papers only, never the "
    "company's own products, blends, lab results or internal data, so a question about those is always "
    "declined. Write the answer, or the decline reason, in the language of the question (English or Italian), in at most 150 words."
)
SYSTEM = (
    "You answer questions from a coffee company's R&D researchers using only the passages below, "
    "which come from published research papers. " + RULES
)

CITATION = re.compile(r"W\d{6,}")


def model_kwargs() -> dict:
    kwargs = {"model": os.getenv("LLM_MODEL", "gpt-4.1-mini"), "timeout": 120,
              # Providers such as OpenRouter reserve credit for max_tokens; the answer is capped at 150 words anyway.
              "max_tokens": 800}
    if os.getenv("LLM_API_BASE"):
        kwargs["api_base"] = os.environ["LLM_API_BASE"]
    # Provider-specific knobs live in config, e.g. {"num_ctx": 32768, "think": false} for Ollama.
    kwargs.update(json.loads(os.getenv("LLM_OPTIONS") or "{}"))
    if os.getenv("LLM_EXTRA_HEADERS"):
        kwargs["extra_headers"] = json.loads(os.environ["LLM_EXTRA_HEADERS"])
    return kwargs


def _complete(messages: list[dict], *, meter=None) -> str:
    response = completion(**model_kwargs(), messages=messages)
    if meter:
        meter.track(response)
    return (response.choices[0].message.content or "").strip()


def _unique(ids):
    return list(dict.fromkeys(ids))


def to_answer(reply: str, retrieved: list[str]) -> CorpusAnswer:
    """The model's final text as the response contract: a decline, or an answer with grounded sources."""
    if reply.upper().startswith(DECLINE):
        return CorpusAnswer(needs_human=True, retrieved=retrieved, needs_human_reason=reply[len(DECLINE):].strip())
    # Only ids the model was actually shown count as sources; anything else it typed is not grounded.
    cited = [w for w in _unique(CITATION.findall(reply)) if w in retrieved]
    return CorpusAnswer(needs_human=False, answer=reply, sources=cited or retrieved, retrieved=retrieved)


# `search` is an argument so a measurement can hand in a counting version without patching anything.
def answer_question(question: str, *, k: int = 5, technique: str = TECHNIQUE,
                    search=retrieval.search, meter=None) -> CorpusAnswer:
    hits = search(question, k=k, technique=technique)
    retrieved = _unique(hit["source"] for hit in hits)

    # Retrieval always returns k rows, so "nothing matched" has to be decided here.
    # BM25 alone has no comparable score, so the gate needs the dense similarity.
    if technique != "bm25":
        best = retrieval.dense_rank(question, 1)
        if not best or best[0][1] < MIN_SIMILARITY:
            return CorpusAnswer(needs_human=True, retrieved=retrieved,
                                needs_human_reason=f"no passage is close enough to the question "
                                                   f"(best similarity {best[0][1] if best else 0:.2f} < {MIN_SIMILARITY})")

    reply = _complete([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Passages:\n\n{retrieval.format_hits(hits)}\n\nQuestion: {question}"},
    ], meter=meter)
    return to_answer(reply, retrieved)
