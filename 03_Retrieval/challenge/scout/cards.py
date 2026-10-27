"""The funnel's card step: one OpenAlex work in, one article card out."""

from card import build_card_prompt, parse_card
from schema import Request, Response

import helpers.llm


def card_work(
    cfg,
    work: dict,
    *,
    focus: str | None,
    languages: list[str],
    text: str | None = None,
    model: str | None = None,
    stats: helpers.llm.CallStats | None = None,
    chat=helpers.llm.chat,
) -> Response:
    request = Request(
        document_text=text or work["abstract"],
        title=work["title"],
        source=work.get("source"),
        focus=focus,
        output_languages=languages,
    )
    # Only forward what was set, so an injected chat need not accept either.
    kwargs = {k: v for k, v in (("model", model), ("stats", stats)) if v is not None}
    card = parse_card(chat(cfg, build_card_prompt(request), **kwargs), request)
    # A decline has no card to qualify; an abstract-only card is thinner evidence than a full-text one.
    if text is None and not card.needs_human and "abstract_only" not in card.trust_warnings:
        card.trust_warnings.append("abstract_only")
    return card
