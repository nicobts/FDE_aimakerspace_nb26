# Decision log

One row per architectural decision, with the option you rejected and why.

> **Week 5 asks you to defend your agent architecture against the alternatives.**
> **Week 10's handoff doc is largely this file.** Both are much easier if you
> wrote the reasoning down while you still remembered it.

A decision without a rejected alternative is not a decision, it is a default.
If you cannot name what you did not do, you did not choose.

| Week | Decision | What you rejected | Why | What would change your mind |
| --- | --- | --- | --- | --- |
| 1 | Start as a pipeline of functions, not an agent. Week 1 is one function: one document in, one article card out. The end goal is the full solution for the customer (sweep the sources, card every document, rank, store, weekly report, and conversational retrieval over the papers), built by putting steps around this same function. | A multi-agent architecture from day one, with one agent each for search, screening, comparison, translation and packaging, as the original brief proposes. | On the four questions the full solution scores 1 to 2: it must call out to search and a database, but the order of steps is fixed and can be drawn in advance, and a card is either accepted or flagged for a human. A fixed pipeline gives a known cost per document and outputs I can score against the goldens. | Evidence that fixed steps fail on real requests: for example the sweep missing relevant papers unless the search is reformulated per topic, or chat questions that need several retrieval steps a fixed flow cannot plan. |
| 2 | **Model/endpoint for synthetic data: hosted `claude-sonnet-5` through OpenRouter**, at temperature 0.9 and top-p 0.95. | Local `qwen2.5:7b` on Ollama, on the laptop's RTX 4060 (8 GB VRAM). | On a 3-combination trial the hosted model returned 6 of 6 schema-valid rows at 39.8 s per call, 27,621 tokens (*measured*). The local model returned 0 of 6 valid at its default context, because the reply was cut off mid-JSON, and 2 of 6 valid with `num_ctx` 16384, at 31 s per call and 12,374 tokens (*measured*). Its full run would therefore yield about a third of the rows. Price on OpenRouter: $2.00 per 1M input tokens and $10.00 per 1M output tokens (*looked up*, 2026-10-21). The full 60-combination run used 304,973 input and 243,523 output tokens in 2,490 s, 41.5 s per call (*measured*), so about $3.05 (*measured* tokens × *looked up* prices); 118 of 120 rows were schema-valid (*measured*). The local model has no per-token price, only the laptop's time. **Constraint:** the submission deadline left no time to tune a local model. **Constraint, which allows hosted:** the inputs are generated from public journal abstracts and a written description, so nothing internal leaves the network. **Preference:** the hosted model follows the long JSON schema without extra prompt work. | Real R&D documents or reading notes becoming the seed: those must not leave the network, and the local model becomes the only option. Also a local model, larger or tuned, reaching at least 5 of 6 valid on the same trial. |
| 2 | **Dedupe threshold 0.7** (character n-gram Jaccard). | 0.5, which would also drop rows that share the same template wording ("This study investigated…") but describe different studies, and 0.9, which keeps near-paraphrases. | Rows built from the same combination share a lot of boilerplate. 0.7 dropped 0 of 6 rows in the hosted trial, 1 of 6 in the local one, and 0 of 120 in the full hosted run (*measured*). In the full run the threshold did no work: either the rows really are distinct, or 0.7 is too high to catch paraphrased studies. **Preference**, not a constraint. | Reading the most similar kept pairs, since nothing was dropped: if they describe the same study in different words, I would lower the threshold. If dropped pairs describe different studies (different compound, origin or result), I would raise the threshold. If kept rows differ only in numbers or wording, I would lower it. |
| 2 | **What the Step 6 feedback changed: the review plan, not the axes.** The axes stay as they are, because R&D agreed with them. The reviewer is no longer R&D alone: each research area needs confirmation from the SME who owns it. | Treating R&D's agreement as confirmation of the data and the labels. | R&D said they work across all departments, and that the information and processes belong to the SMEs in those departments. A researcher agreeing with the axes does not confirm, for example, that a packaging or processing trust label is right. **Constraint:** the information owners decide what is correct. | The SMEs' review of 20 rows: if they add document types or areas that are not in the axes, the research_area axis grows and the data is regenerated. |
| 3 | **Retrieval: hybrid (BM25 + dense, reciprocal rank fusion, k = 60), served as a fixed endpoint, `ask_research_corpus`**: top 5 chunks, a decline gate at dense cosine 0.45, one answer call, and only cited ids that were retrieved count as sources. Dense is plain NumPy cosine over 2,398 stored vectors, no vector database. Also: `solve()` implemented on the unchanged card contract, plus a new `CorpusAnswer` model for this endpoint (charter updated). | Measured on 13 labelled questions with local `qwen3.5:9b` (`03_Retrieval/challenge/results.md`): the **BM25 agent** (10 of 13 pass, all gold cited 9 of 12), the **dense agent** (8 of 13), the **wiki / direct corpus interaction agent** (1 of 13), and the **hybrid agent** (11 of 13), which matched the endpoint but needs a model that decides to search. Also rejected: a vector database, and adding fields to the card `Response`. | Ranking alone: all gold papers in the top 5 for 11 of 12 questions with hybrid, 10 with dense, 9 with BM25 (*measured*, same result with OpenRouter and local query vectors). Our questions mix exact names and numbers (Castillo, Caturra, 400 mg, 250 days) with paraphrase and an Italian question, so neither parent alone covers them. The endpoint passes 11 of 13 with **one** model call and cites every gold paper in 10 of 12; it answered the Italian question that every agent skipped searching. **Auditability:** every answer carries `sources` and `retrieved`, so a wrong answer can be traced to a passage. **Cost:** 788,540 embedding tokens to index the corpus (*measured*), 700 s on the laptop GPU. **Constraint:** the corpus is public papers, so a hosted embedding model is allowed; the same model runs locally when it is not. | (1) If the team's real questions are mostly exact identifiers (variety, compound or standard names), I would ship BM25 alone, with no embedding model to approve: switch if BM25's all-gold@5 comes within one question of hybrid on their labels. (2) If a question needs "every paper that mentions X", top-k cannot answer it and I would add the wiki's `grep_wiki` as a second tool, which needs a stronger model than 9B (it scored 9 of 13 with Claude Sonnet in a partial run, 1 of 13 with Qwen 9B). (3) If the endpoint's pass rate on the team's own questions drops below the BM25 agent's, I would move to an agentic loop with a stronger model. (4) If the corpus passes about 100,000 chunks or gets per-user access levels, a vector database with metadata filtering before ranking. |
| 3 | **Passage cut raised from 1,000 to 2,500 characters** per hit shown to the model. | Session 5's 1,000, and chunking abstracts into smaller pieces. | 2,179 of 2,398 chunks are longer than 1,000 characters (median 1,582, 90th percentile 2,146), and abstracts put results last: the model cited the right paper and said the results were cut off. On the same six questions the BM25 agent went from 1 to 3 passes (*measured*). Keeping one chunk per abstract keeps one id per finding. | Answer latency or the model's context becoming the budget limit: then cut abstracts at sentence boundaries into two chunks rather than truncating. |
| 3 | <!-- TC3 Step 6: one thing the researcher's feedback changed (a question added to retrieval.jsonl, the 0.45 gate moved, a record fixed), or 'nothing changed' and why --> | <!-- --> | <!-- --> | <!-- --> |
| 5 | <!-- agent architecture --> | <!-- --> | <!-- --> | <!-- --> |
| 6 | <!-- guardrail level --> | <!-- --> | <!-- --> | <!-- --> |
| 7 | <!-- memory type --> | <!-- --> | <!-- --> | <!-- --> |
| 8 | <!-- model --> | <!-- --> | <!-- --> | <!-- --> |

**Week 1, the strongest case for the opposite verdict.** The customer asked for agents, and the
real work is open-ended: a researcher's request can be about any topic, the right sources differ
per topic, and a good literature search reformulates itself when the first results are poor. A
fixed pipeline may only automate the easy part. I would switch if, with retrieval in place, the
pipeline's results on real requests were clearly worse than what a researcher finds by hand.

**Week 3, the non-text content in the corpus.** The corpus is 2,425 open-access papers from
OpenAlex; what is indexed is their text (abstracts, generated cards, and the few full texts
converted from PDF).

1. **Visual, or text rendered as pixels?** The papers are born-digital: the prose and most tables
   are real text, extractable without OCR. What is genuinely visual is the figures: chromatograms,
   sensory spider charts, roast curves, maps of growing areas. Today none of it is indexed.
2. **Does the number live only in the pixels?** Sometimes: a sensory score read off a spider chart
   or a shelf-life curve's end point may not be stated in the text. Then the caption finds the
   figure (text retrieval over captions, the cheapest of the three strategies), a vision model
   reads it, and the paper's own text or tables check the reading, because a misread axis is a
   silent wrong number. Out of scope until a researcher asks a question only a chart answers.
3. **Descriptions, or one parse per image?** We have descriptions for free: figure captions. Docling
   extracts them with the full text, measured at 96 s per paper on this laptop (model download
   included), so it runs locally as a batch job, and only for papers that get a card, not for all
   2,425.
4. **Video or audio?** None in the corpus. The first to arrive would be recorded conference talks or
   webinars; for "what did they find" questions the transcript alone would answer, because the
   slides repeat the paper.

---

The last column is the one people skip and the one people ask about. "We chose
dense retrieval; we would switch to hybrid if exact-match queries went above ~20%
of traffic" is an engineering position. "We chose dense retrieval" is a
preference.
