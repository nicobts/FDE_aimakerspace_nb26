"""OpenAlex client: search works and normalise them to the dicts the scout stores."""

import http.client
import json
import time
import urllib.error
import urllib.request
from urllib.parse import quote

API = "https://api.openalex.org/works"
# 200-work pages are about 4 MB and were cut in transit; 100 keeps bodies near 1 MB with select=.
PAGE_SIZE = 100
# Only the top-level fields normalise_work reads; the full records are mostly unused bulk.
SELECT = ("id,doi,title,publication_year,publication_date,type,primary_location,cited_by_count,"
          "is_retracted,authorships,open_access,best_oa_location,abstract_inverted_index,language")
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


# A body cut in transit surfaces as a decode error or a short read, so those retry like a dropped connection.
_TRANSIENT = (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, ConnectionResetError, json.JSONDecodeError)


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
        except _TRANSIENT:
            if attempt == retries:
                raise
        sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])


def search_works(*, query, from_date, to_date=None, work_type="article",
                 max_works=300, mailto=None, api_key=None, fetch=fetch_json):
    # Offset paging, not cursors: OpenAlex wants an API key for cursor paging past
    # the first page, and the offset limit (10,000 results) is far above max_works.
    # Colons and commas stay literal in the filter: OpenAlex accepts them.
    filters = [f"from_publication_date:{from_date}"]
    if to_date:
        filters.append(f"to_publication_date:{to_date}")
    filters.append(f"type:{work_type}")
    per_page = min(PAGE_SIZE, max_works)
    base = f"{API}?search={quote(query, safe='')}&filter={','.join(filters)}&per-page={per_page}&select={SELECT}"
    if mailto:
        base += f"&mailto={quote(mailto, safe='')}"
    if api_key:
        base += f"&api_key={quote(api_key, safe='')}"

    works = []
    page_no = 0
    while len(works) < max_works:
        page_no += 1
        page = fetch(f"{base}&page={page_no}")
        results = page["results"]
        works.extend(normalise_work(raw) for raw in results)
        count = (page.get("meta") or {}).get("count")
        if len(results) < per_page or (count is not None and page_no * per_page >= count):
            break
    return works[:max_works]
