# Project charter

<!--
  Fill this in during TC1 Step 4, from your Getting to Concreteness form.
  Later weeks' notebooks read this file and stop if it is still the template.
  That is on purpose.
-->

**Department:** R&D 

**Working title:** Research digest: one article card per publication

---

## The problem

**Who has it?** One real role, not a department.

A researcher in the R&D team of an Italian coffee company. Team of 5 generally has the responsibility to scout and try to collect news and updates and write reports.

**What are they trying to do?**

Stay on top of what is being published worldwide on coffee research and innovation, and decide quickly whether a given study matters for a project they are working on.

**How do they handle it today?**

Manually. They search Google Scholar, PubMed and ResearchGate, collect PDFs locally, read each paper in English, compare studies in a spreadsheet, and rewrite the findings in Italian in a slide deck for colleagues.

**What does that cost — time, money, risk, or relationships?**

Several person-hours per request, and requests are constant. 30 to 60 min per paper depending on the reviewer or the complexity of the document, language barrier is an issue here , nomber of papers reviewed per month can variate a lot but generally we can consider 10 reviewed papers per request, so 5 to 10 hours per request. The result depends on who did the reading, so it is imprecise and hard to compare. Because the papers are in English and the team works in Italian, relevant research is read late or not at all, and a weak study can be passed on without its limits being noticed.

**The problem in one sentence. No solution in it.**

R&D researchers cannot keep up with the volume of English-language coffee research, so deciding whether a study is relevant and reliable takes hours of manual reading and translation per request.

---

## Success

**What does the new world look like for that person?**

For each publication the researcher gets a short card in Italian and English: what the study is, what it found, how relevant it is to their topic, and how far it can be trusted. They read the full paper only when the card says it is worth it.

**How would the firm measure it? Which numbers should move?**

- Hours spent per research request go down.
- Time from a request to a first answer goes down.
- The number of studies screened per request goes up.
- Fewer weak studies reach a report without a caveat.

---

## The first product

**Your solution in one sentence.**

A service that takes the text of one publication and returns a structured article card with a bilingual summary, a relevance score and a trust level, or says that a researcher must read it. (pdf and artifact uploads is expected to be implmented later , instead of a copay/paste text)

**Input → Output.** Be specific enough that someone could build it wrong and you
would notice.

| | |
| --- | --- |
| **In** | The text of one paper or abstract in English (required). Optionally a title, the source, a focus topic or question, and the output languages wanted (English, Italian, or both; default both). |
| **Out** | One article card: category, relevance from 1 to 3, study type, sample size, main finding, a summary and reader notes in each requested language, a trust level (high, medium, low) with the warning signs found. Or `needs_human = true` with a reason and no card, when the text is not a study, is too short to judge, or is not about coffee. |

---

## Decisions made later

<!--
  Amended as the cohort goes. Keep the reasoning, not just the choice — Week 5
  asks you to defend your architecture against the options you rejected, and
  Week 10's handoff doc is largely this section.
-->

| Week | Decision | Why, and what you rejected |
| --- | --- | --- |
| 3 | Retrieval approach, and a second contract next to the card | The card contract (`Request` → `Response`) is unchanged and `solve()` now implements it. Asking a question of the whole corpus is a different In → Out, so it got its own model, `CorpusAnswer` in `schema.py`: In = a question in English or Italian; Out = an answer citing works as [W<id>], the `sources` it is grounded in, every id the model was shown (`retrieved`), or `needs_human = true` with a reason and no answer. Rejected: adding `answer` and `sources` to the card `Response`, which would make one model mean two things and leave most card fields empty on every answer. The technique and what it beat are in `decisions.md`, week 3. |
| 5 | Agent architecture | <!-- TC5 --> |
| 8 | Model | <!-- TC8 --> |
