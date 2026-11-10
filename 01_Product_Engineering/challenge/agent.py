"""Two more ways for a model to reach the same search capability, next to the fixed pipeline in qa.py.

    pipeline   (qa.answer_question)  code searches once, the model reads the passages and answers
    tool loop  (answer_with_tool_loop)  the model decides when to search; every result enters its context
    subagent   (answer_with_subagent)   an outer model delegates to the pipeline; it never sees a passage

The search underneath is the same function in all three, passed in as an argument, so
05_Agent_Architecture/challenge/measure.py can count how often it really ran.
"""

import inspect
import json

from litellm import completion

import qa
import retrieval
from schema import CorpusAnswer

# A model that keeps calling tools is stopped here; the request then declines instead of running on.
MAX_ROUNDS = 4
# One request may fan out into this many pipeline runs, each a model call reading about 12 KB.
MAX_SUBQUESTIONS = 4

TOOL_LOOP_SYSTEM = (
    "You answer questions from a coffee company's R&D researchers using only passages returned by the "
    "search_papers tool, which come from published research papers. Search before answering. When the "
    "question has several parts, send one search per part in the same turn. " + qa.RULES
)

SUBAGENT_SYSTEM = (
    "You coordinate answers for a coffee company's R&D researchers. Your only source is the "
    "ask_research_corpus tool, which answers one focused question from published research papers and "
    "cites them. Pass a simple question on unchanged. Split a question with several parts into one "
    "focused call per part, and send those calls in the same turn. Then write the final answer from "
    "the tool's answers only, keeping every work id in square brackets, for example [W4403193476]. "
    f"If the tool declined every call, reply with one line that starts with '{qa.DECLINE}' followed by "
    "the reason, and give no figures. Write in the language of the question, in at most 150 words."
)


class Meter:
    """Counts model round trips, their tokens, and how many tool calls each turn asked for."""

    def __init__(self):
        self.calls = 0
        self.tokens = 0
        self.tool_calls_per_turn: list[int] = []

    def track(self, response) -> None:
        self.calls += 1
        self.tokens += getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
        self.tool_calls_per_turn.append(len(getattr(response.choices[0].message, "tool_calls", None) or []))


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required}}}


def dispatch(tools: dict, name: str, arguments: str) -> str:
    """Run one tool call the model asked for. Never raises: every failure is text for the model to act on."""
    if name not in tools:
        return f"unknown tool {name!r}; available: {', '.join(sorted(tools))}"
    try:
        args = json.loads(arguments or "{}")
    except ValueError:
        return f"arguments were not valid JSON: {str(arguments)[:120]!r}; send a JSON object"
    if not isinstance(args, dict):
        return f"arguments must be a JSON object, got {type(args).__name__}"
    accepted = inspect.signature(tools[name])
    try:
        accepted.bind(**args)
    except TypeError as error:
        return f"bad arguments for {name}: {error}; it accepts: {', '.join(accepted.parameters)}"
    try:
        return tools[name](**args)
    except Exception as error:
        # The tool itself failed (the embedding endpoint is down, say). Still a message, so the
        # model can say it could not search instead of the request dying with a traceback.
        return f"{name} failed: {type(error).__name__}: {error}"[:300]


def run_loop(question: str, *, system: str, schemas: list[dict], tools: dict, meter=None) -> str | None:
    """Decide, dispatch, answer. Returns the final text, or None when the model never stopped calling tools."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    for round_number in range(MAX_ROUNDS):
        # The first turn must call a tool: a small model otherwise sometimes answers from memory
        # (Week 4 failures.md line 2), and an answer with no search is declined anyway.
        response = completion(**qa.model_kwargs(), messages=messages, tools=schemas,
                              tool_choice="required" if round_number == 0 else "auto")
        if meter:
            meter.track(response)
        message = response.choices[0].message
        if not message.tool_calls:
            return (message.content or "").strip()
        messages.append(message.model_dump())
        for call in message.tool_calls:
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": dispatch(tools, call.function.name, call.function.arguments)})
    return None


def _finish(reply: str | None, retrieved: list[str]) -> CorpusAnswer:
    if reply is None:
        return CorpusAnswer(needs_human=True, retrieved=retrieved,
                            needs_human_reason=f"the agent did not reach an answer in {MAX_ROUNDS} rounds")
    if not retrieved:
        # An answer written without any search result is the model's memory, not the corpus.
        return CorpusAnswer(needs_human=True, needs_human_reason="the agent answered without searching the corpus")
    return qa.to_answer(reply, retrieved)


def answer_with_tool_loop(question: str, *, k: int = 5, technique: str = qa.TECHNIQUE,
                          search=retrieval.search, meter=None) -> CorpusAnswer:
    retrieved: list[str] = []

    def search_papers(query: str) -> str:
        hits = search(query, k=k, technique=technique)
        retrieved.extend(hit["source"] for hit in hits)
        return retrieval.format_hits(hits) or "(no matches)"

    schemas = [_schema("search_papers",
                       "Search ranked passages from coffee research papers. Each passage starts with its id, [W<id>#<n>].",
                       {"query": {"type": "string"}}, ["query"])]
    reply = run_loop(question, system=TOOL_LOOP_SYSTEM, schemas=schemas, tools={"search_papers": search_papers}, meter=meter)
    return _finish(reply, qa._unique(retrieved))


def answer_with_subagent(question: str, *, k: int = 5, technique: str = qa.TECHNIQUE,
                         search=retrieval.search, meter=None) -> CorpusAnswer:
    retrieved: list[str] = []
    asked = 0

    def ask_research_corpus(question: str) -> str:
        nonlocal asked
        asked += 1
        if asked > MAX_SUBQUESTIONS:
            return f"limit of {MAX_SUBQUESTIONS} calls per request reached; answer from what you already have"
        result = qa.answer_question(question, k=k, technique=technique, search=search, meter=meter)
        retrieved.extend(result.retrieved)
        if result.needs_human:
            return json.dumps({"declined": result.needs_human_reason}, ensure_ascii=False)
        # The passages stay in the inner call. The outer model gets the answer and its ids, nothing else.
        return json.dumps({"answer": result.answer, "sources": result.sources}, ensure_ascii=False)

    schemas = [_schema("ask_research_corpus",
                       "Answer one focused question from the coffee research paper corpus. Returns the answer with "
                       "the works it cites as [W<id>], or a decline with the reason when the papers do not answer it.",
                       {"question": {"type": "string"}}, ["question"])]
    reply = run_loop(question, system=SUBAGENT_SYSTEM, schemas=schemas,
                     tools={"ask_research_corpus": ask_research_corpus}, meter=meter)
    return _finish(reply, qa._unique(retrieved))


WAYS = {"pipeline": qa.answer_question, "tool loop": answer_with_tool_loop, "subagent": answer_with_subagent}
