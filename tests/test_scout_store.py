from scout_support import work, add_scout_paths
add_scout_paths()
from scout.store import Store  # noqa: E402


def test_upsert_counts_new_only_and_accumulates_areas(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    assert s.upsert_works([work(1), work(2)], area="roasting", first_seen="2026-10-27") == 2
    assert s.upsert_works([work(2), work(3)], area="health", first_seen="2026-11-30") == 1
    w2 = s.works(ids=["W2"])[0]
    assert w2["areas"] == ["roasting", "health"] and w2["first_seen"] == "2026-10-27"


def test_works_filters(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, publication_date="2024-05-01"), work(2, publication_date="2026-09-15")], area="roasting", first_seen="2026-10-27")
    s.set_tier("W1", tier="metadata"); s.set_tier("W2", tier="abstract")
    assert [w["id"] for w in s.works(since_published="2026-01-01")] == ["W2"]
    assert [w["id"] for w in s.works(tier="metadata")] == ["W1"]
    assert s.works(area="health") == []


def test_cards_are_versioned(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1)], area="roasting", first_seen="2026-10-27")
    assert s.add_card("W1", card={"needs_human": False}, schema_version="0.1.0", model="m", tier="abstract", cost_usd=0.01) == 1
    assert s.add_card("W1", card={"needs_human": False, "x": 1}, schema_version="0.1.0", model="m", tier="pdf", cost_usd=0.02) == 2
    assert s.latest_card("W1")["card"] == {"needs_human": False, "x": 1}
    assert s.works(ids=["W1"])[0]["card"]["x"] == 1


def test_runs_and_fulltext(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    assert s.last_run(kind="seed") is None
    s.add_run(kind="seed", params={"from_date": "2024-01-01"}, counts={"new": 3}, tokens=0, cost_usd=0.0, ran_at="2026-10-27")
    assert s.last_run(kind="seed")["params"]["from_date"] == "2024-01-01"
    s.upsert_works([work(1)], area="roasting", first_seen="2026-10-27")
    s.set_fulltext("W1", markdown="# paper", source_url="https://x/y.pdf")
    assert s.fulltext("W1") == "# paper"
