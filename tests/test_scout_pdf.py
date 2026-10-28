import urllib.error

from scout_support import add_scout_paths, work
add_scout_paths()
from scout import pdf  # noqa: E402
from scout.store import Store  # noqa: E402


class Resp:
    def __init__(self, ctype, body): self.headers = {"Content-Type": ctype}; self._b = body
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False


GOOD = '{"needs_human": false, "category": "roasting", "relevance": 3, "study_type": "x", "sample_size": 12, "main_finding": "f", "summary_en": "s", "summary_it": "r", "notes_en": null, "notes_it": null, "affiliation": "unknown", "trust_level": "high", "trust_warnings": []}'


def test_fetch_pdf_rejects_html_landing_page(tmp_path):
    assert pdf.fetch_pdf("https://x/y", dest=tmp_path / "y.pdf", opener=lambda req, timeout: Resp("text/html", b"<html>")) is None


def test_fetch_pdf_accepts_pdf_by_magic_bytes(tmp_path):
    out = pdf.fetch_pdf("https://x/y", dest=tmp_path / "y.pdf", opener=lambda req, timeout: Resp("application/octet-stream", b"%PDF-1.7 ..."))
    assert out == tmp_path / "y.pdf" and out.read_bytes().startswith(b"%PDF-")


def test_fetch_pdf_returns_none_when_the_publisher_refuses(tmp_path):
    def refuse(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
    assert pdf.fetch_pdf("https://x/y", dest=tmp_path / "y.pdf", opener=refuse) is None
    assert not (tmp_path / "y.pdf").exists()


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
    counts = pdf.fulltext_for_carded(s, None, directory=tmp_path / "pdf", fetch=fetch, convert=convert, chat=lambda c, p, **k: GOOD)
    assert counts == {"converted": 1, "downgraded": 1}
    assert s.latest_card("W1")["version"] == 2 and s.latest_card("W1")["tier"] == "pdf" and s.fulltext("W1")
    assert s.works(ids=["W2"])[0]["tier"] == "abstract" and s.latest_card("W2")["version"] == 1
    assert s.last_run(kind="fulltext")["counts"] == counts


def test_fulltext_downgrades_short_output_and_broken_pdfs_and_keeps_going(tmp_path, capsys):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(i, pdf_url=f"https://x/{i}.pdf") for i in (1, 2, 3)], area="roasting", first_seen="2026-10-27")
    for i in (1, 2, 3):
        s.set_tier(f"W{i}", tier="pdf")
        s.add_card(f"W{i}", card={"needs_human": False}, schema_version="0.1.0", model="m", tier="abstract", cost_usd=0)
    def fetch(url, *, dest, **k):
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(b"%PDF-"); return dest
    def convert(path):
        if path.stem == "W1":
            raise ValueError("corrupt xref")
        return "short" if path.stem == "W2" else "word " * 1000
    counts = pdf.fulltext_for_carded(s, None, directory=tmp_path / "pdf", fetch=fetch, convert=convert, chat=lambda c, p, **k: GOOD)
    assert counts == {"converted": 1, "downgraded": 2}
    assert "corrupt xref" in capsys.readouterr().err
    assert s.fulltext("W2") is None and s.works(ids=["W2"])[0]["tier"] == "abstract"


def test_fulltext_skips_uncarded_and_already_converted(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1, pdf_url="https://x/1.pdf"), work(2, pdf_url="https://x/2.pdf")], area="roasting", first_seen="2026-10-27")
    for i in (1, 2):
        s.set_tier(f"W{i}", tier="pdf")
    s.add_card("W2", card={"needs_human": False}, schema_version="0.1.0", model="m", tier="pdf", cost_usd=0)
    s.set_fulltext("W2", markdown="x" * 3000, source_url="https://x/2.pdf")
    called = []
    counts = pdf.fulltext_for_carded(s, None, directory=tmp_path, fetch=lambda *a, **k: called.append(a), convert=lambda p: "")
    assert counts == {"converted": 0, "downgraded": 0} and not called


def test_convert_pdf_explains_missing_docling(monkeypatch, tmp_path):
    import sys, pytest
    # A None entry in sys.modules makes `import docling...` raise ImportError.
    for name in ("docling", "docling.document_converter", "docling.datamodel.pipeline_options"):
        monkeypatch.setitem(sys.modules, name, None)
    with pytest.raises(RuntimeError, match="uv sync --group pdf"):
        pdf.convert_pdf(tmp_path / "x.pdf")
