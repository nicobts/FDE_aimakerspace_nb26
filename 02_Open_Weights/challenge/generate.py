"""Generate use_case/data/synthetic_v1.jsonl from the goldens and the axes.

    uv run python 02_Open_Weights/challenge/generate.py --limit 3   # trial run
    uv run python 02_Open_Weights/challenge/generate.py             # full run
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "01_Product_Engineering" / "challenge"))
sys.path.insert(0, str(Path(__file__).parent))

from axes import AXES  # noqa: E402
from helpers import nb  # noqa: E402
from helpers.llm import CallStats  # noqa: E402
from helpers import sdg  # noqa: E402
from helpers.sdg import generate  # noqa: E402
from schema import Request, Response  # noqa: E402

TEMPERATURE = 0.9
TOP_P = 0.95
DEDUPE_THRESHOLD = 0.7
PER_COMBO = 2

# generate() only shows the model the first three seeds, so pick which three.
# Golden numbers, 1-based. TODO(you): which three, and why that mix?
SEED_ORDER = [5, 4, 1, 2, 3]


class Sampled:
    """The run's config plus sampling settings.

    generate() has no temperature argument, but every call goes through
    cfg.kwargs(), so the settings ride along there and are recorded with the run.
    """

    def __init__(self, cfg, **sampling):
        self._cfg = cfg
        self._sampling = sampling

    def kwargs(self) -> dict:
        return {**self._cfg.kwargs(), **self._sampling}


def validate(row: dict) -> bool:
    """True when the row's input is a valid Request and its output a valid Response.

    The goldens store input and output as JSON text, and the model may copy that
    or write plain objects, so both forms are accepted. Any exception means
    invalid; generate() counts it as such.
    """
    def parse(model, value):
        if isinstance(value, str):
            return model.model_validate_json(value)
        return model.model_validate(value)

    parse(Request, row["input"])
    card = parse(Response, row["output"])

    # Same rule as the app: a decline carries a reason and no card. The schema
    # cannot express that, so it is checked here.
    if card.needs_human:
        return bool(card.needs_human_reason) and card.category is None and card.trust_level is None
    return card.category is not None and card.trust_level is not None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only the first N combos")
    parser.add_argument("--out", default=None, help="file name inside use_case/data/")
    # Ollama's default context window holds prompt and reply together; with this
    # long prompt the reply was cut off mid-JSON (2 of 4 lines unparseable, 0 valid).
    # With 16384 the same trial had no unparseable lines.
    parser.add_argument("--num-ctx", type=int, default=None, help="local models only")
    args = parser.parse_args()

    cfg = nb.bootstrap()
    goldens = [
        json.loads(line)
        for line in (ROOT / "use_case" / "evals" / "golden.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seeds = [goldens[number - 1] for number in SEED_ORDER]

    # Three examples were not enough: the trial wrote sample_size as prose
    # ("6 origins x 3 roasts"), so every row failed. The output schema goes into
    # the prompt; braces are doubled because the prompt is a str.format template.
    schema_rule = (
        "\n- The output must match this JSON schema exactly; sample_size is one integer "
        "or null, never a description:\n" + json.dumps(Response.model_json_schema())
    )
    sdg.GENERATION_PROMPT += schema_rule.replace("{", "{{").replace("}", "}}")

    sampling = {"temperature": TEMPERATURE, "top_p": TOP_P}
    if args.num_ctx:
        sampling["num_ctx"] = args.num_ctx

    stats = CallStats()
    rows, report = generate(
        Sampled(cfg, **sampling),
        seeds,
        AXES,
        per_combo=PER_COMBO,
        limit=args.limit,
        validate=validate,
        dedupe_threshold=DEDUPE_THRESHOLD,
        progress=lambda done, total: print(f"  combo {done}/{total}", flush=True),
        stats=stats,
    )

    name = args.out or ("synthetic_trial.jsonl" if args.limit else "synthetic_v1.jsonl")
    out = ROOT / "use_case" / "data" / name
    out.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    # Everything the datasheet and decisions.md need, in one place.
    print(report)
    print("model:", cfg.llm_model, f"| temperature {TEMPERATURE} | top_p {TOP_P}"
          f" | dedupe {DEDUPE_THRESHOLD} | per_combo {PER_COMBO}")
    print("cost:", stats)
    print("leaks:", report.leaks or "none found")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
