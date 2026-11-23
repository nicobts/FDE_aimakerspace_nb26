"""The TC7 memory tests in pytest as well as in run.py, and the checks on spec rule 7."""

import inspect
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("nemoguardrails")
pytest.importorskip("rank_bm25")
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "01_Product_Engineering" / "challenge"), str(ROOT / "use_case" / "evals")]
import memory_scenarios  # noqa: E402
import qa  # noqa: E402


@pytest.mark.parametrize("name", list(memory_scenarios.SCENARIOS))
def test_scenario_holds_and_can_fail(name):
    out = json.loads(memory_scenarios.run_scenario(name))
    assert all(out["checks"].values()), [k for k, v in out["checks"].items() if not v]
    assert out["caught_broken_memory"], "this test passes on a broken memory, so it proves nothing"


def test_memory_never_reaches_the_prompt():
    source = inspect.getsource(qa.answer_question)
    assert "memory." not in source and "verdict" not in source
