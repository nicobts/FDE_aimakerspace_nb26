<div align="center">
  <img
    src="https://github.com/AI-Maker-Space/LLM-Dev-101/assets/37101144/d1343317-fa2f-41e1-8af1-1dbb18399719"
    width="200"
    alt="AI Makerspace logo"
  />
  <h1>Technical Challenge 5</h1>
  <p><strong>The refined demo, and an architecture you can defend with a second implementation you measured.</strong></p>
</div>

---

## Overview

> **Read first:** [`use_case/decisions.md`](../../use_case/decisions.md). This
> challenge fills in its architecture row. It starts with the questions from
> Session 9 that you could not answer.

Session 9 put your demo in front of a tough room, and one of its questions
was *"what did you reject?"* This challenge gets you a real answer. You
**build an alternative and measure it against what you have.**

Weeks 1–4 gave you an endpoint, data, retrieval and a number. This week your
architecture becomes a decision. A design review asks one question, and
"we use MCP" does not answer it:

> **"Why this way, and what would make you switch?"**

The second implementation is a few dozen lines. **The measurement and the
switch condition are the assignment.**

> 💡 **You already know enough to be dangerous!** In Session 10 you built the
> same capability six ways: a tool, a skill, a subagent, an MCP server, Code
> Mode, and UTCP. You put a counter on five of them that separates model calls
> from capability calls. You watched the tool loop's token cost climb with
> payload size while Code Mode stayed flat. Now you run that comparison on
> your own endpoint, at your own response size.

<table>
  <tr>
    <td width="120"><strong>Outcome</strong></td>
    <td>A second implementation of your endpoint, with both versions measured on model calls, capability calls, latency and tokens at your real response size. An architecture row in <code>use_case/decisions.md</code> with the closest reject and a switch condition. A refined five-minute demo that answers what the room asked.</td>
  </tr>
  <tr>
    <td><strong>Tools</strong></td>
    <td>LiteLLM, Gradio, and the <code>Meter</code> and capability counter from Session 10 (middleware on a FastMCP server, or the deep dive's counting wrapper). <code>fastmcp</code> or <code>mcp</code> 2.0+ only if the second way is an MCP server. Nothing else new.</td>
  </tr>
  <tr>
    <td><strong>Due</strong></td>
    <td>End of the week. Post your repo link in the Maven Community.</td>
  </tr>
  <tr>
    <td><strong>Before you start</strong></td>
    <td>Your TC3 endpoint running, your TC4 numbers, and the questions you wrote down during Session 9. If you did not write them down, Step 1 tells you what to do instead.</td>
  </tr>
</table>

---

<!-- deliverables:start -->
## 🏗️ Build | 🚢 Ship | 📤 Share

Three escalating bars. **Build** means it runs for you. **Ship** means someone
else can run it. **Share** means someone who is not you has an opinion about it.

### 🏗️ Build

A second implementation of your endpoint, in the way you judged second best,
measured against the first at your real response size. That measurement is
what lets you defend the decision.

Four questions are asked inside the Session 10 notebook as you work through
it. *They are not submitted and not graded.* They help you work out what the
challenge is going to ask you for.

| # | Question | Asked in |
| :---: | --- | --- |
| 1 | What your endpoint's dispatcher does today on a tool name it does not have, and which of the five failure rows a user of your app would meet first | S10 |
| 2 | Who outside your codebase would need to discover your capability in the next year (a named client), and what MCP buys you if the answer is nobody | S10 |
| 3 | How many bytes your endpoint really returns per call, how many calls a request needs, and where that puts you on the tool-loop slope | S10 |
| 4 | Which of the six ordering questions decides it for *your* endpoint, and the condition under which you would switch | S10 |

> **Jumping to one.** Open the notebook, then add the anchor to your browser's
> address bar, for example `#discuss-question-3`. It works once the notebook has finished loading.

### 🚢 Ship

This is the graded part. Every item comes from a numbered step in the technical
challenge, which has the full detail.

- [ ] **The room's questions written down** in `use_case/decisions.md`: the two you will fix, and the one you could not answer
- [ ] **A second implementation of your endpoint**, in the way you judged second best, running
- [ ] **Both implementations measured**: model calls, **capability calls**, latency and tokens, on the same two requests
- [ ] **The token measurement repeated at your endpoint's real response size**, with the size in bytes recorded
- [ ] `use_case/decisions.md` has the architecture row: decision, closest reject, why in terms of the six questions, and **switch condition**
- [ ] It still runs in Docker

### 📤 Share

- [ ] **The refined demo, shown to a real stakeholder**, with what changed after critique and what they asked, recorded in your own words. Graded
- [ ] **What you would swap to run this at work**: data, model or endpoint, and the approval you would need, as three lines in your README
- [ ] Your repo link posted in [our community on Maven](https://bit.ly/fde1-maven-community)
- [ ] Comments on at least two other students' submissions, after the deadline
<!-- deliverables:end -->

---

## 📖 Official documentation

Everything this challenge uses, from the people who maintain it.

| Tool | What you use it for here | Docs |
| --- | --- | --- |
| LiteLLM | `completion(tools=...)`, the model loop in every way that uses one | [docs.litellm.ai — function calling](https://docs.litellm.ai/docs/completion/function_call) |
| Gradio | the endpoint under test, and exposing it as an MCP server if that is your second way | [gradio.app — building an MCP server](https://www.gradio.app/guides/building-mcp-server-with-gradio) |
| MCP | the protocol, if the second way is a server something else has to discover | [modelcontextprotocol.io](https://modelcontextprotocol.io/docs/getting-started/intro) |
| FastMCP | the framework Session 10 builds all six ways on: a tool, a server, `mount`, `CodeMode`, `from_openapi` | [gofastmcp.com — tools](https://gofastmcp.com/servers/tools) |
| UTCP | the manifest, if your capability already exists as an HTTP API | [utcp.io](https://www.utcp.io/) |
| `helpers/tools.py` | `Toolbox`: dispatch where a tool failure is a message, not an exception | [`helpers/tools.py`](../../helpers/tools.py) |

---

## Setting Expectations

**Budget six to eight hours**, spread across the week. The second
implementation takes an evening. The measurement takes an hour. The decision
row takes thirty minutes, and it answers *"what did you reject?"*

| Step | What it is | Rough time |
| :---: | --- | --- |
| 1 | Write down what the room asked | 20 min |
| 2 | Pick the second-best way, and say why | 30 min |
| 3 | Build it | 2–3 hrs |
| 4 | Measure both, at demo scale | 45 min |
| 5 | Measure again at your real response size | 30 min |
| 6 | Write the decision, with the switch condition | 30 min |
| 7 | Refine the demo and show it to a real stakeholder | 45 min, plus their calendar |
| 8 | Share: bring it to work | 20 min |

> **Do Step 1 today, while you still remember what was asked.** The questions
> fade fast, and the ones you could not answer are why this challenge exists.
> Book Step 7's audience at the same time.

---

## What you are building

| File | Role |
| --- | --- |
| Your existing `@app.api` endpoint | Implementation one, the baseline. Usually a tool |
| A second implementation of the same endpoint | Skill, subagent, MCP server, Code Mode, or UTCP manifest, whichever Step 2 picks |
| `measure.py` (or a cell) | The counter from Session 10, run over both: `Meter` plus a capability counter (`CapabilityCounter` middleware, or the deep dive's counting wrapper) |
| `use_case/decisions.md` | The room's questions, then the architecture row |
| `use_case/stakeholders.md` | Who saw the refined demo, and what they asked |
| `CLAUDE.md` | The instructions Claude Code reads before it touches anything |

> **What is already written for you, and what is not.** Session 10's five
> `call_with_*` functions and its `measure()` counter run unchanged against
> any capability that takes its function as an argument. Swap `who_is_oncall`
> for your retrieval call and the plumbing is done. The taught notebook's
> `dispatch` never raises, and neither does the `Toolbox` in
> `helpers/tools.py` that the deep dive uses. **The choice of second way, the
> implementation, the measurement at your real payload, and the decision row
> are yours.**

`CLAUDE.md` puts Claude Code into **instructor mode** for this directory. It
will explain, debug, and review. It will decline to write your second
implementation or your decision row. That is deliberate. The decision reads
like documentation, so having it drafted feels harmless, but it is the
assignment.

---

## Step 1 — Write down what the room asked

In Session 9, people who did not build your system asked you questions. Most
of them are what a real sponsor asks a few months in. Write them down now,
before they blur.

Under a `## Week 5 — what the room asked` heading in
[`use_case/decisions.md`](../../use_case/decisions.md), list every question
you were asked. Then mark three of them:

| Mark | Which | What you do with it |
| --- | --- | --- |
| **Fair** | Two questions that landed: a real gap, not a misunderstanding | Fix them. Step 7's demo shows the fix |
| **Open** | The one you could not answer | Answer it by Step 6, or say plainly in the decision row why it is still open |
| **Confusion** | Any that were really *"I did not follow your explanation"* | Rewrite that part of the demo, not the system |

*"What did you reject?"* is on the rubric's list. This challenge answers it.

> **If you did not write them down during the session**, use the rubric's
> *What the room asks* list and answer every question in it in writing. Mark
> the one you struggle with most as open.

### ✅ Deliverables

1. **The questions, in `use_case/decisions.md`**, with two marked fair, one
   marked open, and any confusion ones marked as such.
2. **One line per fair question** saying what you will change.

---

## Step 2 — Pick the second-best way, and say why

Session 10's ordering, in the order the questions resolve fastest:

| # | Question | If yes |
| :---: | --- | --- |
| 1 | Does the capability **already exist as an HTTP API** at work? | **UTCP**. Describe it, do not rebuild it. Settle who holds the credential |
| 2 | Does anything **outside your codebase** need to discover this? | **MCP**. Discovery is what the process boundary buys, and the only thing |
| 3 | Does one request need **several calls, or calls that return a lot**? | **Code Mode**. The intermediate data never enters the context |
| 4 | Does the **knowledge change more often than the code**? | **A skill**. Policy in markdown that a domain expert edits |
| 5 | Does the work **read a lot to produce a little**? | **A subagent**, to keep the parent's context clean |
| 6 | Otherwise | **A tool**. The boring answer, usually right |

Your endpoint is almost certainly a tool today. Walk the six questions for
*your* capability and find the first "yes" that is not "otherwise". That is
your second-best way. Write down the reason it is second best.

**Two constraints on the pick:**

- **It has to be buildable this week** against your real endpoint. If you
  have no sandbox that can run untrusted code, Code Mode is a paragraph in
  your write-up, not an implementation.
- **It has to be measurable** with the Session 10 counter. That rules out
  nothing, but an MCP server gets measured as a tool loop plus a process,
  because that is what it is.

### ✅ Deliverables

1. **The second way, named**, with the ordering question that selected it and
   one sentence on why the questions above it were "no".
2. **The closest alternative you did *not* pick**, and why. This becomes the
   *rejected* field in Step 6.

---

## Step 3 — Build it

Build a second implementation of the same endpoint. The capability underneath
stays the same (your retrieval call, your `solve()`). What changes is how the
model reaches it.

Session 10's code is the shape for each:

| Way | What you write | What Session 10 gives you |
| --- | --- | --- |
| **Skill** | A `SKILL.md` with the policy and a `run.py` that calls your capability | The directory layout, `SkillsDirectoryProvider` to serve it, and the plan-with-a-schema step that costs ~100 tokens instead of ~1,000 (measured in the deep dive) |
| **Subagent** | A second model call with its own prompt and only your capability's output in context | `call_with_subagent` (a tool whose body is a model call), and the warning that a subagent reciting from its prompt is stale |
| **MCP server** | `@server.tool` over your capability, on stdio; or Gradio's own MCP mode over the endpoint you already have | `oncall_fastmcp_server.py` (the deep dive's twelve-line `MCPServer` is the same idea), `mount` for putting it behind a platform server, and the `.mcp.json` to point Claude Code at it |
| **Code Mode** | A namespace exposing your capability and a prompt that asks for a program | `call_with_code_mode` on FastMCP's `CodeMode`, and the rule that `SAFE_BUILTINS` is not a sandbox. This one runs in a subprocess or container, or it does not ship |
| **UTCP** | A description of the HTTP API your capability already is | `FastMCP.from_openapi` over its OpenAPI document; the deep dive's hand-written manifest, `utcp_schemas` and `utcp_invoke` |

Whichever you build, the capability takes its function as an **argument**.
That lets Step 4's counter swap in a counting version without patching
anything.

> **Dispatch through something that does not raise.** Session 10 showed a loop
> with no name check running the wrong function with no error. Wherever the
> model's request meets your code, put `Toolbox` or its equivalent. A tool
> failure is a message to the model, not an exception in your process.

### ✅ Deliverables

1. **The second implementation, running**, answering the same requests as the
   first.
2. **Its dispatcher handling an unknown tool name and malformed arguments as
   messages**, with one line in your README showing what the model gets back.

---

## Step 4 — Measure both, at demo scale

This is Session 10's Task 5 (Task 7 in the deep dive), over your two
implementations instead of its five. Send the same two requests through each:
one that needs a single capability call, and one that needs several. Record
four numbers per run:

| Column | What it tells you |
| --- | --- |
| **model calls** | What the loop cost |
| **capability calls** | What the work *was*: how many times your function actually ran |
| **seconds** | Wall-clock, end to end |
| **tokens** | What crossed the model boundary, total |

**Don't skip the second column.** When model calls and capability calls
diverge, say four invocations behind one model call, you are seeing what
your architecture is actually doing.

If the second way is a skill or an MCP server, expect the counter to read
zero. The capability ran on the other side of a process boundary, where your
counter and your tracing cannot see. Write that blind spot down as a finding.

Before you read anything else in your output, check one thing: **how many
tool calls did your model make in a single turn?** If four lookups cost two
model calls, your model emits parallel tool calls, and the round-trip argument
does not apply to it. If they cost five, it does. Either way it depends on
your model and its server, and your decision row should say which.

### ✅ Deliverables

1. **The measurement table** in your README: two implementations × two
   requests × four columns.
2. **One line** on whether your model emitted parallel tool calls, with the
   count from `len(msg.tool_calls)` on the first turn.

---

## Step 5 — Measure again at your real response size

This is Session 10's payload sweep (Task 5's second half; Task 8 in the deep
dive), on your data. Demo-scale measurements flatter every architecture,
because real capabilities return more than a four-key dictionary. Make your
endpoint return what it really returns: the full retrieved passages with their
sources, the whole record, the actual document. Then run the same request
through both implementations again.

Record three things:

- the **size of one response in bytes**
- the **number of capability calls per request**
- the **tokens** for each implementation

Then put them next to the sweep's curve. Here is how each way's cost behaves:

- **Tool loop:** it reads every result back into the conversation, so its
  cost is roughly *calls × response size* on top of the conversation.
- **Code Mode:** flat, as long as the program returns only what the question
  needs. Making sure it does is the tool description's job.
- **Subagent:** whatever it read.
- **Skill and MCP:** the tool loop's cost plus a process.

> **This is the measurement that changes decisions.** At 118 bytes the two
> ways were within a few hundred tokens of each other. At 2.5 KB the tool
> loop cost 5× more in the taught notebook's run and 32× more in the deep
> dive's. Your endpoint returns more than 118 bytes.

### ✅ Deliverables

1. **The real-size row** in your README: bytes per response, calls per
   request, tokens for each implementation, marked *measured*.
2. **One sentence** on what that number does at 10× your current volume.

---

## Step 6 — Write the decision, with the switch condition

In [`use_case/decisions.md`](../../use_case/decisions.md), fill in the
architecture row that Week 1 left as `<!-- TC5 -->`:

| Field | What it means |
| --- | --- |
| **Decision** | Which of the six you are keeping |
| **What you rejected** | The other five in a line, and the closest one (the one you built) in detail |
| **Why** | In terms of the six ordering questions and the numbers from Steps 4 and 5: callers, knowledge churn, context, response size, existing API, who holds the credential. Not preference |
| **What would change your mind** | The trigger. A second client, a response size, a call count, a security review passing |

What a good row looks like:

> **Decision:** a plain tool.
> **Rejected:** MCP, most seriously, because we built it. It added ~90 ms and
> a process we would have to own. Our app is the only caller and will be for
> at least a year, so discoverability buys nothing. A skill is the wrong
> shape: the knowledge is in code, not policy. Code Mode was the interesting
> one. Our endpoint returns ~4 KB per call and two calls per request, so it
> would have cut tokens by roughly 5×. But we are not ready to run untrusted
> code, and that is a security decision, not an architecture one.
> **Switch condition:** the moment a second client needs this (the ops
> console is the likely one), MCP becomes worth the deployment. If
> per-request calls go above four, Code Mode becomes worth the sandbox.

It is concrete, it has numbers, it names the closest alternative, and it gives
a trigger. A rejection can be *for a reason outside architecture*. Saying so is
stronger than inventing a technical objection you do not hold.

What gets picked apart:

> **Decision:** MCP, because it is the standard.

No caller named, no alternative built, no number, no trigger.

*"My architecture is one prompt"* is fine. Say so and defend it. Plenty of
production systems are one prompt with good retrieval, and Week 1's challenge
asked whether this needed to be agentic at all. If the answer was no then and
is still no, write that down as your decision.

### ✅ Deliverables

1. **The architecture row**, all four fields, with the Step 4 and 5 numbers
   cited in *why*.
2. **The open question from Step 1, answered**, or the row says plainly why
   it is still open and what would close it.

---

## 🧯 If it's blocked

### "I only know how to do it one way"

That is why Session 10 exists. Build the second one from its code. The
capability there is trivial, so all you are learning is the plumbing. Start
from the `call_with_*` that matches your pick and replace `who_is_oncall` with
your function.

### "They all perform the same"

On latency, at your scale, they might. Say that: *"at 40 requests a day the
latency difference is unmeasurable, so I chose on maintenance cost"* is a
strong engineering answer. But check tokens before you conclude it, at your
real response size. Tokens are what separate them, and the gap widens as your
data grows.

### "My round-trip numbers don't match the session's"

They are not supposed to. Whether your model emits parallel tool calls
depends on the model and the server in front of it. Report what yours does.
That is your finding.

### "The counter reads zero capability calls"

Your second way is a skill or an MCP server, and the capability ran in
another process. The counter cannot see it, and neither can your tracing.
Count it on the far side (a log line in `run.py`, a counter in the server) and
write down that you had to. That is the cost of the process boundary.

### "`mcp` won't import"

You need `mcp` 2.0 or later (`uv add mcp`). The 2.0 release removed
`mcp.server.fastmcp`. `MCPServer` in `mcp.server` is the replacement, with the
same decorator API. A tutorial that imports `mcp.server.fastmcp` predates that
release, and its import no longer resolves.

Session 10's taught notebook uses the separate `fastmcp` package instead
(`from fastmcp import FastMCP`, version 4.1 or later, which itself needs `mcp`
2.x). Either works, but do not mix a tutorial for one with the import of the
other.

### "Code Mode hung"

The model probably wrote `while True:`, and nothing in an in-process `exec` limits
time. Restart the kernel. To get a timeout you need isolation: run the code in
a subprocess you can kill, or do not run it.

---

## 👥 Step 7 — Refine the demo, and show it to a real stakeholder

Don't give the same demo again. **Refined** means it answers what the room
asked. From Step 1:

- [ ] Fix the two fair questions, and show the fix.
- [ ] Answer the open one, or say plainly on the slide why it is still open
  and what would close it.
- [ ] Cut thirty seconds of stack description and spend it on the problem.
- [ ] Show a failure on purpose, if you did not already.
- [ ] Add one line to the numbers section: the architecture decision, the
  Step 5 number that backs it, and the way you rejected, by name. Session
  10's platform engineer gave her board six answers for six teams. You owe
  the room one answer with one reject.

Then **show it to someone real**: the person from your charter, the person who
would fund the seat, or whoever is closest. Five minutes, timed, then their
questions. A screen-share counts. A recording you send and they reply to
counts. Imagining how it would go does not.

**Ask three things, in this order:**

1. *"What would you do differently on Monday if this is right?"*
2. *"What did I say that you did not believe?"*
3. *"What is the worst thing this could do, from where you sit?"* The answer
   is a candidate for the guardrail you build next.

> A demo that has visibly absorbed criticism is more credible than one that
> was polished from the start. Say out loud what changed and why.

> **Your agent will help you tighten this, and will not invent it.** Ask it to
> time the sections, to cut the stack slide, or to turn messy notes into three
> findings. It will decline to write the feedback itself, because it was not
> in the room.

### ✅ Deliverables

1. **A row in [`use_case/stakeholders.md`](../../use_case/stakeholders.md)**:
   who you showed it to by role, what you asked, what you learned, and the
   follow-up.
2. **A line in [`use_case/decisions.md`](../../use_case/decisions.md)** naming
   one thing their questions changed: a number added, a claim cut, a switch
   condition sharpened. If nothing changed, write that and say why.
3. **What changed after critique**, in one paragraph at the top of your
   README, so a reader can see the demo absorbed it.

---

## 📤 Step 8 — Share: bring it to work

This week's pattern: *build the alternative before you reject it, and measure
at the size your data really is*. Look for one of these at your company:

- a capability is being wrapped in an MCP server for one caller
- a tool loop reads 20 KB responses into a context window on every request
- an HTTP API that has run for four years is about to be rebuilt as a service
  that forwards calls to it

This step is where you write down which one.

### ✅ Deliverables

1. **Which capability at work this is for**, one line under `## Bring it to
   work` in your README. *"The ticket-lookup API the support bot wraps in
   an MCP server that only the support bot calls"* names one. *"Our agent
   platform"* does not.
2. **What you would swap**: three lines under the same heading, one each for
   - the **data**: what the capability really returns, in bytes, and how many
     calls a request needs
   - the **model or endpoint**: whether the capability already exists as an
     HTTP API, and who would hold the credential
   - the **access or approval** you would need to ask for: a sandbox for
     untrusted code, a deployment target for a server, a token for a client

   Put the Step 5 token number next to them, marked *measured*. These lines
   turn the comparison into the version your team could run.
3. **Your repo link posted in [our community on Maven](https://bit.ly/fde1-maven-community)**,
   and comments on at least two other students' submissions after the deadline.

---

## What this challenge deposits for later

| What you write | Where it lives | When it comes back |
| --- | --- | --- |
| The architecture row, with the switch condition | `use_case/decisions.md` | **Week 9**, when the deployment checklist asks what runs where and who holds which credential. **Week 10**, where the handoff doc is largely this file. |
| The second implementation | Your app | **Week 6.** A tool description is text a model reads and acts on, so the one you wrote this week is an injection surface. Code Mode's namespace is the one you escape. |
| The measurement at real response size | Your README | **Week 7.** Memory is retrieval over a corpus that grows, and this number says what growing costs. **Week 9.** The concurrency and latency numbers the deployment checklist wants. |
| The room's questions, and who saw the refined demo | `use_case/decisions.md`, `use_case/stakeholders.md` | **Week 10.** The final report answers the same questions, to a bigger room. |
| The three swap lines | Your README, `## Bring it to work` | **Week 10.** The final report's "what it would take to run" section. |

---

## Your Final Submission

Please include the following in your final submission:

1. **A public link to your repo**, containing:
   1. **A five-minute-or-less Loom video** of the refined demo. Open with
      what changed after critique, and lead with the problem, not the stack.
   2. **A written document addressing each deliverable above**:
      - the room's questions with their marks
      - the second way and why
      - the dispatcher's failure messages
      - the demo-scale measurement table, with the parallel-tool-call count
      - the real-size row
      - the architecture row
      - the Step 7 answers
      - the swap lines
   3. **All relevant code**, committed and pushed: both implementations and
      the measurement. **Never the data.**
2. **Your `use_case/` directory updated**: the Week 5 questions and the
   architecture row in `decisions.md`, and the new row in `stakeholders.md`.

### How to submit

1. **Post your repo link** in
   [our community on Maven](https://bit.ly/fde1-maven-community). That is where
   every technical challenge is submitted.
2. **Push your `use_case/` updates to that repo** before you post, so the link
   shows the current state of your project.
3. **After the deadline, comment on at least two other students' submissions.**
   Read their architecture row and leave something specific: a switch
   condition you would push on, a reject they did not measure, or the one
   question from the rubric they still have not answered.

> **Never commit real company data.** `use_case/data/` is gitignored for this
> reason. If your second implementation talks to a real internal API, commit
> the manifest shape with the hostname removed, and never the credential. Do
> not post screenshots of internal infrastructure, hostnames, or anything your
> firm would consider confidential.

---

<!-- deliverables:start -->
## 🏗️ Build | 🚢 Ship | 📤 Share

Three escalating bars. **Build** means it runs for you. **Ship** means someone
else can run it. **Share** means someone who is not you has an opinion about it.

### 🏗️ Build

A second implementation of your endpoint, in the way you judged second best,
measured against the first at your real response size. That measurement is
what lets you defend the decision.

Four questions are asked inside the Session 10 notebook as you work through
it. *They are not submitted and not graded.* They help you work out what the
challenge is going to ask you for.

| # | Question | Asked in |
| :---: | --- | --- |
| 1 | What your endpoint's dispatcher does today on a tool name it does not have, and which of the five failure rows a user of your app would meet first | S10 |
| 2 | Who outside your codebase would need to discover your capability in the next year (a named client), and what MCP buys you if the answer is nobody | S10 |
| 3 | How many bytes your endpoint really returns per call, how many calls a request needs, and where that puts you on the tool-loop slope | S10 |
| 4 | Which of the six ordering questions decides it for *your* endpoint, and the condition under which you would switch | S10 |

> **Jumping to one.** Open the notebook, then add the anchor to your browser's
> address bar, for example `#discuss-question-3`. It works once the notebook has finished loading.

### 🚢 Ship

This is the graded part. Every item comes from a numbered step in the technical
challenge, which has the full detail.

- [ ] **The room's questions written down** in `use_case/decisions.md`: the two you will fix, and the one you could not answer
- [ ] **A second implementation of your endpoint**, in the way you judged second best, running
- [ ] **Both implementations measured**: model calls, **capability calls**, latency and tokens, on the same two requests
- [ ] **The token measurement repeated at your endpoint's real response size**, with the size in bytes recorded
- [ ] `use_case/decisions.md` has the architecture row: decision, closest reject, why in terms of the six questions, and **switch condition**
- [ ] It still runs in Docker

### 📤 Share

- [ ] **The refined demo, shown to a real stakeholder**, with what changed after critique and what they asked, recorded in your own words. Graded
- [ ] **What you would swap to run this at work**: data, model or endpoint, and the approval you would need, as three lines in your README
- [ ] Your repo link posted in [our community on Maven](https://bit.ly/fde1-maven-community)
- [ ] Comments on at least two other students' submissions, after the deadline
<!-- deliverables:end -->

---

## Where this goes next

| Week | What it adds to this decision |
| --- | --- |
| 6 | Guardrails. The tool description you wrote is an injection surface, and you escape the Code Mode namespace on purpose. |
| 7 | Memory. Retrieval over a corpus that grows, measured with the same counter, so you know what growing costs. |
| 8 | Fine-tuning. The model behind the loop changes, so re-measure whether it still emits parallel tool calls first. |
| 9 | Infrastructure. Which process runs where, and who holds which credential, is the deployment checklist's first page. |
| 10 | Production. The refined demo becomes the final readout, and the decision row becomes the handoff doc. |

Everything after this week assumes you chose your architecture with a
measurement and can say what would change it.

---

## My submission

**What changed after critique.** The criticism in Session 9 was that the RAG pipeline looks too
simple. My answer this week is a measurement, not more components: I built the more agentic
versions (a tool loop and a subagent) and measured them against the simple pipeline at the real
response size. The pipeline cited the same gold papers for a third to a quarter of the tokens, so
it stays, and I can now say what I rejected and that I built it. What I take from the critique is
that I need to study RAG techniques and evals further, and I say that in the demo. Showing it to
the customer's IT and the data scientist I work with changed the roadmap more than the
architecture: they want the tool inside Microsoft Copilot over MCP, proper paper cards with title,
link and abstract where today there are only ids, and a monthly view of hot topics and newest
papers. They also did not believe the precision yet, which is the right doubt, and their worst
case is a model outside the EU.

The endpoint is `ask_research_corpus` from Week 3: one hybrid search over the paper corpus, then
one model call that answers with sources. This week it got a second implementation, and both were
measured with the same counter. Everything runs from
`uv run --group week3 python 05_Agent_Architecture/challenge/measure.py`.

| Deliverable | Answer | Where |
| --- | --- | --- |
| The room's questions (Step 1) | The rubric's 17 questions answered; 3 marked fair, 1 open ("better than what?") | [`use_case/decisions.md`](../../use_case/decisions.md), `## Week 5 — what the room asked` |
| The second way and why (Step 2) | A **subagent**: it is what an agent on the customer's platform does with this endpoint. MCP and Code Mode are named, not built | below |
| Second implementation (Step 3) | `answer_with_subagent`, served as `ask_research_corpus_agent`; a tool loop built beside it as the reference | [`agent.py`](../../01_Product_Engineering/challenge/agent.py), [`app.py`](../../01_Product_Engineering/challenge/app.py), [`tests/test_agent.py`](../../tests/test_agent.py) |
| Dispatcher failures as messages (Step 3) | Unknown tool, malformed JSON and wrong arguments all return text to the model | below |
| Measurement at demo scale (Step 4) | 3 ways × 2 requests × 4 columns; the model emits parallel tool calls | [`results.md`](results.md), below |
| Measurement at real size (Step 5) | 7.0–9.0 KB per search; pipeline 1,917–2,274 tokens, subagent 5,496–9,481 (*measured*) | [`results.md`](results.md), below |
| Architecture row (Step 6) | Keep the fixed pipeline; the subagent is the reject I built | [`use_case/decisions.md`](../../use_case/decisions.md), Week 5 row |
| Still runs in Docker | Image `fde-app:tc5`; `ask_research_corpus_agent` called inside the container | [`Dockerfile`](../../01_Product_Engineering/challenge/Dockerfile) |
| Refined demo to a stakeholder (Step 7) | Shown to the customer's IT and the data scientist on the integration; they asked for MCP from Microsoft Copilot, doubted the precision, and named a non-EU model as the worst case | [`use_case/stakeholders.md`](../../use_case/stakeholders.md), Week 5 rows in [`decisions.md`](../../use_case/decisions.md) |
| Bring it to work (Step 8) | below | - |

### The second way, and why (Step 2)

The six ordering questions, for a capability that searches 2,398 chunks of published coffee
research and returns the top 5 passages:

| # | Question | For this endpoint |
| :---: | --- | --- |
| 1 | Already an HTTP API at work? | No. The ranked-passage search exists only in this repo |
| 2 | Does anything outside the codebase need to discover it? | **Yes, soon.** The customer's agent-builder platform, whose agents would call this endpoint as a tool, and Microsoft Copilot, which the customer's IT asked about in the demo. MCP is how it would be exposed, and Gradio can serve it from the same app. Not built this week; it changes how the endpoint is reached, not what runs inside it |
| 3 | Several calls, or calls that return a lot? | Yes on size (7.0–9.0 KB per search, *measured*), no on count (one search per request). Code Mode would be the pick, but it is not built: the answer needs a model to read the passages, so a program cannot return much less than it fetched, and running model-written code needs a sandbox nobody has reviewed |
| 4 | Does the knowledge change more often than the code? | No. The knowledge is the papers, which are data; the rules in the prompt rarely change |
| 5 | Does the work read a lot to produce a little? | **Yes.** 7–9 KB of passages in, at most 150 words out: the **subagent** |
| 6 | Otherwise | A tool |

**Second way: a subagent.** An outer model gets one tool, `ask_research_corpus`, whose body is the
shipped pipeline. It splits a question into parts, each part runs the pipeline in its own model
call, and only the cited answer comes back, so the outer model never sees a passage.

**Why the subagent and not MCP first.** An agent on the platform calling this endpoint is an outer
model delegating to the pipeline, which is exactly the subagent. Building it in-process let me
measure what that agent will cost before a server exists; Session 10 measured the MCP transport
itself as the same tool loop plus a process. **Ways named and not built:** MCP (row 2, the next
step) and Code Mode (row 3). A plain **tool loop** (the
model calls `search_papers` and reads the passages itself) is also built and measured, as the
reference the subagent has to beat.

### What the model gets back when it gets it wrong (Step 3)

`agent.dispatch` never raises. The three failures, as the model receives them:

```
unknown tool 'lookup_paper'; available: ask_research_corpus
bad arguments for ask_research_corpus: missing a required argument: 'question'; it accepts: question
arguments were not valid JSON: '{"question": "roa'; send a JSON object
```

A tool that fails inside (the embedding endpoint down) also comes back as text, a loop that never
answers stops after 4 rounds, and an answer written without any search is declined, not returned.

### Both measured at demo scale (Step 4)

Local `qwen3.5:9b` on Ollama, one run per cell, passages cut to 200 characters (about 1.6 KB per
search). **1 search** is q08 (cold brew shelf life), **several** is q13 (cascara coating plus
by-product nutrients, two gold papers).

| request | way | model calls | capability calls | seconds | tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 search | pipeline (shipped) | 1 | 1 | 35.1 | 681 |
| 1 search | tool loop | 2 | 2 | 61.9 | 2,037 |
| 1 search | **subagent** | 4 | 2 | 106.6 | 2,808 |
| several | pipeline (shipped) | 1 | 1 | 45.1 | 720 |
| several | tool loop | 2 | 3 | 77.0 | 2,677 |
| several | **subagent** | 5 | 3 | 173.6 | 4,223 |

**Parallel tool calls: yes.** `len(msg.tool_calls)` on the first turn was 2 for q08 and 3 for q13,
in both the tool loop and the subagent, so the loop costs two round trips whatever the number of
searches. The subagent's extra model calls are not round trips of the loop: they are the inner
pipeline runs, one per sub-question.

Two things the table shows that the session's did not. The model treated the "one search"
question as two (how long, and does roast matter), so the split is the model's choice, not mine.
And with 200-character passages the answers got worse, not just cheaper: the tool loop and the
subagent declined q08 because the finding was cut off, which is the Week 3 passage-length result
again.

### Measured again at the real response size (Step 5)

Passages as shipped (up to 2,500 characters), same model, same two requests. All *measured*.

| request | bytes per search response | way | capability calls | model calls | seconds | tokens | gold papers cited |
| --- | ---: | --- | ---: | ---: | ---: | ---: | :---: |
| 1 search | 6,973 | pipeline (shipped) | 1 | 1 | 17.4 | **1,917** | 1/1 |
| 1 search | 7,296 | tool loop | 2 | 2 | 70.7 | 4,498 | 1/1 |
| 1 search | 7,486 | **subagent** | 2 | 4 | 120.9 | **5,496** | 1/1 |
| several | 8,960 | pipeline (shipped) | 1 | 1 | 18.2 | **2,274** | 2/2 |
| several | 8,960 | tool loop | 1 | 2 | 73.7 | 3,182 | 2/2 |
| several | 8,995 | **subagent** | 3 | 5 | 154.0 | **9,481** | 2/2 |

- The subagent costs **2.9× and 4.2× the tokens** of the pipeline and **7× to 8× the time**, and
  cites the same gold papers. Its total is roughly one pipeline run per sub-question plus the
  outer model's two calls: it keeps the passages out of the outer context, it does not make them
  cheaper to read.
- From demo to real size the pipeline went from 681 to 1,917 tokens and the subagent from 2,808 to
  5,496: the gap in tokens grew from about 2,100 to about 3,600 on the same question.
- The tool loop skipped the search on 1 of its 2 attempts at the multi-part question, although the
  first turn is sent with `tool_choice="required"`; that attempt was declined by the guard and
  re-measured. On the attempt that counted it searched once.
- Seconds are a laptop's: the chat model and the CPU embedding model share one machine, and one
  run per cell does not show the spread.

**At 10× the volume:** every request is one search and one model call, so the pipeline's cost is
about 2,100 tokens × the number of questions and nothing else moves; the subagent would multiply
the same growth by three to four. A 10× larger corpus does not change the response size at all,
because the endpoint always hands the model the top 5 passages.

### How to reproduce

```bash
# local model; the shell wins over .env
export LLM_MODEL=ollama_chat/qwen3.5:9b LLM_API_BASE=http://localhost:11434
export LLM_OPTIONS='{"num_ctx": 32768, "think": false}'
export EMBED_MODEL=ollama/qwen3-embedding-cpu EMBED_API_BASE=http://localhost:11434 EMBED_API_KEY=
uv run --group week3 python 05_Agent_Architecture/challenge/measure.py
uv run --group week3 python -m pytest tests/test_agent.py tests/test_corpus_qa.py
```

Finished runs are kept in `use_case/data/runs/tc5_measure.jsonl` (gitignored), so an interrupted
run resumes; delete the file to measure from scratch.

---

## Bring it to work

**The capability this is for.** The paper-corpus search, `ask_research_corpus`, which agents built
on the customer's agent-builder platform will call as a tool.

**Data.** One search returns 7.0 to 9.0 KB of passages (*measured*) and a question needs one
search; an agent that splits a question makes two or three, each a full pipeline run.

**Model or endpoint.** The capability already exists as an HTTP API, the Gradio endpoint in the
VM's stack. The platform calls it with its own service identity behind Identity-Aware Proxy, and
the model keys stay in the Bifrost gateway, so neither the agent nor the endpoint holds a provider
key.

**Access or approval.** The customer's IT to register the endpoint as a tool on the platform and
approve the route through the gateway; the review the customer requires before real users, which
is still to be asked; a reviewed sandbox for model-written code before Code Mode can be tried;
and the final go-ahead between my CTO and the customer.

Measured here, to put next to those lines: one search returns **7.0–9.0 KB**, a request needs
**1 search** in the pipeline and 2–3 in the subagent, and a question costs **1,917–2,274 tokens**
in the pipeline against **5,496–9,481** in the subagent (*measured*, local `qwen3.5:9b`).
