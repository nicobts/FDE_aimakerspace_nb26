import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS works(
    id TEXT PRIMARY KEY, json TEXT, areas TEXT, tier TEXT, first_seen TEXT,
    publication_date TEXT, similarity REAL, triage TEXT);
CREATE TABLE IF NOT EXISTS cards(
    work_id TEXT, version INTEGER, schema_version TEXT, model TEXT, tier TEXT,
    cost_usd REAL, created_at TEXT, card TEXT, focus TEXT, PRIMARY KEY(work_id, version));
CREATE TABLE IF NOT EXISTS fulltext(
    work_id TEXT PRIMARY KEY, markdown TEXT, source_url TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS runs(
    id INTEGER PRIMARY KEY, kind TEXT, ran_at TEXT, params TEXT, counts TEXT,
    tokens INTEGER, cost_usd REAL);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    """System of record for the coffee-paper corpus: works, extraction cards, full text and ingestion runs."""

    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(_SCHEMA)
        # Databases created before cards recorded their focus lack the column; CREATE IF NOT EXISTS leaves them as they were.
        if "focus" not in {row[1] for row in self._db.execute("PRAGMA table_info(cards)")}:
            with self._db:
                self._db.execute("ALTER TABLE cards ADD COLUMN focus TEXT")

    def upsert_works(self, works: list[dict], *, area: str, first_seen: str) -> int:
        ids = [w["id"] for w in works]
        areas_by_id = {}
        # Chunked so a large batch stays under SQLite's bound-variable limit.
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            for wid, areas in self._db.execute(f"SELECT id, areas FROM works WHERE id IN ({marks})", chunk):
                areas_by_id[wid] = json.loads(areas)
        inserts, updates, seen = [], [], set()
        for w in works:
            wid = w["id"]
            if wid in seen:
                continue  # the same id twice in one batch must not count or insert twice
            seen.add(wid)
            if wid in areas_by_id:
                areas = areas_by_id[wid]
                if area not in areas:
                    updates.append((json.dumps(areas + [area]), wid))
            else:
                inserts.append((wid, json.dumps(w), json.dumps([area]), first_seen, w.get("publication_date")))
        with self._db:
            self._db.executemany(
                "INSERT INTO works(id, json, areas, first_seen, publication_date) VALUES(?,?,?,?,?)", inserts)
            self._db.executemany("UPDATE works SET areas=? WHERE id=?", updates)
        return len(inserts)

    def works(self, *, area: str | None = None, tier: str | None = None, since_published: str | None = None,
              since_seen: str | None = None, ids: list[str] | None = None) -> list[dict]:
        where, args = [], []
        if tier is not None:
            where.append("tier = ?"); args.append(tier)
        if since_published is not None:
            where.append("publication_date >= ?"); args.append(since_published)
        if since_seen is not None:
            where.append("first_seen >= ?"); args.append(since_seen)
        if ids is not None:
            where.append(f"id IN ({','.join('?' * len(ids))})"); args.extend(ids)
        sql = "SELECT id, json, areas, tier, first_seen, similarity, triage FROM works"
        if where:
            sql += " WHERE " + " AND ".join(where)
        out = []
        for wid, body, areas, tier_, first_seen, similarity, triage in self._db.execute(sql + " ORDER BY rowid", args):
            areas = json.loads(areas)
            # Areas live in a JSON list, so membership is checked here rather than with LIKE on the text.
            if area is not None and area not in areas:
                continue
            out.append({**json.loads(body), "areas": areas, "tier": tier_, "first_seen": first_seen,
                        "similarity": similarity, "triage": json.loads(triage) if triage else None,
                        "card": (self.latest_card(wid) or {}).get("card")})
        return out

    def set_tier(self, work_id: str, *, tier: str) -> None:
        with self._db:
            self._db.execute("UPDATE works SET tier=? WHERE id=?", (tier, work_id))

    def set_triage(self, work_id: str, *, triage: dict | None, similarity: float | None) -> None:
        with self._db:
            self._db.execute("UPDATE works SET triage=?, similarity=? WHERE id=?",
                             (None if triage is None else json.dumps(triage), similarity, work_id))

    def add_card(self, work_id: str, *, card: dict, schema_version: str, model: str, tier: str, cost_usd: float,
                 focus: str | None = None) -> int:
        with self._db:
            # sqlite3 opens its transaction at the INSERT, so the SELECT below is not covered by it: two writers
            # could pick the same number, and the primary key then makes the second INSERT fail instead of overwrite.
            version = self._db.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM cards WHERE work_id=?",
                                       (work_id,)).fetchone()[0]
            self._db.execute("INSERT INTO cards(work_id, version, schema_version, model, tier, cost_usd, created_at, card, focus) "
                             "VALUES(?,?,?,?,?,?,?,?,?)",
                             (work_id, version, schema_version, model, tier, cost_usd, _now(), json.dumps(card), focus))
        return version

    def latest_card(self, work_id: str) -> dict | None:
        row = self._db.execute(
            "SELECT version, card, model, tier, cost_usd, created_at, focus FROM cards WHERE work_id=? "
            "ORDER BY version DESC LIMIT 1", (work_id,)).fetchone()
        if row is None:
            return None
        return {"version": row[0], "card": json.loads(row[1]), "model": row[2], "tier": row[3],
                "cost_usd": row[4], "created_at": row[5], "focus": row[6]}

    def set_fulltext(self, work_id: str, *, markdown: str, source_url: str) -> None:
        with self._db:
            self._db.execute("INSERT OR REPLACE INTO fulltext VALUES(?,?,?,?)", (work_id, markdown, source_url, _now()))

    def fulltext(self, work_id: str) -> str | None:
        row = self._db.execute("SELECT markdown FROM fulltext WHERE work_id=?", (work_id,)).fetchone()
        return row[0] if row else None

    def add_run(self, *, kind: str, params: dict, counts: dict, tokens: int, cost_usd: float, ran_at: str) -> int:
        with self._db:
            cur = self._db.execute("INSERT INTO runs(kind, ran_at, params, counts, tokens, cost_usd) VALUES(?,?,?,?,?,?)",
                                   (kind, ran_at, json.dumps(params), json.dumps(counts), tokens, cost_usd))
        return cur.lastrowid

    def last_run(self, *, kind: str) -> dict | None:
        row = self._db.execute(
            "SELECT id, kind, ran_at, params, counts, tokens, cost_usd FROM runs WHERE kind=? ORDER BY id DESC LIMIT 1",
            (kind,)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "kind": row[1], "ran_at": row[2], "params": json.loads(row[3]),
                "counts": json.loads(row[4]), "tokens": row[5], "cost_usd": row[6]}
