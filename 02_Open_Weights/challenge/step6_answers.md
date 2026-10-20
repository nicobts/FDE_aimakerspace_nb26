# Step 6 — Show it to someone who knows the real data

**Status: first iteration, agreed by R&D.** The R&D team reviewed the answers
below and agreed with them. They also said the next iteration will bring
better feedback and more precise details on the various aspects, including
those tied to the company's different verticals, with SMEs from those
departments involved.

**Who:** the customer's R&D team (researchers who will use the cards), then
the subject matter experts who own each research area.
**What they saw:** the axes, `use_case/axis_assumptions.md`, 20 rows of
`synthetic_v1.jsonl` and `use_case/data/DATASHEET.md`.

**Already said by R&D:** they agree with the axes and the assumptions, but
confirmed, high-quality answers on the data must come from the SMEs who own the
information and the processes. The research covers many parts of the business,
and R&D works horizontally with all the departments.

## 1. Which of these would never actually happen?

- Supplier technical notes written like journal papers. Real supplier notes
  rarely give a methods section or sample sizes; they read more like brochures.
- Weaknesses that are too easy to spot. In the generated rows the funding line
  or the lab-scale setup is stated in the text; in real abstracts it is often
  missing or in a footnote.
- Abstracts that state affiliation and funding. Most real abstracts do not, so
  `affiliation` would mostly be `unknown`.
- A single exact sample size on lab studies. Real roasting studies describe a
  design, such as 3 origins × 4 roast levels × triplicate.
- Cleanly truncated texts. A real truncated input comes from a bad PDF
  extraction or a paywall page, not from a sentence that simply stops.

## 2. What comes in that is not here at all?

- Research areas owned by other departments: sustainability and
  certifications, agronomy and climate, regulatory (acrylamide limits,
  contaminants, novel food rules), sensory and consumer studies, equipment and
  process engineering.
- Formats: full PDFs with tables and references, patents, conference posters,
  trade-press articles, regulatory documents, and papers in Italian,
  Portuguese or Spanish from producing countries.
- Internal context: whether a finding is relevant to the company's own
  process or product line. The relevance score cannot judge that without the
  business knowledge the SMEs hold.

## 3. If this were public, what would worry you?

- The research areas could show which topics the company is investigating,
  for example a packaging change or a new process.
- The `focus` questions in the inputs could read like the company's R&D
  priorities.
- Trust labels on real, named papers or suppliers could look like the company
  publicly judging a supplier's or partner's work.
- The synthetic texts themselves are invented and based on public abstracts.

## What I expected vs what they said

No differences in this iteration: R&D agreed with the answers as written. The
differences are expected in the second iteration, from the SMEs of each
vertical.

## What changes

The review plan, not the axes. R&D's agreement does not count as confirmation
of the data and the labels: each research area now needs its owning SME. If
the SMEs add document types or areas, the research_area axis grows and the data
is regenerated. Same line as the Week 2 Step 6 row in `use_case/decisions.md`.
