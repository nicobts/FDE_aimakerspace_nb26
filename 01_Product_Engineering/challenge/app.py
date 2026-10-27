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

from card import build_card_prompt, parse_card
from llm import stream_reply
from schema import Request

app = Server()

FRONTEND = Path(__file__).parent / "frontend" / "index.html"
_PYPROJECT = Path(__file__).parent / "pyproject.toml"
VERSION = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]


# --- The API -----------------------------------------------------------------
# The `-> str` return annotation is REQUIRED. Without it Gradio infers zero
# output components and silently returns nothing. Ask us how we know.


@app.api(name="summarize_research_paper")
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
    """
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
