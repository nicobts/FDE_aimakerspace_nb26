"""The full-text tier: download an open-access PDF, convert it to Markdown, and card the paper again from it."""

import datetime
import sys
import urllib.error
import urllib.request
from pathlib import Path

import helpers.llm

from .cards import card_work
from .pipeline import _prices, call_cost, schema_version

# Publishers often answer a bare urllib request with a 403; a browser-like agent gets the open-access copy.
_USER_AGENT = "Mozilla/5.0 (compatible; coffee-scout/0.1)"


def fetch_pdf(url: str, *, dest: Path, timeout: float = 30.0, opener=urllib.request.urlopen) -> Path | None:
    """Save the PDF at `url` to `dest`; None when the server refuses or sends something else (a landing page)."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type") or ""
    # URLError and TimeoutError are OSError subclasses; a refusing publisher is a downgrade, not a crash.
    except OSError:
        return None
    # Many "PDF" links answer with HTML, and some PDFs come back as octet-stream, so check the bytes too.
    if "application/pdf" not in content_type.lower() and not body.startswith(b"%PDF-"):
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return dest


def convert_pdf(path: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat
    except ImportError as exc:
        raise RuntimeError("docling is not installed; run: uv sync --group pdf") from exc
    # OCR and page images are the slow parts and open-access papers carry a text layer; tables are worth keeping.
    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True, generate_page_images=False)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    return converter.convert(path).document.export_to_markdown()


def fulltext_for_carded(store, cfg, *, directory: Path, limit: int = 10, min_chars: int = 2000,
                        fetch=fetch_pdf, convert=convert_pdf, chat=helpers.llm.chat,
                        today: str | None = None) -> dict:
    today = today or datetime.date.today().isoformat()
    # The latest screen's focus keeps the full-text card answering the same question as the abstract card.
    screen_run = store.last_run(kind="screen")
    focus = screen_run["params"].get("focus") if screen_run else None
    candidates = [w for w in store.works(tier="pdf")
                  if store.latest_card(w["id"]) and store.fulltext(w["id"]) is None][:limit]
    stats = helpers.llm.CallStats()
    prices = _prices()
    version = schema_version()
    model = cfg.llm_model if cfg else "injected"
    converted = downgraded = 0
    for work in candidates:
        work_id = work["id"]
        markdown = None
        path = fetch(work["pdf_url"], dest=directory / f"{work_id}.pdf")
        if path is not None:
            try:
                markdown = convert(path)
            except Exception as exc:  # a broken PDF must not stop the batch
                print(f"{work_id}: conversion failed: {exc}", file=sys.stderr)
        # Too little text means a scanned or paywalled page; the abstract card stays the better record.
        if markdown is None or len(markdown) < min_chars:
            store.set_tier(work_id, tier="abstract")
            downgraded += 1
            continue
        store.set_fulltext(work_id, markdown=markdown, source_url=work["pdf_url"])
        before = (stats.prompt_tokens, stats.completion_tokens)
        card = card_work(cfg, work, focus=focus, languages=["en", "it"], text=markdown, stats=stats, chat=chat)
        cost = call_cost(prices, prompt_tokens=stats.prompt_tokens - before[0],
                         completion_tokens=stats.completion_tokens - before[1])
        store.add_card(work_id, card=card.model_dump(), schema_version=version, model=model, tier="pdf", cost_usd=cost)
        converted += 1
    counts = {"converted": converted, "downgraded": downgraded}
    store.add_run(kind="fulltext", params={"limit": limit, "min_chars": min_chars}, counts=counts,
                  tokens=stats.total_tokens,
                  cost_usd=call_cost(prices, prompt_tokens=stats.prompt_tokens, completion_tokens=stats.completion_tokens),
                  ran_at=today)
    return counts
