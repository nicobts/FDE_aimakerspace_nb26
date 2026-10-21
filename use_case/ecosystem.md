# The ecosystem you deploy into

Where your application would actually run, inside your actual firm.

> **Week 1 starts this file. Week 9 finishes it.**
> TC1 Step 10 asks eight questions. The full Week 9 checklist has around thirty,
> and the eight are a strict subset — so nothing here gets thrown away.

Describe patterns, not specifics. "On-prem OpenShift, images from an internal
registry, no public egress" is useful to everyone and identifies nobody. Never
put real hostnames, IPs, or architecture diagrams in this file.

---

## Week 1 — the first eight questions

<!-- Answered in TC1 Step 10. Bring these back from a real conversation. -->

**Who did you ask?** (role, not name)

The customer's IT department, which I am working with on the deployment, and my own CTO, who
supervises the development. I own the build myself, so several answers below are decisions I am
making, not ones I was handed.

| # | Question | Answer |
| :---: | --- | --- |
| 1 | Where do internal apps run? (k8s, ECS, App Service, a VM someone maintains) | A single VM hosting the container and the rest of the services stack. It is the test deployment of a wider agent platform; this use case runs on top of it. Target: stack deployed by the end of this week. |
| 2 | Which cloud? AWS, Azure, GCP, on-prem, several? | GCP, in the customer's own infrastructure. I deploy the whole solution for them. |
| 3 | Is there an internal container registry? | Not used yet. Because this is a test, the image is built on the VM from the repository and is not pushed anywhere. |
| 4 | How do users log in? (Okta, Entra ID, Ping, SAML, homegrown) | Google Cloud Identity-Aware Proxy in front of the stack, with a small OAuth proxy as the authentication layer, so users sign in with the customer's Google accounts. IAP controls the connection, which means the VM needs no public IP. The app itself implements no authentication. |
| 5 | Can the app reach the internet? Egress proxy? Allowlist? | Yes for model APIs, but only through an AI gateway (Bifrost) that I am setting up for control, governance and tracing. The gateway is not publicly accessible; like the rest of the stack it is reachable only through IAP. Providers: OpenRouter only at first, for simplicity; most likely Vertex AI later. Whether general egress from the VM is open or allowlisted: unknown, to ask IT. |
| 6 | Where do secrets come from? (Vault, Secrets Manager, Key Vault) | GitHub repository secrets. Planned: a simple CI pipeline that collects them and deploys them to the customer's GCP infrastructure. Not built yet. |
| 7 | Who approves a deployment, and what review does it need? | I own the development, supervised by my CTO. Final approval has to be agreed with the customer. What review the customer requires before real users: unknown, to ask. |
| 8 | Is there an approved internal LLM endpoint already? | Yes, but in my own company's infrastructure, not yet in the customer's. |

**What surprised you?**

There is no existing platform or process to deploy onto, so the path is mine to
define. An approved model endpoint exists in my own company but not at the
customer. There is no registry and no pipeline yet. Nobody could say what review
the customer requires before real users. I expected constraints and was handed a
blank page.

**What would you have to change about your app to deploy there?**

- Point the model at the AI gateway through `LLM_API_BASE` and the model name
  (configuration only).
- Take secrets from the planned CI pipeline, not a local `.env`; no
  authentication in the app, the proxy in front handles login.
- Run it as one service in the VM's compose stack behind the reverse proxy, with
  `/health` as its health check.

**The wider project.** This use case is one of 45 the customer wants to evaluate.
The stack it runs alongside: an AI gateway, an agent-builder platform, a tracing
service, a logging service and others.

---

## Week 1 — what your machine told you

<!--
  Paste the egress probe output from Session 1 here. It is evidence, and it
  frequently disagrees with what people believe about their own network.
-->

### 2026-10-14, my development laptop

| Host | Why | Status | Signed by |
| --- | --- | --- | --- |
| pypi.org | Python packages | OK | GlobalSign nv-sa |
| files.pythonhosted.org | the actual wheel downloads | OK | GlobalSign nv-sa |
| api.openai.com | the model API | OK | Google Trust Services |
| cdn.jsdelivr.net | the CDN your app's frontend uses | OK | GlobalSign nv-sa |
| huggingface.co | open weights and fine-tuning | OK | Amazon |
| registry-1.docker.io | container images | OK | Amazon |
| github.com | this repository | OK | Sectigo Limited |

**Verdict:** Open network, public CAs, no proxy. Nothing here will bite you.

**Does this match what you were told in the table above?** Where it doesn't, that
gap is worth chasing — it usually means a proxy nobody documented.

It cannot be compared yet. This probe ran on my own laptop, on an open network.
The table above describes a VM in the customer's cloud that does not exist yet,
with model calls going through a gateway and general egress still unknown. The
useful comparison is this same probe run from that VM once it is up; I will add
that as a second dated table here.

**Week 2 — a local model (2026-10-21).** Ollama with `qwen2.5:7b` downloaded
without trouble on my laptop (RTX 4060, 8 GB), and the Week 1 app ran on it
with two `.env` lines and no code change. But on the five goldens it declined
all five, including the four that should get a card, against 5 of 5 correct
decisions from the hosted model on the same inputs. A local model is a
plausible path at the customer only if three things are true: a GPU VM in
their GCP project next to the app, a larger open model than 7B that passes the
goldens, and their IT accepting that the gateway routes internal documents to
it instead of to a hosted API.

Both paths stay configured: the hosted model through OpenRouter is the default,
and two local models are commented options in `.env`, `qwen2.5:7b` and Liquid
AI's `LFM2.5-8B-A1B` (Q4_K_M, about 5 GB, pulled from Hugging Face through
Ollama). Liquid AI's models are built for on-device use, which matches the
"model inside the customer's boundary" case. Its licence must be read before
anything is deployed at the customer. Tested on the same five goldens, it did
worse than Qwen: 4 of 5 answers broke the JSON contract, and its one card had
the wrong category and trust level. Neither small local model is usable for
this task yet.

---

## Week 9 — the full checklist

<!--
  TC9 extends this same file. Do not start a new one: the point is that the git
  history shows one continuous piece of work from Week 1 to Week 9.
-->

<!-- Week 9 -->
