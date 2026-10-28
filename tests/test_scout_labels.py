import json

import pytest

from scout_support import work, add_scout_paths
add_scout_paths()
from scout.labels import load_labels, to_case  # noqa: E402
from scout.store import Store  # noqa: E402


def store(tmp_path):
    s = Store(tmp_path / "s.sqlite")
    s.upsert_works([work(1), work(2)], area="roasting", first_seen="2026-10-27")
    return s


def write(tmp_path, *lines):
    path = tmp_path / "retrieval.jsonl"
    path.write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines) + "\n", encoding="utf-8")
    return path


LOOKUP = {"question": "Which roast level lowers acrylamide?", "kind": "lookup", "gold": ["W1"], "expected_terms": ["acrylamide"]}
DECLINE = {"question": "Who will win the barista cup?", "kind": "decline", "gold": [], "expected_terms": ["non"]}


def test_valid_file_yields_labels_and_cases(tmp_path):
    path = write(tmp_path, {"header": {"multi_record": 0}}, "# a comment", "", LOOKUP, DECLINE)
    labels = load_labels(path, store=store(tmp_path))
    assert [l["id"] for l in labels] == ["q01", "q02"]
    assert [l["must_decline"] for l in labels] == [False, True]
    assert to_case(labels[0]) == {"id": "q01", "question": LOOKUP["question"], "expected_terms": ["acrylamide"],
                                  "expected_pages": ["W1"], "must_decline": False}


def test_gold_id_missing_from_store_names_line_and_id(tmp_path):
    path = write(tmp_path, LOOKUP, {**LOOKUP, "gold": ["W1", "W99"]})
    with pytest.raises(ValueError, match=r"line 2.*gold.*W99"):
        load_labels(path, store=store(tmp_path))


def test_decline_with_must_decline_false_is_rejected(tmp_path):
    path = write(tmp_path, {**DECLINE, "must_decline": False})
    with pytest.raises(ValueError, match=r"line 1.*must_decline"):
        load_labels(path, store=store(tmp_path))


def test_lookup_with_empty_gold_is_rejected(tmp_path):
    path = write(tmp_path, {**LOOKUP, "gold": []})
    with pytest.raises(ValueError, match=r"line 1.*gold"):
        load_labels(path, store=store(tmp_path))


def test_a_byte_order_mark_on_the_first_line_is_ignored(tmp_path):
    path = write(tmp_path, {"header": {"multi_record": 0}}, LOOKUP)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert [l["id"] for l in load_labels(path, store=store(tmp_path))] == ["q01"]
