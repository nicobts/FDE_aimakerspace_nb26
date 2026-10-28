"""Read-only views derived from the store: JSONL export, bilingual chunks, Markdown wiki and vector store.

The store stays the system of record; everything here can be deleted and rebuilt from it.
"""
import json
from pathlib import Path

from helpers.rag import chunk
from helpers.vectorstore import VectorStore


def export_jsonl(store, *, path: Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    works = store.works()
    path.write_text("".join(json.dumps(w, ensure_ascii=False) + "\n" for w in works), encoding="utf-8")
    return len(works)


def _usable(card):
    # A decline carries no summary or trust assessment worth indexing.
    return card if card and not card.get("needs_human") else None


def _trust_line(card):
    warnings = ", ".join(card.get("trust_warnings") or []) or "none"
    return f"Trust: {card.get('trust_level') or 'unrated'}. Warnings: {warnings}."


def build_chunks(store, *, include_fulltext: bool = True, size: int = 900, overlap: int = 150) -> list[dict]:
    chunks = []
    for w in store.works():
        base = {"source": w["id"], "work_id": w["id"], "tier": w["tier"], "publication_date": w.get("publication_date"),
                "first_seen": w["first_seen"], "areas": w["areas"]}
        pieces = []  # (language, text); the index in this list becomes the chunk number

        if w.get("abstract"):
            pieces.append(("en", f"{w['title']}\n\n{w['abstract']}"))
        card = _usable(w.get("card"))
        if card:
            italian = "\n\n".join(t for t in (card.get("summary_it"), card.get("notes_it")) if t)
            if italian:
                pieces.append(("it", italian))
            finding = card.get("main_finding")
            pieces.append(("en", f"{finding}\n\n{_trust_line(card)}" if finding else _trust_line(card)))
        text = store.fulltext(w["id"]) if include_fulltext else None
        if text:
            pieces.extend(("en", part) for part in chunk(text, size=size, overlap=overlap))

        for n, (language, body) in enumerate(pieces):
            chunks.append({"id": f"{w['id']}#{n}", **base, "language": language, "text": body})
    return chunks


def _cell(text):
    return str(text).replace("|", r"\|").replace("\n", " ")


def _card_section(card):
    if not card:
        return ["No card yet."]
    if card.get("needs_human"):
        return [f"Declined: {card.get('needs_human_reason') or 'no reason given'}"]
    lines = []
    for label, key in (("Main finding", "main_finding"), ("Summary", "summary_en"), ("Notes", "notes_en"),
                       ("Study type", "study_type"), ("Sample size", "sample_size"), ("Category", "category"),
                       ("Relevance", "relevance")):
        if card.get(key) is not None:
            lines.append(f"- {label}: {card[key]}")
    italian = [(label, card.get(key)) for label, key in (("Riassunto", "summary_it"), ("Note", "notes_it")) if card.get(key)]
    if italian:
        lines += ["", "### Italiano", ""] + [f"- {label}: {value}" for label, value in italian]
    return lines or ["Card has no fields."]


def _trust_section(card):
    if not card or card.get("needs_human"):
        return ["Not assessed."]
    warnings = ", ".join(card.get("trust_warnings") or []) or "none"
    return [f"- Trust level: {card.get('trust_level') or 'unrated'}", f"- Warnings: {warnings}"]


def _page(w, fulltext):
    insts = ", ".join(w.get("institutions") or []) or "unknown"
    meta = [("Year", w.get("year")), ("Publication date", w.get("publication_date")), ("Source", w.get("source")),
            ("DOI", w.get("doi")), ("Type", w.get("type")), ("Institutions", insts), ("Areas", ", ".join(w["areas"])),
            ("Tier", w["tier"]), ("First seen", w["first_seen"]), ("OpenAlex id", w["id"]), ("URL", w.get("landing_url"))]
    lines = [f"# {w['title']}", "", "## Metadata", ""]
    lines += [f"- {label}: {value if value not in (None, '') else 'unknown'}" for label, value in meta]
    lines += ["", "## Abstract", "", w.get("abstract") or "No abstract available.", "", "## Card", ""]
    lines += _card_section(w.get("card"))
    lines += ["", "## Trust", ""] + _trust_section(w.get("card"))
    if fulltext:
        lines += ["", "## Full text", "", fulltext]
    return "\n".join(lines) + "\n"


def render_wiki(store, *, directory: Path) -> int:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    works = store.works()
    ids = {w["id"] for w in works}
    # A rebuilt wiki must not keep pages for works that left the store.
    for old in directory.glob("W*.md"):
        if old.stem not in ids:
            old.unlink()
    by_area = {}
    for w in works:
        (directory / f"{w['id']}.md").write_text(_page(w, store.fulltext(w["id"])), encoding="utf-8")
        for area in w["areas"]:
            by_area.setdefault(area, []).append(w)
    index = ["# Corpus index", ""]
    for area in sorted(by_area):
        index.append(f"- [{area}](index_{area}.md): {len(by_area[area])} works")
        # Two-pass stable sort puts dated works newest first and undated ones last.
        rows = sorted(by_area[area], key=lambda w: w["id"])
        rows.sort(key=lambda w: w.get("publication_date") or "", reverse=True)
        rows.sort(key=lambda w: w.get("publication_date") is None)
        table = [f"# {area}", "", "| W-id | year | title | tier |", "| --- | --- | --- | --- |"]
        table += [f"| [{w['id']}]({w['id']}.md) | {w.get('year') or ''} | {_cell(w['title'])} | {w['tier']} |" for w in rows]
        (directory / f"index_{area}.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    (directory / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return len(works)


def build_vector_store(chunks: list[dict], embedder, *, path: Path) -> VectorStore:
    store = VectorStore()
    if chunks:
        # One call: the Embedder batches and caches internally.
        vectors = embedder.embed([c["text"] for c in chunks])
        store.add(vectors, chunks)
    store.save(Path(path))
    return store
