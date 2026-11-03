import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("rank_bm25")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "01_Product_Engineering" / "challenge"))
import qa  # noqa: E402
import retrieval  # noqa: E402


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Three papers, one chunk each, with hand-made 2-d vectors so cosine is predictable."""
    (tmp_path / "index").mkdir()
    (tmp_path / "wiki").mkdir()
    rows = [
        {"id": "W1000001#0", "source": "W1000001", "text": "acrylamide forms during roasting of arabica coffee"},
        {"id": "W1000002#0", "source": "W1000002", "text": "ocratossina nella fermentazione della mucillagine e qualità"},
        {"id": "W1000003#0", "source": "W1000003", "text": "cold brew shelf life in the fridge"},
    ]
    (tmp_path / "index" / "chunks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    np.save(tmp_path / "index" / "chunks.npy", np.array([[1, 0], [0, 1], [0.6, 0.8]], dtype=np.float32))
    for r in rows:
        (tmp_path / "wiki" / f"{r['source']}.md").write_text(f"# Title {r['source']}\n\n## Abstract\n\n{r['text']}\n", encoding="utf-8")
    (tmp_path / "wiki" / "index.md").write_text("# Corpus index\n", encoding="utf-8")
    monkeypatch.setattr(retrieval, "DATA_DIR", tmp_path)
    retrieval.corpus.cache_clear()
    retrieval.embed_query.cache_clear()
    yield tmp_path
    # embed_query may be monkeypatched at this point; monkeypatch restores it afterwards.
    retrieval.corpus.cache_clear()


def fake_query_vector(monkeypatch, vector):
    monkeypatch.setattr(retrieval, "embed_query", lambda q: np.asarray(vector, dtype=np.float32))


def test_tokenize_keeps_italian_words_whole():
    assert retrieval.tokenize("Qualità dell'ocratossina") == ["qualità", "dell", "ocratossina"]


def test_bm25_finds_exact_term(corpus):
    assert retrieval.search("acrylamide", k=1, technique="bm25")[0]["source"] == "W1000001"


def test_hybrid_fuses_ranks_so_both_parents_agreeing_wins(corpus, monkeypatch):
    # BM25 prefers W1000003 (shelf life), dense prefers W1000003 second and W1000002 first;
    # RRF puts the paper both rankers place high above one only dense likes.
    fake_query_vector(monkeypatch, [0, 1])
    order = [hit["source"] for hit in retrieval.search("cold brew shelf life", k=3, technique="hybrid")]
    assert order[0] == "W1000003"


def test_read_page_accepts_md_suffix_and_rejects_unknown(corpus):
    assert retrieval.read_page("W1000002.md").startswith("# Title W1000002")
    assert "unknown page" in retrieval.read_page("W9")


def test_endpoint_declines_below_gate_without_calling_the_model(corpus, monkeypatch):
    fake_query_vector(monkeypatch, [-1, 0])  # cosine <= 0 with every stored vector
    monkeypatch.setattr(qa, "_complete", lambda messages: pytest.fail("model must not be called"))
    out = qa.answer_question("How do I reset my VPN password?", k=2)
    assert out.needs_human and out.answer is None and out.sources == []


def test_endpoint_turns_model_decline_into_needs_human(corpus, monkeypatch):
    fake_query_vector(monkeypatch, [1, 0])
    monkeypatch.setattr(qa, "_complete", lambda messages: "NOT IN CORPUS: no internal lab data")
    out = qa.answer_question("acrylamide in our own blends last quarter?", k=2)
    assert out.needs_human and out.needs_human_reason == "no internal lab data" and out.sources == []


def test_endpoint_sources_are_only_cited_ids_the_model_was_shown(corpus, monkeypatch):
    fake_query_vector(monkeypatch, [1, 0])
    monkeypatch.setattr(qa, "_complete", lambda messages: "Roasting forms it [W1000001]; also [W7777777].")
    out = qa.answer_question("acrylamide roasting", k=2)
    assert not out.needs_human
    assert out.sources == ["W1000001"]
    assert "W7777777" not in out.retrieved


def test_fake_completion_shape_is_what_litellm_returns(monkeypatch):
    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" ok "))])
    monkeypatch.setattr(qa, "completion", lambda **kw: reply)
    assert qa._complete([{"role": "user", "content": "x"}]) == "ok"
