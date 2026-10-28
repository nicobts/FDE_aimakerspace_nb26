from scout_support import work, add_scout_paths
add_scout_paths()
from scout import views  # noqa: E402
from scout.store import Store  # noqa: E402


def seeded(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, abstract="English abstract"), work(2, abstract=None)], area="roasting", first_seen="2026-10-27")
    s.set_tier("W1", tier="pdf"); s.set_tier("W2", tier="metadata")
    s.add_card("W1", card={"needs_human": False, "summary_en": "sum en", "summary_it": "riassunto", "notes_it": "note", "main_finding": "mf",
                           "trust_level": "medium", "trust_warnings": ["abstract_only"], "relevance": 2}, schema_version="0.1.0", model="m", tier="abstract", cost_usd=0)
    s.set_fulltext("W1", markdown="# Paper\n\n" + "body " * 400, source_url="u")
    return s


def test_chunks_carry_provenance_and_language(tmp_path):
    chunks = views.build_chunks(seeded(tmp_path))
    by_work = {}
    for c in chunks: by_work.setdefault(c["work_id"], []).append(c)
    assert "W2" not in by_work                                   # metadata tier has no text
    langs = {c["language"] for c in by_work["W1"]}
    assert langs == {"en", "it"} and all(c["source"] == "W1" and c["tier"] == "pdf" for c in by_work["W1"])
    assert any("riassunto" in c["text"] for c in by_work["W1"]) and any("body" in c["text"] for c in by_work["W1"])
    assert len(views.build_chunks(seeded(tmp_path), include_fulltext=False)) < len(chunks)


def test_chunk_ids_count_from_zero_in_the_documented_order(tmp_path):
    chunks = views.build_chunks(seeded(tmp_path))
    assert [c["id"] for c in chunks[:3]] == ["W1#0", "W1#1", "W1#2"]
    assert chunks[0]["text"] == "t1\n\nEnglish abstract" and chunks[0]["language"] == "en"
    assert chunks[1]["language"] == "it" and chunks[1]["text"] == "riassunto\n\nnote"
    assert "mf" in chunks[2]["text"] and "medium" in chunks[2]["text"] and "abstract_only" in chunks[2]["text"]
    assert set(chunks[0]) == {"id", "source", "work_id", "tier", "language", "publication_date", "first_seen", "areas", "text"}


def test_declined_card_adds_no_card_chunks(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, abstract="abs")], area="roasting", first_seen="2026-10-27")
    s.add_card("W1", card={"needs_human": True, "needs_human_reason": "unreadable"}, schema_version="0.1.0", model="m", tier="abstract", cost_usd=0)
    assert [c["id"] for c in views.build_chunks(s)] == ["W1#0"]


def test_wiki_pages_named_by_id_with_fixed_headings(tmp_path):
    n = views.render_wiki(seeded(tmp_path), directory=tmp_path / "wiki")
    assert n == 2 and (tmp_path / "wiki" / "W1.md").exists() and (tmp_path / "wiki" / "W2.md").exists()
    page = (tmp_path / "wiki" / "W1.md").read_text(encoding="utf-8")
    for h in ("## Metadata", "## Abstract", "## Card", "## Trust", "## Full text"): assert h in page
    assert "## Full text" not in (tmp_path / "wiki" / "W2.md").read_text(encoding="utf-8")
    index = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "index_roasting.md" in index and "W1" in (tmp_path / "wiki" / "index_roasting.md").read_text(encoding="utf-8")


def test_wiki_page_without_card_or_abstract_says_so_and_stale_pages_go(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "W999.md").write_text("old", encoding="utf-8")
    views.render_wiki(seeded(tmp_path), directory=wiki)
    assert not (wiki / "W999.md").exists()
    page = (wiki / "W2.md").read_text(encoding="utf-8")
    assert "No abstract available." in page and "No card yet." in page and "Not assessed." in page
    w1 = (wiki / "W1.md").read_text(encoding="utf-8")
    assert "### Italiano" in w1 and "riassunto" in w1 and "abstract_only" in w1


def test_area_index_sorts_newest_first_with_undated_last(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, publication_date="2024-01-01"), work(2, publication_date=None), work(3, publication_date="2025-06-01")],
                   area="roasting", first_seen="2026-10-27")
    views.render_wiki(s, directory=tmp_path / "wiki")
    text = (tmp_path / "wiki" / "index_roasting.md").read_text(encoding="utf-8")
    assert text.index("W3") < text.index("W1") < text.index("W2")


def test_export_jsonl_one_line_per_work(tmp_path):
    assert views.export_jsonl(seeded(tmp_path), path=tmp_path / "c.jsonl") == 2
    assert len((tmp_path / "c.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_vector_store_roundtrip(tmp_path):
    import numpy as np
    class E:
        def embed(self, texts): return np.eye(len(texts), 4, dtype="float32")
    chunks = views.build_chunks(seeded(tmp_path), include_fulltext=False)
    store = views.build_vector_store(chunks, E(), path=tmp_path / "index" / "chunks")
    assert len(store) == len(chunks) and (tmp_path / "index" / "chunks.npy").exists()
    hit = store.search(np.eye(1, 4, dtype="float32")[0], k=1, where={"language": "it"})[0]
    assert hit.metadata["language"] == "it"


def test_empty_chunk_list_saves_an_empty_store_without_embedding(tmp_path):
    class E:
        def embed(self, texts): raise AssertionError("must not embed")
    store = views.build_vector_store([], E(), path=tmp_path / "index" / "chunks")
    assert len(store) == 0 and (tmp_path / "index" / "chunks.jsonl").exists()


def test_untitled_work_never_renders_the_string_none(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, title=None, abstract="only abstract")], area="roasting", first_seen="2026-10-27")
    s.set_tier("W1", tier="abstract")
    assert views.build_chunks(s)[0]["text"] == "only abstract"
    views.render_wiki(s, directory=tmp_path / "wiki")
    assert (tmp_path / "wiki" / "W1.md").read_text(encoding="utf-8").startswith("# (untitled)\n")
    row = [l for l in (tmp_path / "wiki" / "index_roasting.md").read_text(encoding="utf-8").splitlines() if "W1" in l][0]
    assert "(untitled)" in row and "None" not in row


def test_index_cell_escapes_pipes_and_collapses_line_breaks(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, title="a | b\r\nc\n\nd")], area="roasting", first_seen="2026-10-27")
    views.render_wiki(s, directory=tmp_path / "wiki")
    row = [l for l in (tmp_path / "wiki" / "index_roasting.md").read_text(encoding="utf-8").split("\n") if "W1" in l][0]
    assert r"a \| b c d" in row and "\r" not in row
