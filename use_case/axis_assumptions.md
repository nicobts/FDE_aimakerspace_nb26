# Input assumptions behind the TC2 axes

**Status: informally confirmed, 2026-10-20.** The answers below were drafted as assumptions and
then shown to a researcher on the R&D team in an informal conversation. She said they look right
and match what the team would answer. She agreed with the list as a whole and did not go item by
item, so no single frequency or ranking has been confirmed on its own. The variation axes are
built on these answers.

Limitation: she reviewed a list that was already filled in instead of answering blank questions,
which tends to produce agreement. If the full questionnaire comes back answered independently,
compare it line by line; every difference is a finding for the datasheet and may change an axis.

Sources for the assumptions: the charter, the internal use-case brief, the five goldens, and
general knowledge of coffee R&D. Nothing here comes from the firm's own request history.

## 1. What kinds of text arrive

| Text type | Assumed frequency | Confidence | Reasoning |
| --- | --- | --- | --- |
| Abstract only | **Most common** | High | Today's process starts from Scholar, PubMed and ResearchGate; four of five goldens are abstracts |
| Full journal article, review or meta-analysis | Often | Medium | Downloaded once the abstract looks promising |
| Preprint | Sometimes | Medium | The brief names non-peer-reviewed preprints as a risk |
| Supplier or equipment-maker technical paper | Sometimes | Low | Common in roasting and equipment work, outside academic search |
| Trade press | Sometimes | Low | Often where a request starts, less often what gets screened |
| Thesis, patent, conference abstract | Rarely | Low | |
| Not in English | Rarely, costly when it happens | Medium | Portuguese and Spanish (producing countries), some Chinese; the schema assumes English input |

## 2. Research areas

| Area | Assumed frequency | In the schema? |
| --- | --- | --- |
| Roasting and coffee chemistry | Often | `roasting` |
| Green coffee processing, fermentation | Often | `processing` |
| Sustainability and certification | Often | `sustainability` |
| Agronomy, varieties, climate | Sometimes | `agronomy` |
| Extraction and brewing | Sometimes | **No**, falls into `other` |
| Health and nutrition | Sometimes | `health` (two of five goldens, likely over-represented) |
| Packaging and shelf life | Sometimes | **No**, falls into `other` |
| Sensory and consumer | Sometimes | **No**, falls into `other` |

## 3. What makes a study hard to trust

- **Most common:** small sample (a few lab batches, pilot trials with around 20 people).
- **Easiest to miss:** lab conditions far from industrial practice; close second, cell or animal
  results presented as if they applied to people. **Neither is a `TrustWarning` in the schema.**
- Also expected: industry funding or conflict of interest; one origin presented as true for all coffee.

## 4. What should be declined (`needs_human = true`)

In assumed order of importance:

1. Mentions coffee only in passing (a real study where coffee is one variable among many).
2. Marketing material presented as a study, often a supplier paper.
3. Text too short or truncated.
4. Conflicting or ambiguous results. **Uncertain** whether the team wants a decline here or a card
   with a caveat; if a decline, the schema's "a weak study still gets a card" rule is wrong for it.

Rare but in scope: retracted papers, editorials and opinion pieces with no data.
"Not about coffee" is already covered by golden 5 and is the easy case.

## Schema gaps these assumptions expose

- Three likely research areas have no category.
- The two hardest-to-spot trust problems have no warning.
- Non-English input is out of contract today.
