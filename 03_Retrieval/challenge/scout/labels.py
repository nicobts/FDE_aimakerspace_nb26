import json
from pathlib import Path

KINDS = {"lookup", "multi-hop", "decline"}


def _fail(lineno: int, field: str, problem: str):
    raise ValueError(f"line {lineno}, field '{field}': {problem}")


def _nonempty_strings(lineno: int, field: str, value, *, allow_empty: bool):
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        _fail(lineno, field, "must be a list of non-empty strings")
    if not value and not allow_empty:
        _fail(lineno, field, "must not be empty")


def load_labels(path: Path, *, store) -> list[dict]:
    """Parse and validate the retrieval label file; return the labels in file order, each with an `id`."""
    parsed = []  # (lineno, label) kept until the gold ids are checked in one store query
    for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            _fail(lineno, "<line>", f"not valid JSON ({e.msg})")
        if not isinstance(obj, dict):
            _fail(lineno, "<line>", "must be a JSON object")
        # The header is the student's own count, not a question, so it never reaches the harness.
        if "header" in obj and not parsed:
            continue

        if not isinstance(obj.get("question"), str) or not obj["question"].strip():
            _fail(lineno, "question", "must be a non-empty string")
        kind = obj.get("kind")
        if kind not in KINDS:
            _fail(lineno, "kind", f"must be one of {sorted(KINDS)}, got {kind!r}")
        _nonempty_strings(lineno, "gold", obj.get("gold"), allow_empty=kind == "decline")
        _nonempty_strings(lineno, "expected_terms", obj.get("expected_terms"), allow_empty=False)
        expected_decline = kind == "decline"
        if "must_decline" in obj and obj["must_decline"] is not expected_decline:
            _fail(lineno, "must_decline", f"must be {expected_decline} when kind is {kind!r}")
        parsed.append((lineno, {**obj, "must_decline": expected_decline}))

    wanted = sorted({g for _, label in parsed for g in label["gold"]})
    known = {w["id"] for w in store.works(ids=wanted)} if wanted else set()
    labels = []
    for position, (lineno, label) in enumerate(parsed, start=1):
        missing = [g for g in label["gold"] if g not in known]
        if missing:
            _fail(lineno, "gold", f"id not in the store: {', '.join(missing)}")
        labels.append({**label, "id": label.get("id") or f"q{position:02d}"})
    return labels


def to_case(label: dict) -> dict:
    # Exactly the keys Session 5's score() reads; anything else would be silently ignored there.
    return {"id": label["id"], "question": label["question"], "expected_terms": label["expected_terms"],
            "expected_pages": label["gold"], "must_decline": label["must_decline"]}
