from scout_support import add_scout_paths
add_scout_paths()
from schema import Request, Response  # noqa: E402
import card  # noqa: E402
from scout import cards  # noqa: E402


def test_parse_card_declines_on_garbage():
    out = card.parse_card("not json at all", Request(document_text="x"))
    assert out.needs_human is True and out.category is None


def test_build_card_prompt_mentions_focus_and_schema():
    p = card.build_card_prompt(Request(document_text="body", focus="acrylamide"))
    assert "acrylamide" in p and '"needs_human"' in p


GOOD = '{"needs_human": false, "category": "roasting", "relevance": 2, "study_type": "lab experiment", "sample_size": null, "main_finding": "f", "summary_en": "s", "summary_it": "r", "notes_en": null, "notes_it": null, "affiliation": "unknown", "trust_level": "medium", "trust_warnings": []}'


def test_card_work_from_abstract_adds_abstract_only_warning():
    work = {"id": "W1", "title": "t", "source": "J", "abstract": "abs", "tier": "abstract"}
    out = cards.card_work(None, work, focus=None, languages=["en", "it"], chat=lambda cfg, prompt, **kw: GOOD)
    assert isinstance(out, Response) and "abstract_only" in out.trust_warnings


def test_card_work_from_fulltext_keeps_warnings_as_returned():
    work = {"id": "W1", "title": "t", "source": "J", "abstract": "abs", "tier": "pdf"}
    seen = {}

    def chat(cfg, prompt, **kw):
        seen["prompt"] = prompt
        return GOOD

    out = cards.card_work(None, work, focus="x", languages=["en"], text="full text here", chat=chat)
    assert "full text here" in seen["prompt"] and "abstract_only" not in out.trust_warnings
