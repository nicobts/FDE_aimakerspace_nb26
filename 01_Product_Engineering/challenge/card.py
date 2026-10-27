"""The article card: one prompt and one parser, shared by the app and the scout."""

import json

from schema import Request, Response

CARD_INSTRUCTIONS = """You turn one scientific publication about coffee into an article card for an R&D researcher.

Reply with one JSON object and nothing else. It must match this JSON schema:
{schema}

Rules:
- Set needs_human to true, give needs_human_reason, and leave every other field null when the text is not a study or review, is too short to judge, or is not about coffee.
- Use only what the text states. Leave sample_size null when no number is given; never estimate one.
- category, study_type, main_finding, trust_level and trust_warnings are always in English.
- Write summary_* and notes_* only for these languages: {languages}. Leave the others null.
- relevance: 1 = background, 2 = worth reading, 3 = act on it. Judge it against the reader's focus when one is given.
- A weak study still gets a card: lower trust_level and list the trust_warnings that explain it.

Title: {title}
Source: {source}
Reader's focus: {focus}

Publication text:
{document_text}
"""


def build_card_prompt(request: Request) -> str:
    return CARD_INSTRUCTIONS.format(
        schema=json.dumps(Response.model_json_schema()),
        languages=", ".join(request.output_languages),
        title=request.title or "not given",
        source=request.source or "not given",
        focus=request.focus or "not given",
        document_text=request.document_text,
    )


def parse_card(raw: str, request: Request) -> Response:
    # Models often wrap JSON in a code fence or a sentence; keep only the object.
    start, end = raw.find("{"), raw.rfind("}")
    try:
        card = Response.model_validate_json(raw[start : end + 1])
    except ValueError:
        # An answer that breaks the contract is a decline, not a half-filled card.
        return Response(
            needs_human=True,
            needs_human_reason="The model's answer did not match the contract; "
            "a researcher should read this document.",
        )
    if "en" not in request.output_languages:
        card.summary_en = card.notes_en = None
    if "it" not in request.output_languages:
        card.summary_it = card.notes_it = None
    return card
