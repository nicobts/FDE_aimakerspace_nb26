"""Coffee-paper scout: fetch OpenAlex works into a local store and screen them against a focus.

    uv run python 03_Retrieval/challenge/scout.py seed
    uv run python 03_Retrieval/challenge/scout.py update
    uv run python 03_Retrieval/challenge/scout.py screen --area roasting --focus "..."
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "01_Product_Engineering" / "challenge"))
sys.path.insert(0, str(Path(__file__).parent))

from helpers import nb  # noqa: E402
from scout import pipeline  # noqa: E402
from scout.areas import AREAS  # noqa: E402
from scout.store import Store  # noqa: E402


def _areas(arg):
    names = arg.split(",") if arg else list(AREAS)
    unknown = [a for a in names if a not in AREAS]
    if unknown:
        raise SystemExit(f"unknown area(s): {', '.join(unknown)}; choose from {', '.join(AREAS)}")
    return names


def _store(cfg):
    return Store(Path(os.getenv("SCOUT_DB") or cfg.root / "use_case" / "data" / "scout.sqlite"))


def _print_counts(label, counts):
    tiers = " ".join(f"{t}={counts[t]}" for t in pipeline.TIERS)
    print(f"{label:15} fetched={counts['fetched']} new={counts['new']} {tiers}")


def _fetch(command, args):
    cfg = nb.bootstrap()
    store = _store(cfg)
    kwargs = dict(areas=_areas(args.areas), per_area=args.per_area, today=datetime.date.today().isoformat(),
                  # Only send a contact address when the team set one; never guess it.
                  mailto=os.getenv("OPENALEX_MAILTO") or None)
    if command == "seed":
        counts = pipeline.seed(store, from_date=args.from_date, **kwargs)
    else:
        counts = pipeline.update(store, overlap_days=args.overlap_days, **kwargs)
    for area, per_area in counts["by_area"].items():
        _print_counts(area, per_area)
    _print_counts("TOTAL", counts)


def _screen(args):
    from helpers.embeddings import Embedder

    cfg = nb.bootstrap()
    store = _store(cfg)
    embedder = Embedder(cfg, cache_dir=cfg.root / "use_case" / "data" / ".embed_cache")
    out = pipeline.screen(store, cfg, embedder, area=args.area, focus=args.focus, n=args.n, floor=args.floor,
                          triage_model=os.getenv("TRIAGE_MODEL") or None, today=datetime.date.today().isoformat())
    print(f"{'rel':>3} {'sim':>5} {'year':>4}  {'tier':8} title")
    for row in out["ranked"][:20]:
        rel = row["triage"]["relevance"] if row["triage"] else "-"
        print(f"{rel:>3} {row['similarity']:5.2f} {row['year'] or '':>4}  {row['tier']:8} {row['title'][:80]}")
    print(f"carded: {', '.join(out['carded']) or 'none'}")
    print(f"tokens: {out['tokens']}  cost_usd: {out['cost_usd']:.4f}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed", help="fetch the corpus once")
    seed.add_argument("--from-date", default="2024-01-01")
    seed.add_argument("--per-area", type=int, default=300)
    seed.add_argument("--areas")
    update = sub.add_parser("update", help="fetch only the recent window")
    update.add_argument("--per-area", type=int, default=300)
    update.add_argument("--overlap-days", type=int, default=90)
    update.add_argument("--areas")
    screen = sub.add_parser("screen", help="rank one area against a focus and card the top works")
    screen.add_argument("--area", required=True, choices=list(AREAS))
    screen.add_argument("--focus", required=True)
    screen.add_argument("--n", type=int, default=10)
    screen.add_argument("--floor", type=float, default=0.25)
    args = parser.parse_args(argv)
    if args.command == "screen":
        _screen(args)
    else:
        _fetch(args.command, args)


if __name__ == "__main__":
    main()
