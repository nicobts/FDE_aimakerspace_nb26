"""The app's memory (TC7): what reviewers have already decided about a paper.

Semantic memory, one live fact per paper, in one SQLite file. The customer asked for it in the TC6
meeting: keep the flags and the feedback, so what was already detected and reviewed is recognised.

    flags      what the guardrails did, written by code from observed events (the audit trail)
    verdicts   what a reviewer decided about a paper; a new verdict supersedes the old one

The memory never reaches the model. It changes which flags a researcher sees and what lands in the
review queue, so a wrong entry can hide a warning but cannot steer an answer.
"""

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

VERDICTS = ("approved", "wrong", "poisoned")
PAPER_ID = re.compile(r"W\d{6,}")
RUNG = re.compile(r"(?:regex|classifier|self) check (?:input|output)")
_TERM = re.compile(r"\w+", re.UNICODE)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS flags (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    seen INTEGER NOT NULL DEFAULT 1,
    fingerprint TEXT NOT NULL,
    question TEXT NOT NULL,
    flags TEXT NOT NULL,
    answer TEXT,
    sources TEXT NOT NULL DEFAULT '[]',
    retrieved TEXT NOT NULL DEFAULT '[]',
    suspicious TEXT NOT NULL DEFAULT '{}',
    withheld INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS flags_open ON flags(status, fingerprint);

CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY,
    paper TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('approved', 'wrong', 'poisoned')),
    note TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    text_hashes TEXT NOT NULL DEFAULT '[]',
    flag_id INTEGER REFERENCES flags(id),
    created_at TEXT NOT NULL,
    superseded_at TEXT,
    superseded_by INTEGER REFERENCES verdicts(id)
);
-- The staleness rule lives in the database: two live verdicts for one paper cannot exist.
CREATE UNIQUE INDEX IF NOT EXISTS one_live_verdict ON verdicts(paper) WHERE superseded_at IS NULL;

CREATE VIRTUAL TABLE IF NOT EXISTS verdict_notes USING fts5(note, paper UNINDEXED, content='verdicts', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS verdict_notes_insert AFTER INSERT ON verdicts BEGIN
    INSERT INTO verdict_notes(rowid, note, paper) VALUES (new.id, new.note, new.paper);
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_hash(text: str) -> str:
    """Whitespace-insensitive, so a re-index that only reflows a passage keeps its verdict."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]


def _flag_row(row: sqlite3.Row) -> dict:
    out = dict(row)
    for key in ("flags", "sources", "retrieved", "suspicious"):
        out[key] = json.loads(out[key])
    out["withheld"] = bool(out["withheld"])
    return out


class ReviewMemory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # A connection per call: Gradio answers on several threads, and SQLite connections do not share.
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    # --- The facts ----------------------------------------------------------------

    def live(self, papers) -> dict[str, dict]:
        papers = sorted(set(papers))
        if not papers:
            return {}
        marks = ",".join("?" * len(papers))
        with closing(self._connect()) as db:
            rows = db.execute(f"SELECT * FROM verdicts WHERE superseded_at IS NULL AND paper IN ({marks})", papers).fetchall()
        return {r["paper"]: {**dict(r), "text_hashes": json.loads(r["text_hashes"])} for r in rows}

    def history(self, paper: str) -> list[dict]:
        with closing(self._connect()) as db:
            return [dict(r) for r in db.execute("SELECT * FROM verdicts WHERE paper = ? ORDER BY id", (paper,))]

    def search_notes(self, query: str, *, limit: int = 5) -> list[dict]:
        """Live verdicts whose note shares a word with the query, best first. Each term is quoted
        because FTS5 reads punctuation and words like NOT as query syntax."""
        terms = _TERM.findall(query)
        if not terms:
            return []
        match = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT v.paper, v.verdict, v.note, v.created_at FROM verdict_notes n
                                 JOIN verdicts v ON v.id = n.rowid
                                 WHERE verdict_notes MATCH ? AND v.superseded_at IS NULL
                                 ORDER BY bm25(verdict_notes) LIMIT ?""", (match, limit)).fetchall()
        return [dict(r) for r in rows]

    # --- What a past verdict changes on a new answer ----------------------------------

    def apply(self, flags: list[str], retrieved: list[str], suspicious: dict[str, list[str]]) -> tuple[list[str], bool]:
        """(the flags to show, whether a person still has to look).

        An approval covers the exact text it judged: if a paper's suspicious passage changes, the flag
        comes back. A wrong or poisoned verdict needs no new review, so it warns without queueing."""
        verdicts = self.live([*retrieved, *suspicious])
        shown, needs_review = [], False
        for flag in flags:
            ids = PAPER_ID.findall(flag)
            verdict = verdicts.get(ids[0]) if len(ids) == 1 and ids[0] in suspicious else None
            if verdict is None:
                shown.append(flag)
                needs_review = True
            elif verdict["verdict"] == "approved" and not set(suspicious[ids[0]]) <= set(verdict["text_hashes"]):
                shown.append(f"{flag} (its text changed since a reviewer approved it on {verdict['created_at'][:10]})")
                needs_review = True
            # Otherwise already judged: approved text stays quiet, a bad paper gets the warning below.
        for paper in dict.fromkeys(retrieved):
            verdict = verdicts.get(paper)
            if verdict and verdict["verdict"] != "approved":
                shown.append(f"{paper} was marked {verdict['verdict']} by a reviewer on {verdict['created_at'][:10]}"
                             + (f": {verdict['note']}" if verdict["note"] else ""))
        return shown, needs_review

    # --- The audit trail and the queue ------------------------------------------------

    def record_flag(self, *, question: str, flags: list[str], answer: str | None = None, sources=(), retrieved=(),
                    suspicious: dict | None = None, withheld: bool = False) -> int:
        """One open review item per question and reason: the same problem asked twice is counted, not
        queued twice."""
        fingerprint = hashlib.sha256(json.dumps([question, sorted(flags)], ensure_ascii=False).encode("utf-8")).hexdigest()
        now = _now()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM flags WHERE status = 'open' AND fingerprint = ?", (fingerprint,)).fetchone()
            if row:
                db.execute("UPDATE flags SET seen = seen + 1, last_seen = ? WHERE id = ?", (now, row["id"]))
                return row["id"]
            cursor = db.execute("""INSERT INTO flags (ts, last_seen, fingerprint, question, flags, answer, sources, retrieved,
                                   suspicious, withheld) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (now, now, fingerprint, question, json.dumps(flags, ensure_ascii=False), answer,
                                 json.dumps(list(sources)), json.dumps(list(retrieved)),
                                 json.dumps(suspicious or {}), int(withheld)))
            return cursor.lastrowid

    def flag(self, flag_id: int) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM flags WHERE id = ?", (flag_id,)).fetchone()
        return _flag_row(row) if row else None

    def open_flags(self) -> list[dict]:
        with closing(self._connect()) as db:
            return [_flag_row(r) for r in db.execute("SELECT * FROM flags WHERE status = 'open' ORDER BY id")]

    def record_verdict(self, *, flag_id: int, verdict: str, paper: str | None = None, note: str = "",
                       reviewer: str = "") -> None:
        """Close a review item and, when it names a paper, make this the one live fact about that paper.
        The old verdict is kept and marked superseded, so the history can still be audited."""
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        row = self.flag(flag_id)
        if row is None:
            raise ValueError(f"no flag {flag_id}")
        if paper and (not PAPER_ID.fullmatch(paper) or paper not in {*row["retrieved"], *row["suspicious"]}):
            raise ValueError(f"{paper} is not a paper that flag {flag_id} read")
        now = _now()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if paper:
                old = db.execute("SELECT id, verdict, text_hashes FROM verdicts WHERE paper = ? AND superseded_at IS NULL",
                                 (paper,)).fetchone()
                hashes = set(row["suspicious"].get(paper, []))
                if old:
                    db.execute("UPDATE verdicts SET superseded_at = ? WHERE id = ?", (now, old["id"]))
                    if old["verdict"] == verdict:  # a second approval extends the text it covers
                        hashes |= set(json.loads(old["text_hashes"]))
                new = db.execute("""INSERT INTO verdicts (paper, verdict, note, reviewer, text_hashes, flag_id, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                 (paper, verdict, note, reviewer, json.dumps(sorted(hashes)), flag_id, now)).lastrowid
                if old:
                    db.execute("UPDATE verdicts SET superseded_by = ? WHERE id = ?", (new, old["id"]))
                self._close_covered(db, paper, hashes)
            db.execute("UPDATE flags SET status = 'reviewed' WHERE id = ?", (flag_id,))

    @staticmethod
    def _close_covered(db, paper: str, hashes: set[str]) -> None:
        """Other open items that exist only because of this same text need no second reviewer."""
        for row in db.execute("SELECT id, flags, suspicious FROM flags WHERE status = 'open'").fetchall():
            suspicious, flags = json.loads(row["suspicious"]), json.loads(row["flags"])
            only_this_paper = set(suspicious) == {paper} and all(PAPER_ID.findall(f) == [paper] for f in flags)
            if only_this_paper and set(suspicious[paper]) <= hashes:
                db.execute("UPDATE flags SET status = 'reviewed' WHERE id = ?", (row["id"],))

    # --- Why did it do that? -------------------------------------------------------------

    def explain(self, flag_id: int) -> str:
        """Built from the log, never from a model: the model's account of itself is not the record."""
        row = self.flag(flag_id)
        if row is None:
            raise ValueError(f"no flag {flag_id}")
        outcome = "The answer was withheld." if row["withheld"] else "The answer was shown with a warning."
        return f"Flag {flag_id}, first seen {row['ts']}, seen {row['seen']} time(s). {outcome} Reasons: " + " | ".join(row["flags"])


def explanation_matches(text: str, row: dict) -> bool:
    """True when an explanation names every check and paper behind the flag and invents none."""
    logged = " ".join(row["flags"])
    want = (set(RUNG.findall(logged)), set(PAPER_ID.findall(logged)))
    said = (set(RUNG.findall(text or "")), set(PAPER_ID.findall(text or "")))
    return said == want


@lru_cache(maxsize=4)
def _store(path: str) -> ReviewMemory:
    return ReviewMemory(path)


def default() -> ReviewMemory:
    """The app's store. Beside the corpus by default; it holds researchers' questions, so where it lives
    and how long it is kept are the DPO's call. MEMORY_DB moves it."""
    root = Path(os.getenv("CORPUS_DIR") or Path(__file__).resolve().parents[2] / "use_case" / "data")
    return _store(os.getenv("MEMORY_DB") or str(root / "memory.sqlite"))
