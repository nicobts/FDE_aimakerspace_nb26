# Stakeholders

Everyone you talk to about this project, from the first "where would this even
run?" to the final readout.

> **Week 10's technical challenge is a report to the people in this file.**
> You cannot write it later from memory. Add a row the day you have the
> conversation.

Use roles, not names. This is a public repo.

| Week | Who (role) | What you asked | What you learned | Follow-up |
| --- | --- | --- | --- | --- |
| 1 | Customer IT department | Where a containerised internal app would run, how users log in, how it reaches a model | A single VM on GCP behind Identity-Aware Proxy; model calls go through an AI gateway; image built from the repo for the test phase | Ask about general egress, the review needed before real users, and how secrets reach the VM |
| 1 | My CTO (supervises the development) | Who approves the deployment | I own the build; final approval is agreed with the customer | Confirm what the customer's approval consists of |
| 2 | Customer R&D team (researchers who will use the cards) | Whether the variation axes and the assumptions behind them (text types, research areas, trust problems, when to decline) match the documents they read. They reviewed the axes, `axis_assumptions.md` and the answers to the three Step 6 questions in `02_Open_Weights/challenge/step6_answers.md`. | They agree with the axes, the assumptions and the Step 6 answers. But R&D is only one part of the picture: the research covers many aspects of the company and the business, and R&D works horizontally with all the departments. Confirmed, high-quality answers on the data must come from the subject matter experts who own that information and those processes, not from R&D alone. | Second iteration requested by R&D: SMEs from the company's verticals review 20 rows and the three questions, for more precise details per vertical. Ask R&D which roles own each area. Until then, labels and trust levels count as unconfirmed. |
| 3 | <!-- TC3 Step 6: role of the researcher, e.g. 'Customer R&D researcher (extraction)' --> | <!-- They typed five questions of their own into ask_research_corpus; after each: would you act on it? does the named source convince you? what did you want to ask that you didn't? --> | <!-- What they said, in their words --> | <!-- The follow-up; their five questions go in use_case/evals/retrieval.jsonl as r01-r05 --> |
| 4 | <!-- TC4 Step 7: who watched the five-minute demo, by role --> | <!-- Asked: what would you do differently on Monday if this number is right? what would convince you it is wrong? what did you expect to see that you didn't? --> | <!-- What they said, in their words --> | <!-- Follow-up, and the decisions.md line it changed --> |
| 5 | Customer IT, and the data scientist assigned to work with me on the AI integration (we also work together on other use cases) | Shown in a remote meeting of more than 40 minutes: the current version, questions answered over the OpenAlex paper corpus on coffee topics. Asked: what would you do differently on Monday if this is right? what did I say that you did not believe? what is the worst thing this could do, from where you sit? | **Monday:** they want to try the tool themselves and to present it to the whole R&D team and to colleagues who touch R&D work; they already suggested further features. **Not believed:** the precision and reliability. Reading a research paper depends on the researcher and their experience, and they see that as a human task that is hard to reproduce with an agent or a pipeline. **Worst thing:** a model outside the EU being used. I offered local models only, or Vertex AI or OpenRouter restricted to EU-hosted models. **They also asked** whether the tool can be used over MCP from Microsoft Copilot, which they already use, so that it becomes a new tool in the chat they have and not one more interface; and whether this is the stack that will go to production, which I could not confirm. They mentioned an older ERP that has APIs but no MCP server. | In-person meeting at the customer the following Thursday, on this demo and the other open projects. I asked them to confirm which papers they care about and to send a complete list of example papers as the reference set. To do: verify whether this stack is suitable for production; evaluate a deployment in their infrastructure so they can try it; look at the ERP's existing APIs (a UTCP description or an MCP server around them). The EU-only model rule is the candidate for the Week 6 guardrail. Changed in `decisions.md`: Week 5 switch conditions 1 and 3. |

---

## Not everyone is an infrastructure contact

The useful list is wider than it first looks, and Week 10's report goes to all of
them:

- **The person with the problem** — the one from your charter. Have you shown
  them anything yet?
- **Whoever owns the data** you would need.
- **Whoever runs the platform** your app would deploy onto.
- **Whoever approves** a deployment, a spend, or a vendor.
- **Your own manager**, who will be asked whether this was worth the ten weeks.

If a week goes by with no conversation, add a row saying so and why. A visible
gap is more useful than a silent one.
