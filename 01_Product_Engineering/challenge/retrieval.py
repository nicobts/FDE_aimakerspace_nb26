"""Retrieval over the coffee paper corpus: one index, three rankers, three wiki tools.

The corpus is built by the scout (03_Retrieval/challenge/scout.py views) and lives in
use_case/data, which is gitignored. Nothing here writes to it.

    chunks   index/chunks.jsonl + index/chunks.npy   one row per abstract, card or full-text piece
    pages    wiki/W*.md                              one page per paper, stable name = OpenAlex id
    index    wiki/index.md + wiki/index_<area>.md    the page map

Rankers (all return [(chunk position, score)], best first):
    bm25_rank    lexical, no model, no approval needed
    dense_rank   cosine against the stored embeddings; one embedding call per query
    hybrid_rank  reciprocal rank fusion of the two
"""

import json
import os
import re
from functools import cache
from pathlib import Path

import numpy as np
from litellm import embedding
from rank_bm25 import BM25Okapi

# In the repo the corpus sits three levels up; in Docker it is mounted and named by CORPUS_DIR.
DATA_DIR = Path(os.getenv("CORPUS_DIR") or Path(__file__).resolve().parent.parent.parent / "use_case" / "data")

# Accented letters stay inside a token, or Italian words split in two ("qualità" -> "qualit").
TOKEN = re.compile(r"[a-z0-9àèéìíòóùú%µμ]+")

# Session 5 showed 1,000 characters per hit. Here 2,179 of 2,398 chunks are longer (median 1,582,
# 90th percentile 2,146), and abstracts put the results last, so the model saw setups without findings.
PASSAGE_CHARS = 2500
PAGE_CHARS = 12000  # what one read_page shows the model, as in Session 5


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class Corpus:
    """Everything loaded once: chunk rows, their vectors, the BM25 index and the wiki pages."""

    def __init__(self, data_dir: Path):
        index = data_dir / "index"
        self.chunks = [json.loads(line) for line in (index / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
        self.vectors = np.load(index / "chunks.npy")
        if len(self.vectors) != len(self.chunks):
            raise ValueError(f"{len(self.vectors)} vectors but {len(self.chunks)} chunks: rebuild with scout.py views")
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])
        wiki = data_dir / "wiki"
        self.pages = {p.stem: p.read_text(encoding="utf-8") for p in sorted(wiki.glob("W*.md"))}
        self.indexes = {p.stem: p.read_text(encoding="utf-8") for p in sorted(wiki.glob("index*.md"))}
        self.titles = {name: text.splitlines()[0].removeprefix("# ") for name, text in self.pages.items()}


@cache
def corpus() -> Corpus:
    # Loaded on first use, so the app still starts (and the card endpoint still works) without the data.
    return Corpus(DATA_DIR)


# --- Rankers -----------------------------------------------------------------


def bm25_rank(query: str, n: int) -> list[tuple[int, float]]:
    scores = corpus().bm25.get_scores(tokenize(query))
    order = np.argsort(-scores)[:n]
    return [(int(i), float(scores[i])) for i in order if scores[i] > 0]


EMBED_TOKENS = {"query": 0}  # measured query-side tokens, reported by the comparison


@cache  # the endpoint ranks and then gates on the same question; embed it once
def embed_query(query: str) -> np.ndarray:
    kwargs = {"model": os.environ["EMBED_MODEL"]}
    if os.getenv("EMBED_API_BASE"):
        kwargs["api_base"] = os.environ["EMBED_API_BASE"]
    if os.getenv("EMBED_API_KEY"):
        kwargs["api_key"] = os.environ["EMBED_API_KEY"]
    response = embedding(input=[query], timeout=60, **kwargs)
    usage = getattr(response, "usage", None)
    EMBED_TOKENS["query"] += getattr(usage, "prompt_tokens", 0) or 0
    vector = np.asarray(response.data[0]["embedding"], dtype=np.float32)
    # The stored vectors are L2-normalised; the query must be too, or the dot product is not cosine.
    return vector / np.linalg.norm(vector)


def dense_rank(query: str, n: int) -> list[tuple[int, float]]:
    scores = corpus().vectors @ embed_query(query)
    order = np.argsort(-scores)[:n]
    return [(int(i), float(scores[i])) for i in order]


def hybrid_rank(query: str, n: int, *, first_stage: int = 50, rrf_k: int = 60) -> list[tuple[int, float]]:
    # Ranks, not scores, are fused: a BM25 score of 14 and a cosine of 0.6 are not on one scale.
    fused: dict[int, float] = {}
    for ranking in (bm25_rank(query, first_stage), dense_rank(query, first_stage)):
        for rank, (position, _) in enumerate(ranking, start=1):
            fused[position] = fused.get(position, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(fused.items(), key=lambda item: item[1], reverse=True)[:n]


RANKERS = {"bm25": bm25_rank, "dense": dense_rank, "hybrid": hybrid_rank}


def search(query: str, *, k: int = 5, technique: str = "hybrid") -> list[dict]:
    """Top-k chunk rows, each carrying its source work id and the score that ranked it."""
    rows = corpus().chunks
    return [{**rows[position], "score": score} for position, score in RANKERS[technique](query, k)]


def format_hits(hits: list[dict]) -> str:
    # Every passage is tagged with its chunk id and title, so the model can cite the work it came from.
    titles = corpus().titles
    return "\n\n---\n\n".join(
        f"[{hit['id']}] {titles.get(hit['source'], '')}\n{hit['text'][:PASSAGE_CHARS]}" for hit in hits
    )


# --- Tools for the agentic loop ------------------------------------------------


def make_search_tool(technique: str):
    """Session 5's search_chunks, with the ranker swapped underneath and nothing else changed."""

    def search_chunks(query: str, k: int = 4) -> str:
        return format_hits(search(query, k=max(1, min(k, 8)), technique=technique)) or "(no matches)"

    return search_chunks


def list_pages(area: str | None = None) -> str:
    indexes = corpus().indexes
    if not area:
        return indexes["index"]
    page = indexes.get(f"index_{area}")
    if page is None:
        return f"(unknown area: {area}; areas: {', '.join(sorted(k.removeprefix('index_') for k in indexes if k != 'index'))})"
    # An area index holds up to ~500 rows; the cut is a measured cost of DCI at this corpus size.
    return page[:PAGE_CHARS] + ("\n(truncated: use grep_wiki to find a paper by its words)" if len(page) > PAGE_CHARS else "")


def grep_wiki(pattern: str) -> str:
    try:
        rx = re.compile(pattern, re.I)
    except re.error:
        rx = re.compile(re.escape(pattern), re.I)
    hits = []
    for name, text in corpus().pages.items():
        for number, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{name}:{number}: {line[:240]}")
                if len(hits) == 40:
                    return "\n".join(hits) + "\n(first 40 matches only: narrow the pattern)"
    return "\n".join(hits) or "(no matches)"


def read_page(page: str) -> str:
    text = corpus().pages.get(page.strip().removesuffix(".md"))
    return text[:PAGE_CHARS] if text else f"(unknown page: {page}; page names are OpenAlex ids like W4403193476)"


def _schema(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}}


SEARCH_TOOL = [_schema(
    "search_chunks",
    "Search ranked passages from coffee research papers. Each passage starts with [W<id>#<n>]. "
    "Search again with a new query when evidence is incomplete.",
    {"query": {"type": "string"}, "k": {"type": "integer"}}, ["query"])]

WIKI_TOOLS = [
    _schema("list_pages", "Read the corpus index (no area) or the paper list of one research area.",
            {"area": {"type": "string"}}),
    _schema("grep_wiki", "Search exact text or a regular expression across all paper pages; returns page:line: text.",
            {"pattern": {"type": "string"}}, ["pattern"]),
    _schema("read_page", "Read one paper page by its stable name, the OpenAlex id (for example W4403193476).",
            {"page": {"type": "string"}}, ["page"]),
]


def toolset(technique: str) -> tuple[list[dict], dict]:
    """The (tool schemas, functions) pair the loop is given for one technique."""
    if technique == "wiki":
        return WIKI_TOOLS, {"list_pages": list_pages, "grep_wiki": grep_wiki, "read_page": read_page}
    return SEARCH_TOOL, {"search_chunks": make_search_tool(technique)}
