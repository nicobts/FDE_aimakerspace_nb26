# OpenAlex ingestion and retrieval over coffee research papers

Date: 2026-10-26. Status: approved 2026-10-27. Scope: Week 3 (Technical
Challenge 3) of the FDE certification, built on the Week 1 and Week 2 work in
`01_Product_Engineering/challenge` and `use_case/`.

## 1. Intent and why

The R&D team asked for a tool that helps them scout and filter research papers.
Today a researcher spends five to ten hours per request to find, screen and
read about ten papers, then explains the findings to colleagues. Week 1 built
the cheapest minute of that hour: paste one text, get one bilingual article
card. Weeks 1 and 2 proved the card works on synthetic data.

This design inverts the flow to match the real job. Instead of a person
bringing one text to the tool, the tool fetches candidate papers from
OpenAlex, screens them cheaply, cards the ones worth reading, stores cards
and abstracts as a retrievable corpus, and answers questions over that corpus
with citations. The Week 1 charter already recorded this as the plan
("sweep the sources, card every document, rank, store, weekly report, and
conversational retrieval over the papers"). This is step two of that plan,
not a restart.

Technical Challenge 3 grades the retrieval part: ten real questions labelled
by the R&D researcher, at least three retrieval techniques measured against
those labels with six columns, an endpoint that answers with sources and
declines when it should, and a written decision. The ingestion exists so the
measurement runs on real papers rather than invented ones.

## 2. Goals, non-goals, anti-goals

Goals

- A researcher states a topic and gets, in minutes, a screened list of real
  recent papers with one full card per paper for the top ten.
- A researcher asks a question in natural language and gets an answer that
  cites the papers it is grounded in, or an explicit decline.
- The retrieval technique is chosen on measured evidence from the labels, not
  on assumption. The user's hypothesis is that hybrid wins; it is a
  hypothesis to test.
- Token spend scales with what is read, not with what OpenAlex returns.
- Every stored passage carries its provenance: OpenAlex id, DOI, tier.

Non-goals (this week)

- Emailing reports, scheduled or periodic sweeps, a web UI for review.
- Ranking by a model. Ranking stays deterministic from card fields.
- Topic synthesis pages in the wiki (consensus, gaps across papers). That is
  the Week 7 memory decision.
- A vector database. The corpus is a few hundred to a few thousand
  abstracts; the repo's numpy `VectorStore` is enough. Qdrant is a Week 9
  deployment decision.
- Choosing an agent architecture. Whether ranking or query reformulation
  become an agent's job is the Week 5 decision.

Anti-goals (what would make this a failure even if it runs)

- Invented labels or invented user feedback. The ten questions and the
  Step 6 session must come from the real R&D researcher.
- Retrieval measured on the synthetic rows. Those were built to test the
  card generator, not to stand in for the literature.
- The ingestion eating the week so the comparison table is thin. The
  table is the graded part.
- Internal data or the customer brief leaving the machine or landing in git.
  `use_case/reference/` and `use_case/data/` stay gitignored.
- A new dependency pulled into the root environment that every notebook
  then pays for.

## 3. Constraints

- Budget: TC3 is scoped at six to eight hours. Ingestion is allowed about
  four more if it stays abstract-first and small. The PDF tier has a hard
  timebox (section 5.4).
- Repo rules: no new dependency without asking (docling is the one asked
  for here); prefer stdlib; comments explain why; helpers take keyword-only
  arguments; no AI attribution anywhere.
- Instructor rules for TC3: the student labels the questions, writes the
  retrieval code, the comparison and the decision rows; the assistant
  coaches. A wiki must exist before direct corpus interaction can be
  measured, and it needs an owner. Hybrid can score worse than its better
  parent. Provenance on every passage.
- OpenAlex: free, no key. The polite pool wants a `mailto` parameter; the
  user's personal address is not sent. Whether to use a project address is
  a builder question (section 6). Abstracts come as an inverted index and
  are sometimes missing, notably for some Elsevier journals. Relevance
  ranking is keyword based. Open-access PDF links are not always direct
  PDFs.
- Environment: Python 3.14 venv managed by uv, Windows. Docling 2.142
  resolves for this platform and brings torch 2.14, the same weight class as
  the existing `local` group. Hosted model through OpenRouter via litellm,
  as decided in Week 2. Embeddings: `helpers/embeddings.py` through the
  configured `EMBED_MODEL` on OpenRouter (a multilingual Qwen3 embedding
  model at the time of writing); its no-API fallback is the
  sentence-transformers path in the `local` group, not fastembed.
- Schema: `Request`/`Response` from Week 1 are implemented, not redesigned.
  The one permitted change is a `sources` field. A second request type for
  questions is a charter addition and is recorded as such.

## 4. What exists and is reused

- `01_Product_Engineering/challenge/schema.py`: the card schema and the
  `solve()` stub. `app.py`: the Gradio server with the
  `summarize_research_paper` API that streams a card from a prompt.
- `helpers/rag.py` (`load_jsonl_corpus`, `chunk`, `chunk_corpus`,
  `format_docs`), `helpers/vectorstore.py` (`VectorStore`, `Hit`),
  `helpers/embeddings.py` (`Embedder`), `helpers/llm.py`.
- Session 5 notebook functions: `tokenize`, `search_chunks` (BM25),
  `list_pages`, `grep_wiki`, `read_page`, `run_agent`, `score`. Session 6:
  `reciprocal_rank_fusion`.
- `use_case/CHARTER.md`, `decisions.md`, `stakeholders.md`,
  `evals/golden.jsonl`, `data/DATASHEET.md`.
- `pyproject.toml` already has the pattern for opt-in groups
  (`local`, `week3`, `harness`). The PDF tier follows it.

## 5. The design, as decided

### 5.1 Shape: a funnel, not a crawl

Per request a researcher gives a topic, optionally a focus question, a date
window and a research area. The pipeline runs these stages in order and each
stage sees fewer papers than the one before:

1. **Fetch** (free). Query OpenAlex `/works` with the topic, date window and
   `type:article` by default. Page through everything it returns up to a
   cap (the user's call: fetch everything, screen cheaply). Store raw
   metadata per work: OpenAlex id, DOI, title, year, type, source, cited-by
   count, retracted flag, authorships with institutions, open-access block,
   best open-access PDF url, abstract rebuilt from the inverted index when
   present.
2. **Tier** (free). Each paper gets exactly one tier:
   `metadata` (no abstract), `abstract` (abstract present), `pdf`
   (abstract present and an open PDF url that downloads as a PDF). Papers
   without an abstract are kept, flagged, and never carded; the list shows
   them so the researcher can chase them by hand. Retracted works are
   flagged and excluded from cards.
3. **Embed** (cents). Embed title plus abstract for every `abstract` and
   `pdf` tier paper with the repo `Embedder`, cached. Score similarity to
   the request focus. This is the first ranking signal and it is reused as
   the dense index for retrieval.
4. **Triage** (cheap model, about thirty output tokens per paper). For
   papers above a similarity floor, a small model reads title and abstract
   and returns relevance 1 to 3, a one-line reason, and whether it is a
   study at all. Fixed prompt prefix, prompt caching on.
5. **Card** (the Week 1 card, Sonnet class). Full bilingual card for the
   top N by triage then similarity. **N = 10 per request** (the assistant's
   recommendation, accepted): the number a researcher reads today. Any
   paper in the screened list can be carded on demand later.
6. **Enrich with full text** (docling, see 5.4). For carded papers in the
   `pdf` tier only, download the PDF, convert to Markdown, and card again
   from the full text so `sample_size`, `study_type` and `trust_warnings`
   come from the methods section rather than the abstract. The abstract
   card is kept until the full-text card succeeds.

Output of a run: a screened list (title, year, source, tier, triage score,
similarity, flags) and N cards. Both are written to the corpus (5.3).

**The seed run** (the assistant's call, so the corpus exists before the
researcher is involved). One request per research area in
`use_case/axis_assumptions.md` (roasting and coffee chemistry; green coffee
processing and fermentation; sustainability and certification; agronomy,
varieties and climate; extraction and brewing; health and nutrition;
packaging and shelf life; sensory and consumer), articles only, published
from 2024-01-01, capped at 300 works per area, deduplicated by work id. That
gives at most about 2,400 papers and in practice fewer, which the numpy
store and a per-area wiki index handle without strain. The seed topics are
read back to the researcher in the same message that asks for the ten
questions, so the questions land inside the corpus; any area the researcher
adds is fetched the same way before labelling starts.

**Fetch once, then update** (the user's requirement). The seed run is done
once. Later runs, for example monthly, fetch the same areas with
`from_publication_date` set to three months before the previous run and
merge by work id: rows already present are left untouched, new ids go
through tier, embed and triage and are appended. Every row records
`publication_date` from OpenAlex and `first_seen`, the date the pipeline
first stored it. The three-month overlap exists because OpenAlex's
"created since" and "updated since" filters are paid (verified 2026-10-27:
the API answers "Plan upgrade required"), while filtering by publication
date is free; papers that OpenAlex indexes late with an earlier
publication date are caught by the overlap, and anything older than that is
accepted as missed. The cost of an update is proportional to the new papers
only, because embeddings are cached and carded rows are never re-carded.

**Latest-only views.** The screened list, the wiki index and the question
endpoint all accept a date filter on `publication_date` and on
`first_seen`, so "papers from the last two months" and "papers that
appeared since my last check" are both one filter away, with no model call.
For the comparison, the retrieval tools pass the same filter through to
the vector store's `where` argument and the BM25 and wiki tools, so a
question about recent work can be restricted before retrieval rather than
after.

Cost expectation, from Week 2 measurements (about $0.016 and 12 s per card):
a 200-paper request costs under $0.20 for embedding and triage and about
$0.16 for ten cards. Carding all 200 would be about $3.20, which is why the
funnel exists. Numbers are measured per run and written to the datasheet.

### 5.2 The card stays a separate tool

`summarize_research_paper` keeps working on pasted text. The pipeline calls
the same card function with provenance attached: `openalex_id`, `doi`,
`tier`, `fetched_at`. The `abstract_only` trust warning that already exists
is set whenever the tier is `abstract`. Keeping one card function is the
Week 1 decision (pipeline of steps around one function) and keeps the
Week 2 goldens valid.

### 5.3 Corpus and ids

- The system of record is one SQLite file under `use_case/data/`
  (gitignored), through the standard library's `sqlite3`, so no new
  dependency. The user asked for it; the assistant agrees because the work
  id as primary key makes the update diff an insert-or-ignore, writes are
  atomic, filters are indexed, and the file mounts into Docker as is.
  Tables: `works` (one row per paper: OpenAlex metadata, abstract, tier,
  `publication_date`, `first_seen`, flags), `cards` (one row per work id
  and version: the card as JSON validated by the pydantic schema, plus
  schema version, model, tier used, cost, timestamp), `runs` (one row per
  fetch or update: request, filters, counts per tier, tokens, cost) and
  `fulltext` (docling Markdown per work when the PDF tier succeeds). Card
  fields get their own column only when something filters on them. The
  record id is the OpenAlex work id (`W…`). It is stable, public and
  resolvable, and it is what `sources` cites.
- Everything else is a view rebuilt from the database: a JSONL export for
  the repo helpers and Session 5's tools, the chunk set (one per paper from
  abstract and card fields, in English and Italian, plus full-text chunks
  for `pdf` tier papers, every chunk tagged with record id, tier and
  language), the vector store and the wiki. Tagging lets the comparison be
  run with and without full text.
- Noted, not decided: SQLite's FTS5 extension has its own BM25 ranking.
  The comparison runs on Session 5's code; if a lexical technique wins, the
  production endpoint may use FTS5 instead of adding `rank-bm25` to the
  app. That choice is made when the winner is known.
- A vector store on disk (numpy `.npy` plus `.jsonl`) built from the same
  embeddings as stage 3. No vector database this week.
- A wiki rendered from the rows: one Markdown page per paper with fixed
  headings (Title, Metadata, Abstract, Card, Trust, Full text when present),
  file name equal to the record id, plus an index page listing every paper
  by research area and year. The wiki is a render, regenerated from the
  rows, never hand edited. It exists so direct corpus interaction can be
  measured fairly. The owner question goes in Step 5.

### 5.4 The PDF tier with docling

The user asked to enable docling this week. The assistant's recommendation,
accepted into this design, is yes under four conditions:

- **Opt-in dependency group.** `pdf = ["docling>=2.142"]` in the root
  `pyproject.toml`, installed with `uv sync --group pdf`, like `local`. The
  app and notebooks do not import docling unless the group is present; the
  pipeline degrades to the abstract tier when the import fails and says so.
- **Only for carded papers.** At most N PDFs per request, never the whole
  fetch.
- **Fast settings.** OCR off, table structure on, page images off. Scanned
  PDFs are out of scope; a conversion that yields near-empty text is
  flagged and the abstract card stands.
- **Hard timebox of two hours.** If PDF download and conversion do not work
  end to end on three real papers within two hours of building, the tier
  ships as a stub that records the PDF url and the reason, and the work moves
  to the next week. The rest of the design does not depend on it.

Known risks the builder handles: publisher pages returning HTML or 403 for
the open-access url (check the content type, try `best_oa_location` first
and the repository copy second, give up quietly); first-run model downloads
for docling layout models; conversion time of seconds to tens of seconds per
paper on CPU.

### 5.5 Question answering endpoint

A second API on the same Gradio server, next to the card API:
`ask_research_corpus`. Input: a question, optional research area and date
filters. Output: answer text, `sources` as a list of record ids with title
and DOI, a `declined` flag with a reason when the corpus does not support an
answer, and the trace (calls, evidence read, latency, stop reason). Decline
behaviour: when no retrieved evidence passes the technique's threshold, or
when the question is outside the corpus (the `decline` kind in the labels),
the endpoint answers that it cannot ground an answer and lists what it looked
at.

`solve()` from Week 1 is implemented as the card function. The question
type is added to the charter's "first product" table as the Week 3 addition,
with one `decisions.md` line saying why: the challenge's `sources` field
belongs to an answer, and the card schema has no question to answer.

### 5.6 The comparison (the graded part)

- **Labels.** Ten real questions from the R&D researcher, in
  `use_case/evals/retrieval.jsonl` with the required shape: question, gold
  record ids, kind (`lookup`, `multi-hop`, `decline`). The assistant does
  not write these. Gold ids are chosen by the researcher against the
  screened list and the wiki, with the user's help.
  Two further fields, because Session 5's `score` needs them (the
  assistant's call): `expected_terms`, the words an acceptable answer must
  contain, and `must_decline`, true when kind is `decline`. The researcher
  is asked for each question together with the answer they would accept
  in one sentence; the user lifts the terms from that sentence, so the
  terms stay the researcher's words. Citation credit is a substring check
  for the record id, so wiki file names are the W-ids and every technique's
  prompt instructs the model to cite them literally.
- **Techniques.** At least three, run through Session 5's `run_agent` and
  `score` unchanged:
  1. Agentic retrieval with BM25 `search_chunks` over the chunk set.
  2. Direct corpus interaction with `list_pages`, `grep_wiki`, `read_page`
     over the rendered wiki.
  3. Dense retrieval over the vector store, and hybrid (BM25 plus dense
     with reciprocal rank fusion). A cross-encoder reranker over the top
     thirty BM25 hits is the fourth run if time allows, because the
     instructor rules call it the highest-value third technique.
- **Columns.** Pass rate, citation rate, calls, evidence read, latency,
  stop reason, for each technique, with the settings (chunk size, k,
  embedding model) stated next to the table.
- **Decision.** The `decisions.md` Week 3 row filled by the user from the
  table: decision, rejected, why, what would change their mind. The four
  non-text answers and the charter's Week 3 row likewise.

### 5.7 Where the code lives and runs

The assistant's call, following the Week 2 precedent where the generator
imported `helpers` and the Week 1 schema from the root environment:

- The ingestion pipeline, the wiki render, the index build and the
  comparison live in `03_Retrieval/challenge/` and run from the root
  environment with the `week3` group (`rank-bm25`, `pandas`) and, for the
  PDF tier, the `pdf` group. Corpus rows, raw OpenAlex cache, wiki and
  vector store are written under `use_case/data/` (gitignored).
- The question endpoint is added to the Week 1 app in
  `01_Product_Engineering/challenge/`, which has its own environment and
  Dockerfile. The app ships only the technique the comparison chose and
  loads a prebuilt index from a directory passed by environment variable,
  mounted into the container at run time. The app never builds the index
  and never calls OpenAlex. Which packages that adds to the app's own
  `pyproject.toml` depends on the winner (numpy for dense, `rank-bm25` for
  BM25, both for hybrid) and is a question for the user (section 7).

### 5.8 Order of work

A. Ingestion to the abstract tier, corpus rows, wiki render, vector store.
B. Labels: the researcher's ten questions against the real corpus.
C. The three techniques and the table.
D. The endpoint with sources and decline.
E. The PDF tier under its timebox, then re-run the table with full-text
   chunks included to see whether it changes the winner.
F. Step 6 session, Step 7 lines, Loom, Maven post.

B cannot start before A produces a list the researcher can read. The
request for the researcher's time goes out on the day A starts.

## 6. What is left to the builder

- OpenAlex query construction (search field vs. filter on title and
  abstract, per-page size, the fetch cap, the politeness `mailto`).
- Abstract reconstruction from the inverted index and its edge cases.
- The similarity floor for triage and the triage prompt wording.
- Chunk size and overlap per tier; k per technique; which fastembed or
  API embedding model, recorded next to the table.
- Wiki page template and index layout, within the fixed headings above.
- Where the raw OpenAlex JSON is cached and how long it is trusted.
- How the trace is attached to the endpoint response without changing the
  card schema.
- Tests: schema round trips, tiering on recorded OpenAlex samples, abstract
  reconstruction, decline path on an empty corpus. Network calls mocked
  with recorded fixtures in the repo (metadata only, no full texts).

## 7. Questions raised by the builder check, and the user's answers

Answered 2026-10-27.

1. **Language of questions, expected terms and answers.** The team works
   in Italian, the abstracts are English, the card is bilingual. BM25 and
   `grep_wiki` over English text score nothing against an Italian question,
   while the configured embedding model is multilingual, so the choice
   tilts the comparison before it is run. **Decided:** questions in the
   language the researcher writes them; the Italian card fields (summary
   and notes) go in the chunks and wiki pages next to the English abstract
   so lexical techniques have Italian text to match; the answer is in the
   language of the question; expected terms in that same language.
   Known limit: papers that were never carded are searchable in English
   only.
2. **Contingency if the researcher's questions do not arrive in the
   week.** **Decided:** the request goes out on the day the seed run
   starts. If it is not answered in time, the user drafts ten questions
   from real past requests (the TC3 README allows questions from a ticket
   or chat log), including at least one the corpus cannot answer, labels
   gold ids provisionally, runs the comparison, and has the researcher
   confirm or correct each label in the Step 6 session. The table is re-run
   if labels change and the decisions row states which labels the
   researcher confirmed.
3. **Dependencies in the Week 1 app.** Serving the question endpoint from
   the Docker image needs the winning technique's packages in the app's
   own `pyproject.toml`. **Decided:** add only what the winning technique
   needs, after the comparison picks it (numpy for dense, `rank-bm25` or
   SQLite FTS5 for lexical, see 5.3).

## 8. Builder check results

A reviewer read the document as a builder who could not ask questions and
raised five points. Two of them, language and the labels contingency, plus
the app dependency question that follows from the code layout, were put to
the user and are answered in section 7. The other three were settled in
the document as the assistant's calls:

- Seed corpus: eight research areas from the axis assumptions, articles
  from 2024-01-01, 300 per area (section 5.1).
- Label file carries `expected_terms` and `must_decline` so Session 5's
  `score` runs unchanged; terms come from the researcher's one-sentence
  answers; citations are literal W-ids (section 5.6).
- Code layout: pipeline and comparison in `03_Retrieval/challenge/` on the
  root environment; the app serves only the chosen technique from a
  prebuilt, mounted index (section 5.7).

One factual correction from the review: the repo embedder's local fallback
is sentence-transformers, not fastembed (section 3).
