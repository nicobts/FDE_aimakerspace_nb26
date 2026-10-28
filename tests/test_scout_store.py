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


def test_area_filter_matches_every_area_of_a_multi_area_work(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1), work(2)], area="roasting", first_seen="2026-10-27")
    s.upsert_works([work(2)], area="health", first_seen="2026-11-30")
    assert [w["id"] for w in s.works(area="roasting")] == ["W1", "W2"]
    assert [w["id"] for w in s.works(area="health")] == ["W2"]


def test_second_upsert_leaves_tier_triage_and_similarity_alone(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, title="original")], area="roasting", first_seen="2026-10-27")
    s.set_tier("W1", tier="abstract")
    s.set_triage("W1", triage={"relevant": True}, similarity=0.8)
    s.upsert_works([work(1, title="changed")], area="health", first_seen="2026-11-30")
    w = s.works(ids=["W1"])[0]
    assert (w["tier"], w["triage"], w["similarity"]) == ("abstract", {"relevant": True}, 0.8)
    assert w["title"] == "original" and w["first_seen"] == "2026-10-27"


def test_since_seen_is_inclusive(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1)], area="roasting", first_seen="2026-10-27")
    s.upsert_works([work(2)], area="roasting", first_seen="2026-11-30")
    assert [w["id"] for w in s.works(since_seen="2026-11-30")] == ["W2"]
    assert [w["id"] for w in s.works(since_seen="2026-10-27")] == ["W1", "W2"]


def test_null_publication_date_is_excluded_by_since_published_only(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, publication_date=None), work(2)], area="roasting", first_seen="2026-10-27")
    assert [w["id"] for w in s.works(since_published="2000-01-01")] == ["W2"]
    assert [w["id"] for w in s.works()] == ["W1", "W2"]


def test_works_come_back_in_insertion_order(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(3), work(1)], area="roasting", first_seen="2026-10-27")
    s.upsert_works([work(2)], area="roasting", first_seen="2026-10-27")
    assert [w["id"] for w in s.works()] == ["W3", "W1", "W2"]
    assert [w["id"] for w in s.works(ids=["W2", "W3", "W1"])] == ["W3", "W1", "W2"]


def test_set_triage_round_trips_and_none_clears(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1)], area="roasting", first_seen="2026-10-27")
    w = s.works(ids=["W1"])[0]
    assert w["triage"] is None and w["similarity"] is None
    s.set_triage("W1", triage={"relevant": True, "why": "x"}, similarity=0.42)
    w = s.works(ids=["W1"])[0]
    assert w["triage"] == {"relevant": True, "why": "x"} and w["similarity"] == 0.42
    s.set_triage("W1", triage=None, similarity=None)
    w = s.works(ids=["W1"])[0]
    assert w["triage"] is None and w["similarity"] is None


def test_last_run_returns_the_newer_run_of_its_own_kind(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.add_run(kind="seed", params={}, counts={"new": 1}, tokens=0, cost_usd=0.0, ran_at="2026-10-27")
    s.add_run(kind="seed", params={}, counts={"new": 2}, tokens=0, cost_usd=0.0, ran_at="2026-11-30")
    s.add_run(kind="refresh", params={}, counts={"new": 9}, tokens=0, cost_usd=0.0, ran_at="2026-12-01")
    last = s.last_run(kind="seed")
    assert last["counts"] == {"new": 2} and last["ran_at"] == "2026-11-30"
    assert s.last_run(kind="refresh")["counts"] == {"new": 9}


def test_card_focus_round_trips_and_defaults_to_none(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1)], area="roasting", first_seen="2026-10-27")
    s.add_card("W1", card={}, schema_version="0.1.0", model="m", tier="abstract", cost_usd=0)
    assert s.latest_card("W1")["focus"] is None
    s.add_card("W1", card={}, schema_version="0.1.0", model="m", tier="pdf", cost_usd=0, focus="acrylamide")
    assert s.latest_card("W1")["focus"] == "acrylamide"


def test_a_database_without_the_focus_column_is_migrated(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE cards(work_id TEXT, version INTEGER, schema_version TEXT, model TEXT, tier TEXT,
                           cost_usd REAL, created_at TEXT, card TEXT, PRIMARY KEY(work_id, version));
        INSERT INTO cards VALUES('W1', 1, '0.1.0', 'm', 'abstract', 0, 'now', '{}');""")
    old.commit(); old.close()
    s = Store(path)
    assert s.latest_card("W1")["focus"] is None
    assert s.add_card("W1", card={}, schema_version="0.1.0", model="m", tier="pdf", cost_usd=0, focus="f") == 2
    Store(path)  # reopening a migrated database is a no-op
