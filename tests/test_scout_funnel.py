from scout_support import add_scout_paths
add_scout_paths()
import numpy as np  # noqa: E402
from scout import funnel  # noqa: E402


class FakeEmbedder:
    def embed(self, texts):
        vecs = {"focus": [1, 0], "A\nnear": [0.9, 0.1], "B\nfar": [0, 1]}
        return np.array([vecs[t] for t in texts], dtype="float32") / np.linalg.norm([vecs[t] for t in texts], axis=1, keepdims=True)


def test_similarity_to_focus_ranks_near_above_far():
    sims = funnel.similarity_to_focus(FakeEmbedder(), [{"id": "W1", "title": "A", "abstract": "near"}, {"id": "W2", "title": "B", "abstract": "far"}], focus="focus")
    assert sims["W1"] > sims["W2"] and 0.0 <= sims["W2"] <= 1.0


def test_triage_parses_json_and_returns_none_on_garbage():
    good = funnel.triage_work(None, {"id": "W1", "title": "t", "abstract": "a"}, focus="f", chat=lambda c, p, **k: '{"relevance": 3, "reason": "r", "is_study": true}')
    assert good == {"relevance": 3, "reason": "r", "is_study": True}
    assert funnel.triage_work(None, {"id": "W1", "title": "t", "abstract": "a"}, focus="f", chat=lambda c, p, **k: "sorry") is None
    assert funnel.triage_work(None, {"id": "W1", "title": "t", "abstract": "a"}, focus="f", chat=lambda c, p, **k: '{"reason": "no relevance key"}') is None


def test_select_for_cards_orders_and_excludes():
    rows = [
        {"id": "W1", "tier": "abstract", "is_retracted": False, "similarity": 0.5, "triage": {"relevance": 3, "is_study": True}},
        {"id": "W2", "tier": "abstract", "is_retracted": False, "similarity": 0.9, "triage": {"relevance": 2, "is_study": True}},
        {"id": "W3", "tier": "abstract", "is_retracted": True,  "similarity": 0.9, "triage": {"relevance": 3, "is_study": True}},
        {"id": "W4", "tier": "metadata", "is_retracted": False, "similarity": 0.9, "triage": None},
        {"id": "W5", "tier": "pdf", "is_retracted": False, "similarity": 0.7, "triage": {"relevance": 3, "is_study": False}},
        {"id": "W6", "tier": "pdf", "is_retracted": False, "similarity": 0.6, "triage": None},
    ]
    assert [w["id"] for w in funnel.select_for_cards(rows, n=10)] == ["W1", "W2"]
    assert [w["id"] for w in funnel.select_for_cards(rows, n=1)] == ["W1"]


def _triage(reply):
    return funnel.triage_work(None, {"id": "W1", "title": "t", "abstract": "a"}, focus="f", chat=lambda c, p, **k: reply)


def test_triage_requires_a_real_bool_for_is_study():
    assert _triage('{"relevance": 3, "reason": "r", "is_study": "false"}') is None
    assert _triage('{"relevance": 3, "reason": "r", "is_study": "no"}') is None
    assert _triage('{"relevance": 3, "reason": "r"}') is None


def test_triage_requires_an_integer_relevance_in_range():
    for bad in ("5", "0", "-1", "2.7", "true", '"high"', "Infinity", "NaN", "1" + "0" * 400):
        assert _triage('{"relevance": %s, "reason": "r", "is_study": true}' % bad) is None
    assert _triage('{"relevance": 3.0, "reason": "r", "is_study": true}')["relevance"] == 3


def test_similarity_of_no_works_is_empty_without_embedding():
    class Boom:
        def embed(self, texts):
            raise AssertionError("embed must not be called")

    assert funnel.similarity_to_focus(Boom(), [], focus="focus") == {}


def test_a_missing_title_never_becomes_the_string_none():
    from scout import funnel
    assert funnel._text({"title": None, "abstract": "abs"}) == "abs"
    assert funnel._text({"title": "T", "abstract": None}) == "T"
    seen = []
    funnel.triage_work(None, {"title": None, "abstract": "a"}, focus="f", chat=lambda c, p, **k: seen.append(p) or "{}")
    assert "None" not in seen[0]
