from scout_support import add_scout_paths
add_scout_paths()
import pytest  # noqa: E402
from scout import pipeline  # noqa: E402
from scout.store import Store  # noqa: E402


def fake_search(ids_by_query):
    calls = []
    def search(*, query, from_date, **kw):
        calls.append((query, from_date))
        return [{"id": i, "doi": None, "title": i, "year": 2025, "publication_date": "2025-01-01", "type": "article", "source": None,
                 "cited_by_count": 0, "is_retracted": False, "institutions": [], "is_oa": False, "oa_status": None,
                 "pdf_url": None, "landing_url": None, "abstract": "a" if i != "W9" else None, "language": "en"} for i in ids_by_query[query]]
    return search, calls


def test_seed_tiers_everything_and_records_run(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    search, calls = fake_search({"roasting-q": ["W1", "W9"], "health-q": ["W1", "W2"]})
    counts = pipeline.seed(s, areas=["roasting", "health"], from_date="2024-01-01", per_area=300, today="2026-10-27", search=search,
                           queries={"roasting": "roasting-q", "health": "health-q"})
    assert counts["new"] == 3 and counts["metadata"] == 1 and counts["abstract"] == 2
    assert s.works(ids=["W1"])[0]["areas"] == ["roasting", "health"]
    assert s.last_run(kind="seed")["counts"]["new"] == 3


def test_update_requires_seed(tmp_path):
    with pytest.raises(ValueError, match="seed"):
        pipeline.update(Store(tmp_path / "s.sqlite"), areas=["roasting"], per_area=300, today="2026-11-30", search=lambda **k: [])


def test_update_uses_overlap_and_adds_only_new(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    search, calls = fake_search({"roasting-q": ["W1", "W2"]})
    pipeline.seed(s, areas=["roasting"], from_date="2024-01-01", per_area=300, today="2026-10-27", search=search, queries={"roasting": "roasting-q"})
    search2, calls2 = fake_search({"roasting-q": ["W2", "W3"]})
    counts = pipeline.update(s, areas=["roasting"], per_area=300, today="2027-01-15", search=search2, queries={"roasting": "roasting-q"})
    assert calls2[0][1] == "2026-07-29" and counts["new"] == 1
    assert s.works(ids=["W3"])[0]["first_seen"] == "2027-01-15"


def test_screen_cards_top_n_and_keeps_unparsed_triage(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    search, _ = fake_search({"q": ["W1", "W2", "W3"]})
    pipeline.seed(s, areas=["roasting"], from_date="2024-01-01", per_area=300, today="2026-10-27", search=search, queries={"roasting": "q"})
    class E:
        def embed(self, texts):
            import numpy as np
            return np.eye(len(texts), 3, dtype="float32") if len(texts) > 1 else np.array([[1, 0, 0]], dtype="float32")
    replies = iter(['{"relevance": 3, "reason": "r", "is_study": true}', 'garbage', '{"relevance": 1, "reason": "r", "is_study": true}',
                    '{"needs_human": false, "category": "roasting", "relevance": 3, "study_type": "x", "sample_size": null, "main_finding": "f", "summary_en": "s", "summary_it": "r", "notes_en": null, "notes_it": null, "affiliation": "unknown", "trust_level": "medium", "trust_warnings": []}'])
    out = pipeline.screen(s, None, E(), area="roasting", focus="focus", n=1, floor=0.0, today="2026-10-27", chat=lambda c, p, **k: next(replies))
    assert out["carded"] == ["W1"] and s.latest_card("W1")["version"] == 1
    assert [r["id"] for r in out["ranked"]][:1] == ["W1"] and any(r["triage"] is None for r in out["ranked"])
