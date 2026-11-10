import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("rank_bm25")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "01_Product_Engineering" / "challenge"))
import agent  # noqa: E402
import qa  # noqa: E402

HITS = [{"id": "W1000001#0", "source": "W1000001", "text": "acrylamide forms during roasting", "score": 1.0}]


def reply(content=None, calls=()):
    """A LiteLLM-shaped response: text, or tool calls given as (name, arguments) pairs."""
    tool_calls = [SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=name, arguments=arguments))
                  for i, (name, arguments) in enumerate(calls)]
    message = SimpleNamespace(content=content, tool_calls=tool_calls or None,
                              model_dump=lambda: {"role": "assistant", "content": content})
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=SimpleNamespace(total_tokens=10))


def script(monkeypatch, *replies):
    """Make the outer model return these replies in order, and record what it was sent each time."""
    seen, queue = [], list(replies)

    def fake(**kwargs):
        seen.append([dict(m) for m in kwargs["messages"]])
        return queue.pop(0)

    monkeypatch.setattr(agent, "completion", fake)
    return seen


@pytest.fixture
def search(monkeypatch):
    monkeypatch.setattr(agent.retrieval, "format_hits", lambda hits: "\n".join(f"[{h['id']}] {h['text']}" for h in hits))
    calls = []

    def fake_search(query, *, k=5, technique="hybrid"):
        calls.append(query)
        return HITS

    fake_search.calls = calls
    return fake_search


def test_dispatch_turns_every_failure_into_a_message():
    tools = {"search_papers": lambda query: "ok"}
    assert agent.dispatch(tools, "lookup_team", "{}") == "unknown tool 'lookup_team'; available: search_papers"
    assert "not valid JSON" in agent.dispatch(tools, "search_papers", '{"query": "roast')
    assert "must be a JSON object" in agent.dispatch(tools, "search_papers", "[1]")
    assert "it accepts: query" in agent.dispatch(tools, "search_papers", '{"q": "roast"}')
    assert "it accepts: query" in agent.dispatch(tools, "search_papers", "{}")
    assert agent.dispatch({"boom": lambda: 1 / 0}, "boom", "{}").startswith("boom failed: ZeroDivisionError")


def test_tool_loop_reads_passages_and_counts_every_search(monkeypatch, search):
    seen = script(monkeypatch,
                  reply(calls=[("search_papers", '{"query": "acrylamide"}'), ("search_papers", '{"query": "roasting"}')]),
                  reply("It forms in roasting [W1000001]."))
    meter = agent.Meter()
    out = agent.answer_with_tool_loop("acrylamide?", search=search, meter=meter)
    assert search.calls == ["acrylamide", "roasting"]
    assert (meter.calls, meter.tool_calls_per_turn) == (2, [2, 0])
    assert out.sources == ["W1000001"] and not out.needs_human
    # The passages are in the model's own conversation: this is the cost the subagent avoids.
    assert "acrylamide forms during roasting" in seen[1][-1]["content"]


def test_subagent_keeps_passages_out_of_the_outer_context(monkeypatch, search):
    seen = script(monkeypatch,
                  reply(calls=[("ask_research_corpus", '{"question": "acrylamide in roasting?"}')]),
                  reply("Roasting forms it [W1000001]."))
    monkeypatch.setattr(qa.retrieval, "dense_rank", lambda question, n: [(0, 0.9)])
    monkeypatch.setattr(qa, "_complete", lambda messages, **kw: "It forms in roasting [W1000001].")
    out = agent.answer_with_subagent("acrylamide?", search=search)
    assert search.calls == ["acrylamide in roasting?"]
    tool_result = json.loads(seen[1][-1]["content"])
    assert tool_result == {"answer": "It forms in roasting [W1000001].", "sources": ["W1000001"]}
    assert "acrylamide forms during roasting" not in json.dumps(seen[1])
    assert out.sources == ["W1000001"] and out.retrieved == ["W1000001"]


def test_subagent_stops_fanning_out_at_the_limit(monkeypatch, search):
    too_many = [("ask_research_corpus", json.dumps({"question": f"part {i}"})) for i in range(agent.MAX_SUBQUESTIONS + 1)]
    seen = script(monkeypatch, reply(calls=too_many), reply("Done [W1000001]."))
    monkeypatch.setattr(qa.retrieval, "dense_rank", lambda question, n: [(0, 0.9)])
    monkeypatch.setattr(qa, "_complete", lambda messages, **kw: "x [W1000001]")
    agent.answer_with_subagent("many parts", search=search)
    assert len(search.calls) == agent.MAX_SUBQUESTIONS
    assert "limit of" in seen[1][-1]["content"]


def test_an_answer_without_any_search_is_declined(monkeypatch, search):
    script(monkeypatch, reply("Coffee is roasted at 200 C."))
    out = agent.answer_with_tool_loop("roast temperature?", search=search)
    assert out.needs_human and out.answer is None and search.calls == []


def test_a_loop_that_never_answers_is_declined(monkeypatch, search):
    script(monkeypatch, *[reply(calls=[("search_papers", '{"query": "x"}')]) for _ in range(agent.MAX_ROUNDS)])
    out = agent.answer_with_tool_loop("x?", search=search)
    assert out.needs_human and "rounds" in out.needs_human_reason
