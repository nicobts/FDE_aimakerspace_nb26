import json, sys, urllib.error, urllib.request
import pytest
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


class _Response:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self, *args):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


def _script_urlopen(monkeypatch, outcomes):
    calls = []

    def fake(request, timeout=None):
        calls.append(request)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


def test_fetch_json_retries_503_then_succeeds(monkeypatch):
    calls = _script_urlopen(monkeypatch, [_http_error(503), _Response({"ok": 1})])
    sleeps = []
    assert openalex.fetch_json("http://x", sleep=sleeps.append) == {"ok": 1}
    assert len(calls) == 2 and sleeps == [1]


def test_fetch_json_does_not_retry_404(monkeypatch):
    calls = _script_urlopen(monkeypatch, [_http_error(404)])
    sleeps = []
    with pytest.raises(urllib.error.HTTPError):
        openalex.fetch_json("http://x", sleep=sleeps.append)
    assert len(calls) == 1 and sleeps == []


def test_fetch_json_gives_up_after_retries_plus_one_attempts(monkeypatch):
    calls = _script_urlopen(monkeypatch, [_http_error(429)] * 4)
    sleeps = []
    with pytest.raises(urllib.error.HTTPError):
        openalex.fetch_json("http://x", retries=3, sleep=sleeps.append)
    assert len(calls) == 4 and sleeps == [1, 2, 4]
