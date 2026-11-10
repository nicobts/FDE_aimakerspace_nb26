"""The server.

`gradio.Server` is a FastAPI app with Gradio's API engine bolted in. You get
queueing, streaming, and MCP for free, but you bring your own frontend. That
split is the point: the API is the product, the UI is disposable.
"""

import os
import tomllib
from pathlib import Path

from fastapi.responses import HTMLResponse
from gradio import Server

import guardrails
from card import build_card_prompt, parse_card
from guardrails import BUDGET, check_lengths
from llm import stream_reply
from schema import CorpusAnswer, Request, Response

app = Server()

FRONTEND = Path(__file__).parent / "frontend" / "index.html"
_PYPROJECT = Path(__file__).parent / "pyproject.toml"
VERSION = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]


# --- The API -----------------------------------------------------------------
# The `-> str` return annotation is REQUIRED. Without it Gradio infers zero
# output components and silently returns nothing. Ask us how we know.
#
# Both endpoints share one concurrency slot ("llm"), so at most LLM_CONCURRENCY model calls run at
# once and the rest queue; time_limit ends a request Gradio has been running too long.
LIMITS = {"concurrency_id": "llm", "concurrency_limit": guardrails.LLM_CONCURRENCY,
          "time_limit": guardrails.LLM_TIMEOUT + 30}


@app.api(name="summarize_research_paper", **LIMITS)
def summarize_research_paper(
    document_text: str,
    title: str | None = None,
    source: str | None = None,
    focus: str | None = None,
    output_languages: list[str] | None = None,
) -> str:
    """Turn the text of one coffee research paper or abstract into an article card.

    Returns JSON with a category, a relevance score from 1 to 3, the key facts,
    a summary and reader notes in English and/or Italian, and a trust level with
    the warning signs found. Returns needs_human=true with a reason, and no
    card, when the text is not a study, is too short to judge, or is not about
    coffee. Use it for one document at a time; it does not search for papers.
    The text is limited to 80,000 characters (a long paper), and title, source and
    focus to 500 each; longer input is declined with the reason.
    """
    # Checked before any model call, so a refused request costs nothing.
    refused = check_lengths({
        "document_text": (document_text, guardrails.MAX_DOCUMENT_CHARS),
        "title": (title, guardrails.MAX_FIELD_CHARS),
        "source": (source, guardrails.MAX_FIELD_CHARS),
        "focus": (focus, guardrails.MAX_FIELD_CHARS),
    }) or BUDGET.take()
    if refused:
        yield Response(needs_human=True, needs_human_reason=f"Not sent to the model: {refused}.").model_dump_json(indent=2)
        return
    request = Request(
        document_text=document_text,
        title=title,
        source=source,
        focus=focus,
        output_languages=output_languages or ["en", "it"],
    )
    raw = ""
    for raw in stream_reply(build_card_prompt(request)):
        yield raw
    # The last value replaces the raw stream with the validated card.
    yield parse_card(raw, request).model_dump_json(indent=2)


@app.api(name="ask_research_corpus", **LIMITS)
def ask_research_corpus(question: str, k: int = 5) -> str:
    """Answer a question about published coffee research from the team's paper corpus, with sources.

    The corpus holds about 2,400 open-access papers since 2024 on roasting, processing,
    agronomy, extraction, packaging, sensory, health, sustainability, IoT/digital and
    by-product innovation. Ask in English or Italian; the answer comes back in the same
    language. Returns JSON: answer (citing works as [W<id>]), sources (the OpenAlex ids
    the answer is grounded in), retrieved (every id the model was shown), and
    needs_human=true with a reason, and no answer, when the papers do not answer the
    question. The company's own products, blends and lab data are never in the corpus,
    so questions about them are declined. k is how many passages the model reads (1-8).
    Use summarize_research_paper instead to card one document you already have.
    """
    from qa import answer_question

    # A research question fits in a few sentences; a longer input is a pasted document or abuse,
    # and every character is paid for in the embedding call.
    refused = check_lengths({"question": (question, guardrails.MAX_QUESTION_CHARS)})
    if refused:
        refused += "; ask a shorter question, or use summarize_research_paper for a whole document"
    refused = refused or BUDGET.take()
    if refused:
        return CorpusAnswer(needs_human=True, needs_human_reason=f"Not sent to the model: {refused}.").model_dump_json(indent=2)
    return answer_question(question, k=max(1, min(k, 8))).model_dump_json(indent=2)


@app.api(name="ask_research_corpus_agent", **LIMITS)
def ask_research_corpus_agent(question: str, k: int = 5) -> str:
    """Answer a multi-part question about published coffee research by splitting it into focused sub-questions.

    The second implementation of ask_research_corpus (Week 5): an outer model sends each part of the
    question through the same search-and-answer pipeline and combines the cited answers. Same corpus,
    same JSON contract (answer, sources, retrieved, needs_human with a reason), same declines. It
    costs at least three model calls where ask_research_corpus costs one, so use ask_research_corpus
    for a single question and this one only when the question has several distinct parts.
    """
    from agent import answer_with_subagent

    refused = check_lengths({"question": (question, guardrails.MAX_QUESTION_CHARS)})
    # One unit of the call budget per request; the fan-out inside it is capped in agent.py
    # (MAX_ROUNDS outer calls, MAX_SUBQUESTIONS pipeline runs), so a request has a known ceiling.
    refused = refused or BUDGET.take()
    if refused:
        return CorpusAnswer(needs_human=True, needs_human_reason=f"Not sent to the model: {refused}.").model_dump_json(indent=2)
    return answer_with_subagent(question, k=max(1, min(k, 8))).model_dump_json(indent=2)


# --- The frontend ------------------------------------------------------------
# Defining a route at "/" replaces Gradio's default UI with ours.


@app.get("/", response_class=HTMLResponse)
def homepage() -> str:
    return FRONTEND.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    """Your future ops team will thank you. Load balancers need this."""
    return {"status": "ok", "model": os.getenv("LLM_MODEL", "gpt-4.1-mini")}


@app.get("/version")
def version() -> dict:
    return {"version": VERSION}


if __name__ == "__main__":
    # 0.0.0.0 so the container is reachable from the host. On your laptop this
    # is fine. On a firm network, "reachable from where, exactly?" is the
    # question this challenge wants you to go ask.
    #
    # Read the port rather than hardcoding it, so a machine that already has
    # something on 7860 can move this one without editing code.
    port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))

    # Gradio announces the address it BOUND to, which is 0.0.0.0 -- not an
    # address a browser can open. Windows rejects it outright; macOS and Linux
    # quietly redirect it to localhost, which is why it looks fine on some
    # machines and broken on others. Print the one that always works.
    print(f"\n  Open http://localhost:{port} in your browser\n", flush=True)
    app.launch(server_name="0.0.0.0", server_port=port)
