"""OpenAlex client: search works and normalise them to the dicts the scout stores."""

import json
import time
import urllib.error
import urllib.request
from urllib.parse import quote

API = "https://api.openalex.org/works"
PAGE_SIZE = 200
BACKOFF_SECONDS = (1, 2, 4)


def rebuild_abstract(inverted):
    """OpenAlex ships abstracts as word -> positions; put the words back in order."""
    if not inverted:
        return None
    words = {pos: word for word, positions in inverted.items() for pos in positions}
    return " ".join(words[pos] for pos in sorted(words))


def _short_id(openalex_id):
    return openalex_id.rsplit("/", 1)[-1]


def normalise_work(raw):
    # Real records carry nulls where we nest (no source, no OA location), so every
    # hop falls back to {} instead of assuming the parent exists.
    source = ((raw.get("primary_location") or {}).get("source") or {}).get("display_name")
    best = raw.get("best_oa_location") or {}
    oa = raw.get("open_access") or {}
    institutions = {
        inst["display_name"]
        for authorship in raw.get("authorships") or []
        for inst in authorship.get("institutions") or []
        if inst.get("display_name")
    }
    return {
        "id": _short_id(raw["id"]),
        "doi": raw.get("doi"),
        "title": raw.get("title"),
        "year": raw.get("publication_year"),
        "publication_date": raw.get("publication_date"),
        "type": raw.get("type"),
        "source": source,
        "cited_by_count": raw.get("cited_by_count"),
        "is_retracted": raw.get("is_retracted"),
        "institutions": sorted(institutions),
        "is_oa": oa.get("is_oa"),
        "oa_status": oa.get("oa_status"),
        "pdf_url": best.get("pdf_url"),
        "landing_url": best.get("landing_page_url"),
        "abstract": rebuild_abstract(raw.get("abstract_inverted_index")),
        "language": raw.get("language"),
    }


def fetch_json(url, *, timeout=30.0, retries=3, sleep=time.sleep):
    request = urllib.request.Request(url, headers={"User-Agent": "fde-scout/0.1"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            # Rate limits and server errors are transient; anything else is our bug.
            transient = err.code == 429 or err.code >= 500
            if not transient or attempt == retries:
                raise
            sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])


def search_works(*, query, from_date, to_date=None, work_type="article",
                 max_works=300, mailto=None, fetch=fetch_json):
    # Colons and commas stay literal in the filter: OpenAlex accepts them and the
    # cursor must stay a separate parameter.
    filters = [f"from_publication_date:{from_date}"]
    if to_date:
        filters.append(f"to_publication_date:{to_date}")
    filters.append(f"type:{work_type}")
    base = f"{API}?search={quote(query, safe='')}&filter={','.join(filters)}&per-page={PAGE_SIZE}"

    works = []
    cursor = "*"
    while cursor and len(works) < max_works:
        url = f"{base}&cursor={quote(cursor, safe='*')}"
        if mailto:
            url += f"&mailto={quote(mailto, safe='')}"
        page = fetch(url)
        works.extend(normalise_work(raw) for raw in page["results"])
        cursor = page["meta"]["next_cursor"]
    return works[:max_works]
