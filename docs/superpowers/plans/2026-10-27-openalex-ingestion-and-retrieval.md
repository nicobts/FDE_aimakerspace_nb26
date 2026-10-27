# OpenAlex Ingestion and Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch coffee research papers from OpenAlex once and incrementally, screen them cheaply, card the top ten per request into a SQLite corpus with derived wiki, chunks and vector store, so that Technical Challenge 3 can measure three retrieval techniques on real papers and ship a cited question endpoint.

**Architecture:** A `scout` package under `03_Retrieval/challenge/` runs from the root environment: an OpenAlex client, a SQLite store keyed by work id, a funnel (tier, embed, triage, card), and view builders (JSONL, chunks, wiki, vector store). The Week 1 card prompt moves into its own module so the funnel and the app share it. Retrieval techniques, the comparison, the labels and the endpoint are the student's graded work; this plan gives their shape and tests only.

**Tech Stack:** Python 3.14 venv via uv, stdlib `urllib` and `sqlite3`, `helpers.llm` / `helpers.embeddings` / `helpers.vectorstore` / `helpers.rag`, pydantic schema from Week 1, `rank-bm25` and `pandas` from the `week3` group, docling in a new opt-in `pdf` group, pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-openalex-ingestion-and-retrieval-design.md`

## Global Constraints

- No new dependency except `docling>=2.142` in an opt-in `pdf` dependency group in the root `pyproject.toml`; everything else stdlib or already present.
- Functions in new modules take their arguments keyword-only after the first positional, like `helpers/`. Comments explain why, not what.
- No AI attribution in commits, code or docs. Commit messages are plain imperative sentences, like `Fix typosquatted dependency in RAG prerequisites`.
- `use_case/data/` and `use_case/reference/` are gitignored and never committed. Tests use recorded fixtures under `tests/fixtures/` holding public OpenAlex metadata only.
- Tests use no network and no model: every external call is injected or stubbed, as in `tests/test_helpers.py`.
- OpenAlex requests never carry the user's personal email. The `mailto` parameter is sent only when `OPENALEX_MAILTO` is set.
- The record id everywhere is the OpenAlex work id, the `W…` string without the URL prefix.
- Tiers are exactly `metadata`, `abstract`, `pdf`. N = 10 cards per request. Seed: eight areas, articles from `2024-01-01`, 300 per area. Update overlap: 90 days.
- Instructor mode (`03_Retrieval/challenge/CLAUDE.md`): Tasks 9 to 13 are the student's. The assistant coaches, reviews and debugs; it does not write the labels, the retrieval code, the comparison, the endpoint, the decision rows, the Step 6 feedback or the Step 7 lines.
- The PDF tier (Task 8) has a two-hour timebox; past it, it ships as the stub described there.

## Review Focus

1. A work whose `abstract_inverted_index` is null: tier `metadata`, stored, listed, never carded, no exception. Test in Task 2.
2. The same work returned by two area queries: stored once with both areas recorded, `first_seen` from the first insert. Test in Task 3.
3. Triage reply that is not JSON or lacks `relevance`: the work stays in the list with triage null and is not selected for a card; the run continues. Test in Task 5.
4. `update` with no previous run: fails with a clear message to run `seed` first rather than fetching nothing silently. Test in Task 6.
5. An open-access URL that serves an HTML landing page: `fetch_pdf` returns None, the tier is downgraded to `abstract`, the abstract card stands. Test in Task 8.

---

## Part 1: ingestion and views (the assistant may implement)

### Task 1: OpenAlex client

**Files:**
- Create: `03_Retrieval/challenge/scout/__init__.py` (empty)
- Create: `03_Retrieval/challenge/scout/openalex.py`
- Create: `tests/fixtures/openalex/work_with_abstract.json`, `tests/fixtures/openalex/work_without_abstract.json`
- Test: `tests/test_scout_openalex.py`

**Interfaces:**
- Produces: `rebuild_abstract(inverted: dict[str, list[int]] | None) -> str | None`; `normalise_work(raw: dict) -> dict` returning keys `id, doi, title, year, publication_date, type, source, cited_by_count, is_retracted, institutions, is_oa, oa_status, pdf_url, landing_url, abstract, language`; `fetch_json(url: str, *, timeout: float = 30.0, retries: int = 3) -> dict`; `search_works(*, query: str, from_date: str, to_date: str | None = None, work_type: str = "article", max_works: int = 300, mailto: str | None = None, fetch=fetch_json) -> list[dict]` returning normalised works.

- [ ] **Step 1: Record two fixtures from the public API**

```bash
mkdir -p tests/fixtures/openalex
curl -s "https://api.openalex.org/works?search=coffee%20roasting&filter=has_abstract:true,is_oa:true,type:article&per-page=1" | python -I -c "import sys,json; json.dump(json.load(sys.stdin)['results'][0], open('tests/fixtures/openalex/work_with_abstract.json','w'), indent=1)"
curl -s "https://api.openalex.org/works?search=coffee%20roasting&filter=has_abstract:false,type:article&per-page=1" | python -I -c "import sys,json; json.dump(json.load(sys.stdin)['results'][0], open('tests/fixtures/openalex/work_without_abstract.json','w'), indent=1)"
```
Expected: two files, the first with a non-null `abstract_inverted_index` and `best_oa_location.pdf_url`, the second with `abstract_inverted_index: null`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_scout_openalex.py
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "03_Retrieval" / "challenge"))
from scout import openalex  # noqa: E402
FIX = ROOT / "tests" / "fixtures" / "openalex"

def test_rebuild_abstract_orders_words_by_position():
    assert openalex.rebuild_abstract({"roasting": [1], "Coffee": [0], "matters": [2]}) == "Coffee roasting matters"

def test_rebuild_abstract_none_stays_none():
    assert openalex.rebuild_abstract(None) is None

def test_normalise_work_strips_url_prefix_and_rebuilds_abstract():
    raw = json.loads((FIX / "work_with_abstract.json").read_text(encoding="utf-8"))
    work = openalex.normalise_work(raw)
    assert work["id"].startswith("W") and "openalex.org" not in work["id"]
    assert work["abstract"] and work["pdf_url"] and work["publication_date"]
    assert set(work) == {"id","doi","title","year","publication_date","type","source","cited_by_count","is_retracted","institutions","is_oa","oa_status","pdf_url","landing_url","abstract","language"}

def test_normalise_work_without_abstract():
    raw = json.loads((FIX / "work_without_abstract.json").read_text(encoding="utf-8"))
    assert openalex.normalise_work(raw)["abstract"] is None

def test_search_works_follows_cursor_and_stops_at_max():
    pages = {"*": {"meta": {"next_cursor": "c2"}, "results": [{"id": f"https://openalex.org/W{i}"} for i in range(200)]},
             "c2": {"meta": {"next_cursor": None}, "results": [{"id": f"https://openalex.org/W{i}"} for i in range(200, 400)]}}
    seen = []
    def fetch(url, **_):
        cursor = url.split("cursor=")[1].split("&")[0]
        seen.append(url)
        return pages[cursor]
    works = openalex.search_works(query="coffee", from_date="2024-01-01", max_works=250, fetch=fetch)
    assert len(works) == 250 and works[0]["id"] == "W0"
    assert "mailto" not in seen[0] and "from_publication_date:2024-01-01" in seen[0] and "type:article" in seen[0]

def test_search_works_sends_mailto_only_when_given():
    def fetch(url, **_):
        assert "mailto=team%40example.org" in url
        return {"meta": {"next_cursor": None}, "results": []}
    assert openalex.search_works(query="coffee", from_date="2024-01-01", mailto="team@example.org", fetch=fetch) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_openalex.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scout'`

- [ ] **Step 4: Implement `scout/openalex.py`**

`fetch_json` uses `urllib.request` with a `User-Agent` header and sleeps then retries on HTTP 429 and 5xx. `search_works` builds `https://api.openalex.org/works?search=<query>&filter=from_publication_date:<from>[,to_publication_date:<to>],type:<work_type>&per-page=200&cursor=<cursor>[&mailto=<mailto>]`, follows `meta.next_cursor`, stops at `max_works`, returns `normalise_work` of each result. `normalise_work` takes `source` from `primary_location.source.display_name`, `pdf_url` from `best_oa_location.pdf_url`, `landing_url` from `best_oa_location.landing_page_url`, `institutions` as the sorted unique `display_name` across `authorships[].institutions`, `is_oa`/`oa_status` from `open_access`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_scout_openalex.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add 03_Retrieval/challenge/scout/__init__.py 03_Retrieval/challenge/scout/openalex.py tests/fixtures/openalex tests/test_scout_openalex.py
git commit -m "Add OpenAlex client for the paper scout"
```

### Task 2: Research areas and tiers

**Files:**
- Create: `03_Retrieval/challenge/scout/areas.py`, `03_Retrieval/challenge/scout/tiers.py`
- Test: `tests/test_scout_tiers.py`

**Interfaces:**
- Produces: `AREAS: dict[str, dict]` with keys `roasting, processing, sustainability, agronomy, extraction, health, packaging, sensory`, each `{"label": str, "query": str, "category": str}` where `category` is a `schema.Category` value (`other` for extraction, packaging, sensory); `assign_tier(work: dict) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scout_tiers.py  (same sys.path preamble as Task 1)
from scout import areas, tiers

def test_eight_areas_with_schema_categories():
    assert set(areas.AREAS) == {"roasting","processing","sustainability","agronomy","extraction","health","packaging","sensory"}
    assert all(a["category"] in {"agronomy","processing","roasting","health","sustainability","other"} for a in areas.AREAS.values())
    assert all(a["query"].strip() for a in areas.AREAS.values())

def test_tier_metadata_when_no_abstract():
    assert tiers.assign_tier({"abstract": None, "pdf_url": "https://x/y.pdf"}) == "metadata"

def test_tier_abstract_when_no_pdf_url():
    assert tiers.assign_tier({"abstract": "text", "pdf_url": None}) == "abstract"

def test_tier_pdf_when_both():
    assert tiers.assign_tier({"abstract": "text", "pdf_url": "https://x/y.pdf"}) == "pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_tiers.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `areas.py` and `tiers.py`**

Queries are the assistant's call, one per area, for example `coffee roasting OR roasted coffee chemistry` for roasting and `coffee packaging OR coffee shelf life` for packaging. The tier is decided from fields only; whether the PDF URL really serves a PDF is checked in Task 8 when the file is fetched, so the seed run makes no publisher requests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scout_tiers.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add 03_Retrieval/challenge/scout/areas.py 03_Retrieval/challenge/scout/tiers.py tests/test_scout_tiers.py
git commit -m "Add research areas and document tiers for the scout"
```

### Task 3: SQLite store

**Files:**
- Create: `03_Retrieval/challenge/scout/store.py`
- Test: `tests/test_scout_store.py`

**Interfaces:**
- Consumes: normalised work dicts from Task 1, tier strings from Task 2.
- Produces: `class Store` with `__init__(self, path: Path)`, `upsert_works(self, works: list[dict], *, area: str, first_seen: str) -> int` (count of new ids; an existing id gets the area appended to its `areas` list and nothing else changed), `works(self, *, area: str | None = None, tier: str | None = None, since_published: str | None = None, since_seen: str | None = None, ids: list[str] | None = None) -> list[dict]` (each dict is the normalised work plus `areas: list[str]`, `tier`, `first_seen`, `similarity: float | None`, `triage: dict | None`, `card: dict | None` for the latest card), `set_tier(self, work_id: str, *, tier: str) -> None`, `set_triage(self, work_id: str, *, triage: dict | None, similarity: float | None) -> None`, `add_card(self, work_id: str, *, card: dict, schema_version: str, model: str, tier: str, cost_usd: float) -> int` (returns the new version, starting at 1), `latest_card(self, work_id: str) -> dict | None` (`{"version","card","model","tier","cost_usd","created_at"}`), `set_fulltext(self, work_id: str, *, markdown: str, source_url: str) -> None`, `fulltext(self, work_id: str) -> str | None`, `add_run(self, *, kind: str, params: dict, counts: dict, tokens: int, cost_usd: float, ran_at: str) -> int`, `last_run(self, *, kind: str) -> dict | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scout_store.py  (same preamble)
from scout.store import Store

def work(i, **over):
    base = {"id": f"W{i}", "doi": None, "title": f"t{i}", "year": 2025, "publication_date": "2025-03-01", "type": "article",
            "source": None, "cited_by_count": 0, "is_retracted": False, "institutions": [], "is_oa": True, "oa_status": "gold",
            "pdf_url": None, "landing_url": None, "abstract": "a", "language": "en"}
    return {**base, **over}

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_store.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `scout/store.py`**

Tables: `works(id TEXT PRIMARY KEY, json TEXT, areas TEXT, tier TEXT, first_seen TEXT, publication_date TEXT, similarity REAL, triage TEXT)`, `cards(work_id TEXT, version INTEGER, schema_version TEXT, model TEXT, tier TEXT, cost_usd REAL, created_at TEXT, card TEXT, PRIMARY KEY(work_id, version))`, `fulltext(work_id TEXT PRIMARY KEY, markdown TEXT, source_url TEXT, created_at TEXT)`, `runs(id INTEGER PRIMARY KEY, kind TEXT, ran_at TEXT, params TEXT, counts TEXT, tokens INTEGER, cost_usd REAL)`. JSON columns hold the normalised work, the areas list, the triage dict and the card. `created_at` is `datetime.now(timezone.utc).isoformat()`. Use one connection per `Store`, `executemany` in a transaction for upserts.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scout_store.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add 03_Retrieval/challenge/scout/store.py tests/test_scout_store.py
git commit -m "Add the SQLite paper store"
```

### Task 4: Shared card module and the card step

**Files:**
- Create: `01_Product_Engineering/challenge/card.py`
- Modify: `01_Product_Engineering/challenge/app.py:27-85` (move `CARD_INSTRUCTIONS`, `_card_prompt`, `_to_card` out; import `build_card_prompt`, `parse_card` from `card`)
- Modify: `01_Product_Engineering/challenge/Dockerfile:25` (`COPY llm.py app.py schema.py card.py ./`)
- Create: `03_Retrieval/challenge/scout/cards.py`
- Test: `tests/test_scout_cards.py`

**Interfaces:**
- Consumes: `schema.Request`, `schema.Response`; `helpers.llm.chat(cfg, prompt_or_messages, **kwargs) -> str`; `helpers.llm.CallStats`.
- Produces: `card.build_card_prompt(request: Request) -> str` and `card.parse_card(raw: str, request: Request) -> Response` (same behaviour as the functions they replace); `cards.card_work(cfg, work: dict, *, focus: str | None, languages: list[str], text: str | None = None, model: str | None = None, stats: CallStats | None = None, chat=helpers.llm.chat) -> Response`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scout_cards.py  (preamble adds both 01_Product_Engineering/challenge and 03_Retrieval/challenge to sys.path)
from schema import Request, Response
import card
from scout import cards

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
        seen["prompt"] = prompt; return GOOD
    out = cards.card_work(None, work, focus="x", languages=["en"], text="full text here", chat=chat)
    assert "full text here" in seen["prompt"] and "abstract_only" not in out.trust_warnings
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_cards.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'card'`

- [ ] **Step 3: Create `card.py` by moving the three objects out of `app.py`, renamed `build_card_prompt` and `parse_card`; update `app.py` imports and call sites; update the Dockerfile `COPY` line**

- [ ] **Step 4: Implement `scout/cards.py`**

`card_work` builds `Request(document_text=text or work["abstract"], title=work["title"], source=work.get("source"), focus=focus, output_languages=languages)`, calls `chat(cfg, build_card_prompt(request), model=model, stats=stats)` when `model` is given else without it, parses with `parse_card`, and when `text is None` and the card is not a decline appends `abstract_only` to `trust_warnings` if absent.

- [ ] **Step 5: Run tests to verify they pass, and the Week 1 app still imports**

Run: `uv run pytest tests/test_scout_cards.py -v` then `cd 01_Product_Engineering/challenge && uv run python -c "import app; print('ok')"`
Expected: 4 passed; `ok`

- [ ] **Step 6: Commit**

```bash
git add 01_Product_Engineering/challenge/card.py 01_Product_Engineering/challenge/app.py 01_Product_Engineering/challenge/Dockerfile 03_Retrieval/challenge/scout/cards.py tests/test_scout_cards.py
git commit -m "Share the card prompt between the app and the scout"
```

### Task 5: Similarity, triage and selection

**Files:**
- Create: `03_Retrieval/challenge/scout/funnel.py`
- Test: `tests/test_scout_funnel.py`

**Interfaces:**
- Consumes: an embedder with `.embed(texts) -> (n, dim)` normalised float32 (`helpers.embeddings.Embedder`); `helpers.llm.chat`.
- Produces: `similarity_to_focus(embedder, works: list[dict], *, focus: str) -> dict[str, float]` (work id to cosine of `title + "\n" + abstract` against `focus`); `TRIAGE_PROMPT: str`; `triage_work(cfg, work: dict, *, focus: str, model: str | None = None, stats=None, chat=helpers.llm.chat) -> dict | None` returning `{"relevance": int, "reason": str, "is_study": bool}` or None when the reply cannot be parsed; `select_for_cards(works: list[dict], *, n: int = 10) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scout_funnel.py  (preamble)
import numpy as np
from scout import funnel

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_funnel.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `scout/funnel.py`**

`TRIAGE_PROMPT` is a fixed prefix (so prompt caching applies) asking for one JSON object with `relevance` 1 to 3, `reason` under 20 words and `is_study`, followed by the focus, title and abstract. Parsing keeps the text between the first `{` and the last `}` like `parse_card`. Selection sorts by `triage.relevance` descending then `similarity` descending, excluding retracted works, tier `metadata`, triage None and `is_study` false.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scout_funnel.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add 03_Retrieval/challenge/scout/funnel.py tests/test_scout_funnel.py
git commit -m "Add similarity, triage and card selection to the scout"
```

### Task 6: Pipeline and command line

**Files:**
- Create: `03_Retrieval/challenge/scout/pipeline.py`, `03_Retrieval/challenge/scout.py`
- Modify: `.env.template` (add `OPENALEX_MAILTO=` and `TRIAGE_MODEL=` lines with one comment each)
- Test: `tests/test_scout_pipeline.py`

**Interfaces:**
- Consumes: Tasks 1 to 5.
- Produces: `seed(store, *, areas: list[str], from_date: str, per_area: int, today: str, search=search_works, mailto: str | None = None) -> dict` (counts: `fetched`, `new`, per tier); `update(store, *, areas: list[str], per_area: int, today: str, overlap_days: int = 90, search=search_works, mailto=None) -> dict`, raising `ValueError("no seed run yet; run seed first")` when `last_run(kind="seed")` is None, otherwise fetching from the later of the last seed or update `ran_at` minus `overlap_days`; `screen(store, cfg, embedder, *, area: str, focus: str, n: int = 10, floor: float = 0.25, triage_model: str | None = None, card_model: str | None = None, languages=("en", "it"), today: str, chat=helpers.llm.chat) -> dict` (`ranked`: list of `{id, title, year, source, tier, similarity, triage}` sorted as `select_for_cards` sorts, `carded`: list of ids, `tokens`, `cost_usd`). Every function records a run row. CLI `scout.py` with subcommands `seed`, `update`, `screen --area X --focus "..." [--n 10]`, `fulltext` (Task 8), `views` (Task 7); database path from `SCOUT_DB`, default `use_case/data/scout.sqlite`; config via `helpers.nb.bootstrap` like `02_Open_Weights/challenge/generate.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scout_pipeline.py  (preamble)
from scout import pipeline
from scout.store import Store
import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_pipeline.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `scout/pipeline.py`**

`queries` is an optional mapping overriding `AREAS[area]["query"]`, present so tests inject queries. `screen` embeds `focus` plus every `abstract`/`pdf` tier work in the area (the `Embedder` cache under `use_case/data/.embed_cache` makes repeats free), stores similarity, triages only works at or above `floor`, stores triage, selects with `select_for_cards`, cards each selected work with `card_work` (tier `abstract` text None), stores the card with `schema_version` read from `01_Product_Engineering/challenge/pyproject.toml`, and records a `screen` run with tokens and cost from `CallStats`. Cost per token is read from `CARD_PRICE_IN`/`CARD_PRICE_OUT` env when set, else 0 with `cost_usd` marked unknown in the run params.

- [ ] **Step 4: Implement `scout.py` CLI and add the two `.env.template` lines**

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_scout_pipeline.py -v`
Expected: 4 passed

- [ ] **Step 6: Run the real seed once and keep the numbers**

Run: `uv run python 03_Retrieval/challenge/scout.py seed`
Expected: a `use_case/data/scout.sqlite` file; the command prints fetched, new and per-tier counts per area and in total. The user copies those counts into `use_case/data/DATASHEET.md` under a new "Scout corpus" heading, marked *measured*, with the date.

- [ ] **Step 7: Commit**

```bash
git add 03_Retrieval/challenge/scout/pipeline.py 03_Retrieval/challenge/scout.py .env.template tests/test_scout_pipeline.py
git commit -m "Add seed, update and screen commands to the scout"
```

### Task 7: Views: JSONL, chunks, wiki, vector store

**Files:**
- Create: `03_Retrieval/challenge/scout/views.py`
- Modify: `03_Retrieval/challenge/scout.py` (wire `views` subcommand)
- Test: `tests/test_scout_views.py`

**Interfaces:**
- Consumes: `Store.works`, `Store.fulltext`, `helpers.rag.chunk(text, size, overlap)`, `helpers.vectorstore.VectorStore`.
- Produces: `export_jsonl(store, *, path: Path) -> int`; `build_chunks(store, *, include_fulltext: bool = True, size: int = 900, overlap: int = 150) -> list[dict]` with each chunk `{"id": "<W>#<n>", "source": "<W>", "work_id", "tier", "language": "en" | "it", "publication_date", "first_seen", "areas", "text"}`; `render_wiki(store, *, directory: Path) -> int` writing `<W>.md` per work, `index.md` listing areas with counts and linking `index_<area>.md`, and one `index_<area>.md` per area listing `W-id | year | title | tier` sorted by publication date descending; `build_vector_store(chunks: list[dict], embedder, *, path: Path) -> VectorStore` saved as `path.npy` + `path.jsonl`. Default output locations: `use_case/data/corpus.jsonl`, `use_case/data/wiki/`, `use_case/data/index/chunks`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scout_views.py  (preamble; reuse the `work` factory from the store test)
from scout import views
from scout.store import Store

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

def test_wiki_pages_named_by_id_with_fixed_headings(tmp_path):
    n = views.render_wiki(seeded(tmp_path), directory=tmp_path / "wiki")
    assert n == 2 and (tmp_path / "wiki" / "W1.md").exists() and (tmp_path / "wiki" / "W2.md").exists()
    page = (tmp_path / "wiki" / "W1.md").read_text(encoding="utf-8")
    for h in ("## Metadata", "## Abstract", "## Card", "## Trust", "## Full text"): assert h in page
    assert "## Full text" not in (tmp_path / "wiki" / "W2.md").read_text(encoding="utf-8")
    index = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "index_roasting.md" in index and "W1" in (tmp_path / "wiki" / "index_roasting.md").read_text(encoding="utf-8")

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_views.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `scout/views.py` and the `views` subcommand**

Chunk order per work: `title + abstract` (en), then `summary_it + notes_it` (it, only when a card exists), then `main_finding + trust` (en, only when a card exists), then `helpers.rag.chunk` over the full text (en) when `include_fulltext` and a full text exists. The wiki page uses the card's English fields in `## Card` and the Italian ones under a `### Italiano` subheading inside it, so `grep_wiki` finds both.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scout_views.py -v`
Expected: 4 passed

- [ ] **Step 5: Build the real views and look at ten chunks**

Run: `uv run python 03_Retrieval/challenge/scout.py views` then `uv run python -c "import json,itertools; [print(json.loads(l)['id'], json.loads(l)['text'][:120]) for l in itertools.islice(open('use_case/data/index/chunks.jsonl', encoding='utf-8'), 10)]"`
Expected: wiki directory, `corpus.jsonl`, `chunks.npy` + `chunks.jsonl`; ten readable chunks with W-ids. Reading them is the first retrieval-debugging step and is done before any technique exists.

- [ ] **Step 6: Commit**

```bash
git add 03_Retrieval/challenge/scout/views.py 03_Retrieval/challenge/scout.py tests/test_scout_views.py
git commit -m "Render corpus views: JSONL, chunks, wiki and vector store"
```

### Task 8: PDF tier with docling (two-hour timebox)

**Files:**
- Modify: `pyproject.toml` (add `pdf = ["docling>=2.142"]` dependency group with a two-line comment in the style of `local`)
- Create: `03_Retrieval/challenge/scout/pdf.py`
- Modify: `03_Retrieval/challenge/scout.py` (wire `fulltext` subcommand)
- Test: `tests/test_scout_pdf.py`

**Interfaces:**
- Consumes: `Store.works(tier="pdf")`, `Store.latest_card`, `Store.set_fulltext`, `Store.set_tier`, `cards.card_work(..., text=markdown)`.
- Produces: `fetch_pdf(url: str, *, dest: Path, timeout: float = 30.0, opener=urllib.request.urlopen) -> Path | None` (None unless the response `Content-Type` contains `application/pdf` or the body starts with `%PDF-`); `convert_pdf(path: Path) -> str` (docling to Markdown, OCR off, table structure on, page images off; raises `RuntimeError("docling is not installed; run: uv sync --group pdf")` when the import fails); `fulltext_for_carded(store, cfg, *, directory: Path, limit: int = 10, min_chars: int = 2000, fetch=fetch_pdf, convert=convert_pdf, chat=helpers.llm.chat) -> dict` (for works with a latest card, tier `pdf` and no full text: fetch, convert, store the Markdown, re-card from the full text as a new card version; on fetch failure or output under `min_chars`, set tier to `abstract` and keep the abstract card; counts `converted`, `downgraded`).

- [ ] **Step 1: Start the clock and write the failing tests**

```python
# tests/test_scout_pdf.py  (preamble)
import io
from scout import pdf
from scout.store import Store

class Resp:
    def __init__(self, ctype, body): self.headers = {"Content-Type": ctype}; self._b = body
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False

def test_fetch_pdf_rejects_html_landing_page(tmp_path):
    assert pdf.fetch_pdf("https://x/y", dest=tmp_path / "y.pdf", opener=lambda req, timeout: Resp("text/html", b"<html>")) is None

def test_fetch_pdf_accepts_pdf_by_magic_bytes(tmp_path):
    out = pdf.fetch_pdf("https://x/y", dest=tmp_path / "y.pdf", opener=lambda req, timeout: Resp("application/octet-stream", b"%PDF-1.7 ..."))
    assert out == tmp_path / "y.pdf" and out.read_bytes().startswith(b"%PDF-")

def test_fulltext_downgrades_on_failure_and_recards_on_success(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, pdf_url="https://x/1.pdf"), work(2, pdf_url="https://x/2.pdf")], area="roasting", first_seen="2026-10-27")
    for i in (1, 2):
        s.set_tier(f"W{i}", tier="pdf")
        s.add_card(f"W{i}", card={"needs_human": False, "trust_warnings": ["abstract_only"]}, schema_version="0.1.0", model="m", tier="abstract", cost_usd=0)
    def fetch(url, *, dest, **k):
        if "1.pdf" not in url:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(b"%PDF-"); return dest
    convert = lambda path: "# Paper\n" + "word " * 1000
    GOOD = '{"needs_human": false, "category": "roasting", "relevance": 3, "study_type": "x", "sample_size": 12, "main_finding": "f", "summary_en": "s", "summary_it": "r", "notes_en": null, "notes_it": null, "affiliation": "unknown", "trust_level": "high", "trust_warnings": []}'
    counts = pdf.fulltext_for_carded(s, None, directory=tmp_path / "pdf", fetch=fetch, convert=convert, chat=lambda c, p, **k: GOOD)
    assert counts == {"converted": 1, "downgraded": 1}
    assert s.latest_card("W1")["version"] == 2 and s.latest_card("W1")["tier"] == "pdf" and s.fulltext("W1")
    assert s.works(ids=["W2"])[0]["tier"] == "abstract" and s.latest_card("W2")["version"] == 1

def test_convert_pdf_explains_missing_docling(monkeypatch, tmp_path):
    import sys, pytest
    # A None entry in sys.modules makes `import docling...` raise ImportError.
    for name in ("docling", "docling.document_converter", "docling.datamodel.pipeline_options"):
        monkeypatch.setitem(sys.modules, name, None)
    with pytest.raises(RuntimeError, match="uv sync --group pdf"):
        pdf.convert_pdf(tmp_path / "x.pdf")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scout_pdf.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add the `pdf` group, install it, implement `scout/pdf.py` and the `fulltext` subcommand**

Run: `uv sync --group pdf` (downloads torch; several minutes). `convert_pdf` imports docling inside the function, builds `DocumentConverter` with `PdfPipelineOptions(do_ocr=False, do_table_structure=True, generate_page_images=False)` and returns `result.document.export_to_markdown()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scout_pdf.py -v`
Expected: 4 passed

- [ ] **Step 5: Try three real papers**

Run: `uv run python 03_Retrieval/challenge/scout.py fulltext --limit 3`
Expected: counts printed; at least one `converted`. Note the seconds per paper and the first-run model download in `use_case/data/DATASHEET.md` (user writes the numbers, marked *measured*).

- [ ] **Step 6: Timebox check**

If Step 5 has not produced one converted paper within two hours of starting Step 1: keep `fetch_pdf` and the tests, replace the `convert_pdf` body with `raise RuntimeError("PDF conversion deferred: <reason>")`, leave the `pdf` group in place, and record the reason in the datasheet. Full-text chunks are then absent and the comparison in Part 2 runs on abstracts and cards only.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock 03_Retrieval/challenge/scout/pdf.py 03_Retrieval/challenge/scout.py tests/test_scout_pdf.py
git commit -m "Add the PDF tier with docling behind an opt-in group"
```

---

## Part 2: the graded work (the student writes; the assistant coaches)

Each task below gives the shape the design fixed and the checks that prove it. The assistant may write the validator in Task 9 (plumbing, not labels) and may explain, review and debug everything else. The code, labels, table, endpoint and prose are the student's.

### Task 9: Labels and their validator

**Files:**
- Create (student): `use_case/evals/retrieval.jsonl`
- Create (assistant, plumbing): `03_Retrieval/challenge/scout/labels.py`
- Test: `tests/test_scout_labels.py`

**Interfaces:**
- Produces: `load_labels(path: Path, *, store) -> list[dict]` validating each line has `question`, `gold` (list of ids present in the store; may be empty only when `kind == "decline"`), `kind` in `{"lookup", "multi-hop", "decline"}`, non-empty `expected_terms`, and `must_decline == (kind == "decline")`, raising `ValueError` naming the line number; `to_case(label: dict) -> dict` returning Session 5's shape `{"id", "question", "expected_terms", "expected_pages": gold, "must_decline"}`.

- [ ] **Step 1 (student, day one of Task 6): send the request to the R&D researcher**: the eight seed areas read back, a request for ten real questions they asked in the last months, each with the one-sentence answer they would accept, at least one the literature cannot answer, and a date for the Step 6 session.
- [ ] **Step 2 (assistant): write the failing validator tests** with one valid label, one gold id not in the store, one decline with terms, one lookup with empty gold.
- [ ] **Step 3 (assistant): implement `labels.py`**, run `uv run pytest tests/test_scout_labels.py -v`, expected 4 passed, commit `Add the retrieval label validator`.
- [ ] **Step 4 (student): write the ten lines** from the researcher's answers, or under the agreed contingency from real past requests with provisional labels. Pick gold ids from the wiki index. Lift `expected_terms` from the researcher's sentence, in their language. Add the header line counting how many questions need more than one record.
- [ ] **Step 5 (student): validate**: `uv run python -c "import sys; sys.path.insert(0, '03_Retrieval/challenge'); from scout.labels import load_labels; from scout.store import Store; print(len(load_labels(__import__('pathlib').Path('use_case/evals/retrieval.jsonl'), store=Store(__import__('pathlib').Path('use_case/data/scout.sqlite')))), 'labels ok')"`
  Expected: `10 labels ok`. Commit the labels file: `Label ten retrieval questions`.

### Task 10: Three retrieval tool sets (student)

**Files:**
- Create (student): `03_Retrieval/challenge/retrieval.py`
- Test (student): `tests/test_retrieval.py`

**Interfaces the design fixes (shape only):**
- `bm25_tools(chunks: list[dict]) -> tuple[list[dict], dict]` returning Session 5's `(tools, funcs)` pair for `search_chunks`, chunk ids as `<W>#<n>`.
- `dci_tools(wiki_dir: Path) -> tuple[list[dict], dict]` for `list_pages`, `grep_wiki`, `read_page`; `read_page` without the `enum` because the wiki has hundreds of pages; `list_pages` returns `index.md` and `read_page("index_<area>")` the area index.
- `dense_tools(store_path: Path, embedder) -> tuple[list[dict], dict]` over `VectorStore`. Its `where` filter is equality or set membership only (`helpers/vectorstore.py:93-99`), so a date floor is applied by selecting the allowed work ids from the store first and passing `where={"work_id": [...]}`; `language` filters pass through directly.
- `hybrid_tools(chunks, store_path, embedder, *, rrf_k: int = 60) -> tuple[list[dict], dict]` fusing BM25 and dense ranks with Session 6's `reciprocal_rank_fusion`.
- Every tool result tags each passage with its `W…` id so the model can cite it literally.
- Decline markers in `score` are English; Italian answers need `non `, `nessun`, `non ci sono`, `non risulta` added by the student, and the change written next to the table.

- [ ] **Step 1 (student): write one test per tool set** asserting that a known phrase from a chosen W-id's abstract retrieves that id first, and that the `where` filter excludes a work published before the filter date.
- [ ] **Step 2 (student): implement** the four functions, reading Session 5's cell at `S5_Agentic_Retrieval.py:195-240` and Session 6's `reciprocal_rank_fusion` for the shape.
- [ ] **Step 3 (student): print ten retrieved chunks for two labelled questions** before running any agent, and fix chunking or vocabulary mismatch first.
- [ ] **Step 4 (student): run the tests, commit** `Add three retrieval tool sets over the scout corpus`.

### Task 11: The comparison (student)

**Files:**
- Create (student): `03_Retrieval/challenge/compare.py`, `03_Retrieval/challenge/results.md`

**Shape the design fixes:**
- `run_agent` and `score` copied unchanged from Session 5 (plus the Italian decline markers), `max_turns=6`, the same system prompt for every technique with "cite the W-ids of the records you used" added.
- One row per technique: `pass_rate, citation_rate, avg_calls, avg_evidence_chars, avg_latency_s, stop reasons`, over the ten labels, run twice: with and without full-text chunks when Task 8 converted any.
- Settings next to the table: model, turn budget, chunk size and overlap, embedding model and its measured token count from `Embedder.stats`, RRF `k`, and reranker first-stage size if the optional fourth run happens.

- [ ] **Step 1 (student): write `compare.py`** looping techniques × cases, saving per-case details to `use_case/data/compare_<date>.jsonl` and the table to `results.md`.
- [ ] **Step 2 (student): run it**: `uv run python 03_Retrieval/challenge/compare.py`. Expected: `results.md` with at least three rows and six columns; the embedding token count marked *measured*.
- [ ] **Step 3 (student): read the trace of every failed case** before changing anything, in the order the instructor rules give: chunks, retrieved set, vocabulary, then prompt.
- [ ] **Step 4 (student): commit** `Compare three retrieval techniques on ten labelled questions`.

### Task 12: The question endpoint (student)

**Files:**
- Modify (student): `01_Product_Engineering/challenge/schema.py` (add `AskRequest`, `AskResponse` with `sources`, and implement `solve()` as the card function), `app.py` (add `ask_research_corpus`), `pyproject.toml` and `uv.lock` of the challenge (the winning technique's package only, per the approved answer), `Dockerfile` (`COPY` the new module and read `SCOUT_INDEX_DIR`).
- Modify (student): `use_case/CHARTER.md` (Week 3 row and the new In/Out line), `use_case/decisions.md` (one line: `sources` and the question type added, why).

**Shape the design fixes:**
- Input: `question: str`, `area: str | None`, `since: str | None` (publication date floor). Output JSON: `answer`, `sources: list[{"id", "title", "doi"}]`, `declined: bool`, `decline_reason: str | None`, `trace: {"calls", "evidence_chars", "latency_s", "stopped"}`.
- The answer model reads the top 3 to 5 passages, never more. Decline when the best score is under the student's chosen threshold or when retrieval returns nothing after the filters.
- The index directory is mounted at run time; the app never builds it and never calls OpenAlex.
- Docstring written for an agent that sees nothing else.

- [ ] **Step 1 (student): design the two models and the docstring**, review with the assistant.
- [ ] **Step 2 (student): implement**, run the ten questions through the endpoint locally, and once more inside Docker with the index mounted: `docker build -t fde-app . && docker run --env-file .env -e SCOUT_INDEX_DIR=/data -v <abs path>/use_case/data:/data -p 7860:7860 fde-app`.
- [ ] **Step 3 (student): commit** `Add the cited question endpoint over the paper corpus`.

### Task 13: Decisions, Step 6, Step 7, submission (student)

- [ ] **Step 1 (student): `use_case/decisions.md` Week 3 row** (decision, rejected, why with numbers from `results.md` marked *measured*, what would change your mind) and the four non-text answers; the charter's Week 3 row; a `stakeholders.md` row only after the Step 6 session happened.
- [ ] **Step 2 (student): Step 6 session** with the R&D researcher: five questions of theirs through the endpoint, would they act on each answer; add the five to `retrieval.jsonl` with labels; three findings in the README. The assistant helps with the shape, never the content.
- [ ] **Step 3 (student): Step 7 lines** in the README: the data, the model or endpoint, the approval needed at work; embedding token count next to them.
- [ ] **Step 4 (student): README, Loom under five minutes, Maven post, `nb_status.md` update.** Commit `Submit Technical Challenge 3`.

---

## Self-review notes

- Spec coverage: funnel stages 1 to 6 map to Tasks 1, 2, 5, 4 and 6; fetch-once-then-update and the local diff to Task 6; latest-only views to the `since_*` filters in Tasks 3, 7 and 12; the card as a separate tool with provenance to Task 4 (the app's endpoint is untouched; provenance rides in the `cards` table); SQLite tables to Task 3; views and the bilingual chunks to Task 7; the PDF tier and its timebox to Task 8; the question endpoint, labels, techniques, comparison and decisions to Part 2; the order of work A to F matches Tasks 1–8, 9, 10–11, 12, 8's re-run in 11, 13.
- Review Focus items 1 to 5 are tested in Tasks 2, 3, 5, 6 and 8 respectively.
- Names used across tasks: `Store` methods, `card_work`, `select_for_cards`, `build_chunks`, `fetch_pdf`, `convert_pdf`, `load_labels`, `to_case` are consistent between their defining task and later references.
- Out of this plan by the approved design: email reports, scheduled runs, review UI, model-based ranking, topic synthesis pages, vector database.
