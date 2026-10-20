# Datasheet

This file is committed; the data itself (`synthetic_v1.jsonl`) is not.

## What this data is

**Generated on:** 2026-10-21
**Generated from:** the `Request`/`Response` schema in
`01_Product_Engineering/challenge/schema.py`, the axes in
`02_Open_Weights/challenge/axes.py` (a written description of what varies), and
three goldens as format examples (goldens 5, 4 and 1). The goldens are public
journal abstracts. No internal document, note or record of the R&D team was
used.
**Kind:** prototyping data. The inputs look like the documents the service will
receive; the outputs are labels written by the generating model, and no
researcher has verified them. It is not backtesting data.
**Rows:** 111 (65 cards, 46 declines): 118 schema-valid, minus 7 removed after
reading

### Run settings and counts

| | |
| --- | --- |
| Model | `openrouter/anthropic/claude-sonnet-5` (hosted, via OpenRouter) |
| Temperature / top-p | 0.9 / 0.95 |
| Dedupe | character n-gram Jaccard, threshold 0.7 |
| Rows asked per combination | 2 (60 combinations, 120 rows asked) |
| Generated | 120 (0 unparseable lines) |
| After dedupe | 120 (dedupe dropped none) |
| Schema-valid | 118 |
| Removed after reading | 7, leaving 111 (see the leakage check) |
| Dead combinations | 1 of 60: journal abstract × packaging and shelf life × weak in a way that is easy to miss. Both rows failed validation, so the hidden-weakness case has no abstract-format example on packaging. |
| Cost | 60 calls, 548,496 tokens (304,973 in / 243,523 out), 2,490 s (41.5 s per call), about $3.05 at OpenRouter list price |
| Reproduce | `uv run python 02_Open_Weights/challenge/generate.py` |

**What the labels show** (the 111 kept rows). Trust levels are 20 high, 42 low
and only 3 medium among the 65 cards: the generator labelled almost every
"weak but easy to miss" study low, not medium. Affiliation is unknown on 25
cards, company on 23, university or public institute on 13, and mixed on 4.
In the raw run, one of the 48 decline rows came back as a card.

"Schema-valid" means the input parses as a `Request`, the output parses as a
`Response`, and a decline has a reason and no category or trust level (the
`validate()` function in `generate.py`).

## Variation axes

3 axes, 4 × 3 × 5 = 60 combinations. Values are summarised; the full text sent
to the model is in `axes.py`. The axes come from `use_case/axis_assumptions.md`,
informally confirmed by one R&D researcher.

| Axis | Values | Why |
| --- | --- | --- |
| text_type | journal abstract (150–250 words); 600–900-word methods and results excerpt; preprint abstract, not peer-reviewed; supplier technical note, partly marketing | Abstracts dominate what arrives, but full text, preprints and supplier notes arrive too; four of the five goldens are abstracts only. |
| research_area | roasting chemistry; green coffee processing; packaging and shelf life | The most frequent requests. Packaging has no schema category, so it tests whether `other` is used honestly. |
| outcome | solid study, high trust; visibly weak study; weak in a way that is easy to miss (lab scale, cell or animal only, single origin, industry funded); decline: coffee only mentioned in passing; decline: text truncated or under 60 words | The four things the service must do: a card, a card with a visible caveat, a card whose weakness is hidden, or a decline. |

## What it can validate

- That the service returns a schema-valid card, or a valid decline, for each
  of the four text types and three research areas above.
- That the trust warnings added in TC2 (`lab_scale_only`,
  `in_vitro_or_animal_only`, `industry_funded`, `single_origin_or_batch`,
  `no_statistics`, `abstract_only`) and the `affiliation` field get populated at
  all, when the text plainly contains the signal.
- That the two hard declines (coffee mentioned in passing, truncated text) are
  attempted, rather than turned into a card.
- Plumbing for later weeks: retrieval in Week 3 has a corpus to index, and
  the pipeline can be exercised end to end without real documents.

## What it cannot validate

- **Whether the trust level is right.** The same model wrote the paper and its
  label, following `TRUST_RULES`. Agreement with these rows measures
  consistency with my own rules, not whether an R&D researcher would trust the
  study. The weaknesses are planted, so they are always findable in the text;
  in a real paper the missing control or the funding line may be absent from
  the abstract, or buried in a footnote.
- **The medium trust level.** Only 3 of 65 cards are medium. The data cannot
  show whether the service separates medium from low, and that is the line
  researchers care about most: a sound study with one limitation.
- **The real mix of documents.** Every combination is generated equally, so
  declines are 2 of 5 outcomes and supplier notes 1 of 4 text types. The real
  share of declines, preprints and supplier notes is unknown. Any accuracy
  number on this file is weighted by my grid, not by what the team receives.
- **Real document noise.** No PDF extraction artifacts, broken columns, tables,
  figure captions, reference lists, full papers longer than 900 words, or
  papers in languages other than English. These are the inputs most likely to
  break the service and none are here.
- **Three of the six categories.** `agronomy`, `health` and `sustainability`
  are not in the research_area axis (only golden 2–4 cover health and
  agronomy), so category accuracy on them is untested.
- **Affiliation in practice.** The generated texts tend to state who did the
  work. Real abstracts often omit affiliation and funding, so `unknown` will be
  far more common than here, and `industry_funded` harder to detect.
- **Sample size on complex designs.** The schema stores one integer. Real lab
  studies describe designs such as "6 origins × 3 roast degrees × 3
  replicates"; the first trial produced exactly that as prose and every row
  failed. The rows here were forced into an integer, which hides the problem
  rather than solving it.
- **The Italian text.** `summary_it` and `notes_it` are present but nobody has
  checked their quality or terminology.

## What it must never be compared against

Real ground truth is the judgement of the subject matter experts who own each
area: the R&D researchers for the science, and the experts in the departments
R&D works with (processing, packaging, and the other business areas the
research touches) for whether a finding holds in their process. R&D said
plainly that confirmation must come from those owners, not from R&D alone.
None of them has reviewed the rows yet, and I cannot reach their reading notes
or reviews. The five goldens in `use_case/evals/golden.jsonl` are
the only labelled examples, and Week 4 scores against them, never against this
file. A high score on these synthetic rows must not be reported as accuracy.

## Leakage check — outward (what left)

Ticked by me after reading 50 of the 111 rows, not by the script. The automated
regex leak check reported: 1 hit, "BACKGROUND AND AIMS", a structured-abstract heading shared with a golden, not a name or identifier.

- [x] No real record was used as a seed.
- [x] No real entity names, IDs, or identifiers appear.
- [x] No distinctive internal formats that would identify the firm.
- [x] Rare categories were generated, not copied.

**Rows removed after reading, and why.** I read 50 rows, 10 per outcome, and
removed 7 (row numbers in the raw run):

- Row 49: names an Italian roaster and a batch code in an internal-looking
  format, too close to the customer's own world to publish.
- Row 32: the source is an "internal technical bulletin", a format that looks
  like the customer's own documents; the text type asked for a peer-reviewed
  excerpt.
- Row 59: high trust on a preprint that is not peer reviewed, against
  `TRUST_RULES`.
- Row 80: high trust on a preprint that is not peer reviewed, with a "zero aroma
  loss" headline, against `TRUST_RULES`.
- Row 99: high trust on a supplier's own industry-funded internal trial,
  against `TRUST_RULES`.
- Row 94: wrong category; a green coffee extract sold for antioxidant
  protection is health, not roasting.
- Row 66: would never happen; the title is about coffee roasting and the text is
  about melatonin in students.

What reading showed beyond the removals: three of the seven are high trust
against the rules, so the generator does not always follow `TRUST_RULES` and
the service's output will need the same check. High trust with one
single-batch warning (rows 2, 21, 50) was kept but is borderline, a question
for the SMEs. All 20 decline rows read were correct. Supplier and company names
are invented; row 49 was the only one that read like a real company.

## Leakage check — inward (what the eval shares with the training data)

**Are the goldens disjoint from anything the system was, or will be, tuned on?**
No, they overlap. Goldens 1, 4 and 5 were the format examples in the
generation prompt, so the synthetic rows were written by imitating them. The
golden labels were also revised in TC2 against the same `TRUST_RULES` the
generator was given. If these rows are later used for
prompt examples or the Week 8 fine-tune, a Week 4 score on the goldens will
partly measure self-consistency. Golden 2 and golden 3 were not shown to the
generator and are the cleaner test.

**Overlap between `golden.jsonl` and this file, by the dedupe measure:**
0 rows at threshold 0.7. The closest synthetic input to any golden scores 0.22.
