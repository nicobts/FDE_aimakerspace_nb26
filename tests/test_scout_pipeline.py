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
    assert out["carded"] == ["W1"] and s.latest_card("W1")["version"] == 1 and s.latest_card("W1")["tier"] == "abstract"
    assert [r["id"] for r in out["ranked"]][:1] == ["W1"] and any(r["triage"] is None for r in out["ranked"])


CARD = ('{"needs_human": false, "category": "roasting", "relevance": 3, "study_type": "x", "sample_size": null, "main_finding": "f", '
        '"summary_en": "s", "summary_it": "r", "notes_en": null, "notes_it": null, "affiliation": "unknown", "trust_level": "medium", "trust_warnings": []}')
STUDY = '{"relevance": %d, "reason": "r", "is_study": %s}'


def _seeded(tmp_path, ids):
    s = Store(tmp_path / "s.sqlite")
    search, _ = fake_search({"q": ids})
    pipeline.seed(s, areas=["roasting"], from_date="2024-01-01", per_area=300, today="2026-10-27", search=search, queries={"roasting": "q"})
    return s


class SimEmbedder:
    """Focus embeds to [1, 0]; the works embed to unit vectors whose cosine with it is the given similarity."""
    def __init__(self, sims):
        self.sims = sims

    def embed(self, texts):
        import numpy as np
        if len(texts) == 1:
            return np.array([[1, 0]], dtype="float32")
        return np.array([[s, (1 - s * s) ** 0.5] for s in self.sims], dtype="float32")


def test_seed_counts_by_area(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    search, _ = fake_search({"roasting-q": ["W1", "W9"], "health-q": ["W1", "W2"]})
    counts = pipeline.seed(s, areas=["roasting", "health"], from_date="2024-01-01", per_area=300, today="2026-10-27", search=search,
                           queries={"roasting": "roasting-q", "health": "health-q"})
    assert counts["by_area"] == {"roasting": {"fetched": 2, "new": 2, "metadata": 1, "abstract": 1, "pdf": 0},
                                 "health": {"fetched": 2, "new": 1, "metadata": 0, "abstract": 2, "pdf": 0}}


def test_reseed_keeps_an_existing_tier(tmp_path):
    s = _seeded(tmp_path, ["W1", "W2"])
    s.set_tier("W1", tier="pdf")
    search, _ = fake_search({"q": ["W1", "W2"]})
    counts = pipeline.seed(s, areas=["roasting"], from_date="2024-01-01", per_area=300, today="2026-11-01", search=search, queries={"roasting": "q"})
    assert s.works(ids=["W1"])[0]["tier"] == "pdf" and counts["new"] == 0 and counts["pdf"] == 1 and counts["abstract"] == 1


def test_update_starts_from_the_later_of_seed_and_update(tmp_path):
    s = _seeded(tmp_path, ["W1"])
    search, _ = fake_search({"q": ["W1"]})
    pipeline.update(s, areas=["roasting"], per_area=300, today="2027-01-15", search=search, queries={"roasting": "q"})
    search3, calls3 = fake_search({"q": ["W1"]})
    pipeline.update(s, areas=["roasting"], per_area=300, today="2027-02-01", search=search3, queries={"roasting": "q"})
    assert calls3[0][1] == "2026-10-17"
    assert s.last_run(kind="update")["params"]["from_date"] == "2026-10-17"


def test_screen_floor_skips_triage_but_keeps_similarity(tmp_path):
    s = _seeded(tmp_path, ["W1", "W2", "W3"])
    calls = []
    replies = iter([STUDY % (3, "true"), CARD])
    def chat(c, p, **k):
        calls.append(p)
        return next(replies)
    out = pipeline.screen(s, None, SimEmbedder([0.9, 0.1, 0.2]), area="roasting", focus="f", n=1, floor=0.5, today="2026-10-27", chat=chat)
    assert len(calls) == 2 and [r["id"] for r in out["ranked"]] == ["W1"] and out["carded"] == ["W1"]
    below = s.works(ids=["W2"])[0]
    assert below["triage"] is None and below["similarity"] == pytest.approx(0.1)


def test_screen_ranks_every_row_by_relevance_then_similarity(tmp_path):
    s = _seeded(tmp_path, ["W1", "W2", "W3", "W4"])
    replies = iter([STUDY % (1, "true"), STUDY % (3, "true"), STUDY % (3, "true"), STUDY % (3, "false"), CARD])
    out = pipeline.screen(s, None, SimEmbedder([0.2, 0.5, 0.9, 0.8]), area="roasting", focus="f", n=1, floor=0.0,
                          today="2026-10-27", chat=lambda c, p, **k: next(replies))
    # W3 beats W2 on similarity, W1 trails on relevance, and W4 is not a study so it comes last despite its similarity.
    assert [r["id"] for r in out["ranked"]] == ["W3", "W2", "W1", "W4"] and out["carded"] == ["W3"]


def _token_chat(replies):
    def chat(c, p, **k):
        k["stats"].prompt_tokens += 100
        k["stats"].completion_tokens += 50
        return next(replies)
    return chat


def test_screen_run_row_prices_tokens_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv("CARD_PRICE_IN", "0.001")
    monkeypatch.setenv("CARD_PRICE_OUT", "0.002")
    s = _seeded(tmp_path, ["W1", "W2"])
    replies = iter([STUDY % (3, "true"), STUDY % (2, "true"), CARD])
    out = pipeline.screen(s, None, SimEmbedder([0.9, 0.8]), area="roasting", focus="f", n=1, floor=0.0, today="2026-10-27", chat=_token_chat(replies))
    run = s.last_run(kind="screen")
    assert out["tokens"] == 450 and run["tokens"] == 450
    assert out["cost_usd"] == pytest.approx(run["cost_usd"])
    assert run["cost_usd"] == pytest.approx(0.001 * 300 + 0.002 * 150)
    assert run["params"]["cost_known"] is True and run["params"]["area"] == "roasting" and run["params"]["n"] == 1
    assert s.latest_card("W1")["cost_usd"] == pytest.approx(0.001 * 100 + 0.002 * 50)


def test_screen_run_row_marks_cost_unknown_without_prices(tmp_path, monkeypatch):
    monkeypatch.delenv("CARD_PRICE_IN", raising=False)
    monkeypatch.delenv("CARD_PRICE_OUT", raising=False)
    s = _seeded(tmp_path, ["W1"])
    replies = iter([STUDY % (3, "true"), CARD])
    out = pipeline.screen(s, None, SimEmbedder([0.9]), area="roasting", focus="f", n=1, floor=0.0, today="2026-10-27", chat=_token_chat(replies))
    assert out["cost_usd"] == 0.0 and s.last_run(kind="screen")["params"]["cost_known"] is False
    assert s.latest_card("W1")["cost_usd"] == 0.0


def test_screen_stores_the_contract_version_on_the_card(tmp_path):
    import tomllib
    s = _seeded(tmp_path, ["W1"])
    replies = iter([STUDY % (3, "true"), CARD])
    pipeline.screen(s, None, SimEmbedder([0.9]), area="roasting", focus="f", n=1, floor=0.0, today="2026-10-27", chat=lambda c, p, **k: next(replies))
    expected = tomllib.loads(pipeline._CONTRACT.read_text(encoding="utf-8"))["project"]["version"]
    assert s._db.execute("SELECT schema_version FROM cards WHERE work_id='W1'").fetchone()[0] == expected
