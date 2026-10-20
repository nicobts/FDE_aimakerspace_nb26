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
