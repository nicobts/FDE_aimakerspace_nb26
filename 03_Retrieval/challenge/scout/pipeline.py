"""The three ingestion commands: seed the corpus once, update it with the recent window, screen one area."""

import datetime
import os
import tomllib
from pathlib import Path

import helpers.llm

from .areas import AREAS
from .cards import card_work
from .funnel import is_eligible, rank_key, select_for_cards, similarity_to_focus, triage_work
from .openalex import search_works
from .tiers import assign_tier

TIERS = ("metadata", "abstract", "pdf")
_CONTRACT = Path(__file__).resolve().parents[3] / "01_Product_Engineering" / "challenge" / "pyproject.toml"


def _fetch_into(store, *, areas, from_date, per_area, today, search, mailto, api_key, queries):
    """Fetch every area, store what is new and tier what has no tier yet; return the run's counts."""
    queries = queries or {}
    fetched, new, ids_by_area, stats_by_area = 0, 0, {}, {}
    for area in areas:
        query = queries.get(area) or AREAS[area]["query"]
        # Forwarded only when set, so an injected search need not accept it.
        extra = {"api_key": api_key} if api_key else {}
        works = search(query=query, from_date=from_date, max_works=per_area, mailto=mailto, **extra)
        added = store.upsert_works(works, area=area, first_seen=today)
        fetched, new = fetched + len(works), new + added
        ids_by_area[area] = {w["id"] for w in works}
        stats_by_area[area] = {"fetched": len(works), "new": added}
    # Tier only works that have none, so a tier set later (by the full-text step) survives a re-fetch.
    tier_of = {}
    for work in store.works(ids=sorted(set().union(*ids_by_area.values()))):
        if work["tier"] is None:
            work["tier"] = assign_tier(work)
            store.set_tier(work["id"], tier=work["tier"])
        tier_of[work["id"]] = work["tier"]
    tiers = list(tier_of.values())
    by_area = {a: {**stats_by_area[a], **{t: sum(tier_of[i] == t for i in ids_by_area[a]) for t in TIERS}}
               for a in areas}
    return {"fetched": fetched, "new": new, **{t: tiers.count(t) for t in TIERS}, "by_area": by_area}


def seed(store, *, areas, from_date, per_area, today, search=search_works, mailto=None, api_key=None, queries=None) -> dict:
    counts = _fetch_into(store, areas=areas, from_date=from_date, per_area=per_area, today=today,
                         search=search, mailto=mailto, api_key=api_key, queries=queries)
    store.add_run(kind="seed", params={"areas": list(areas), "from_date": from_date, "per_area": per_area},
                  counts=counts, tokens=0, cost_usd=0.0, ran_at=today)
    return counts


def update(store, *, areas, per_area, today, overlap_days=90, search=search_works, mailto=None, api_key=None, queries=None) -> dict:
    seed_run = store.last_run(kind="seed")
    if seed_run is None:
        raise ValueError("no seed run yet; run seed first")
    last = max(r["ran_at"] for r in (seed_run, store.last_run(kind="update")) if r)
    # Works are indexed by OpenAlex some weeks after publication; the overlap re-reads that lag.
    from_date = (datetime.date.fromisoformat(last) - datetime.timedelta(days=overlap_days)).isoformat()
    counts = _fetch_into(store, areas=areas, from_date=from_date, per_area=per_area, today=today,
                         search=search, mailto=mailto, api_key=api_key, queries=queries)
    store.add_run(kind="update", params={"areas": list(areas), "from_date": from_date, "per_area": per_area,
                                         "overlap_days": overlap_days},
                  counts=counts, tokens=0, cost_usd=0.0, ran_at=today)
    return counts


def _prices():
    try:
        return float(os.environ["CARD_PRICE_IN"]), float(os.environ["CARD_PRICE_OUT"])
    except (KeyError, ValueError):
        return None


def schema_version() -> str:
    return tomllib.loads(_CONTRACT.read_text(encoding="utf-8"))["project"]["version"]


def call_cost(prices, *, prompt_tokens, completion_tokens) -> float:
    """Price a call's tokens; zero when the team has set no prices, which the run row records as cost_known."""
    return (prices[0] * prompt_tokens + prices[1] * completion_tokens) if prices else 0.0


def screen(store, cfg, embedder, *, area, focus, n=10, floor=0.25, triage_model=None, card_model=None,
           languages=("en", "it"), today, chat=helpers.llm.chat) -> dict:
    works = [w for w in store.works(area=area) if w["tier"] in ("abstract", "pdf")]
    sims = similarity_to_focus(embedder, works, focus=focus)
    # Stored before the floor applies, so a work below it still shows its similarity in later views.
    for work in works:
        store.set_triage(work["id"], triage=None, similarity=sims[work["id"]])
    stats = helpers.llm.CallStats()
    rows = []
    for work in works:
        if sims[work["id"]] < floor:
            continue
        result = triage_work(cfg, work, focus=focus, model=triage_model, stats=stats, chat=chat)
        store.set_triage(work["id"], triage=result, similarity=sims[work["id"]])
        rows.append({**work, "similarity": sims[work["id"]], "triage": result})
    selected = select_for_cards(rows, n=n)
    # Every candidate is shown in the order the pick uses; rows the pick cannot take (unparsed triage,
    # not a study, retracted) follow, most similar first, so the printed top 20 is not arbitrary.
    ordered = sorted((r for r in rows if is_eligible(r)), key=rank_key)
    ordered += sorted((r for r in rows if not is_eligible(r)), key=lambda r: -r["similarity"])

    version = schema_version()
    model = card_model or (cfg.llm_model if cfg else "injected")
    prices = _prices()
    carded = []
    for work in selected:
        before = (stats.prompt_tokens, stats.completion_tokens)
        card = card_work(cfg, work, focus=focus, languages=list(languages), text=None, model=card_model,
                         stats=stats, chat=chat)
        cost = call_cost(prices, prompt_tokens=stats.prompt_tokens - before[0],
                         completion_tokens=stats.completion_tokens - before[1])
        store.add_card(work["id"], card=card.model_dump(), schema_version=version, model=model,
                       # The text was the abstract whatever the work's tier; the full-text step records "pdf".
                       tier="abstract", cost_usd=cost)
        carded.append(work["id"])
    cost_usd = call_cost(prices, prompt_tokens=stats.prompt_tokens, completion_tokens=stats.completion_tokens)
    store.add_run(kind="screen", ran_at=today, tokens=stats.total_tokens, cost_usd=cost_usd,
                  params={"area": area, "focus": focus, "n": n, "floor": floor, "triage_model": triage_model,
                          "card_model": card_model, "cost_known": prices is not None},
                  counts={"candidates": len(works), "triaged": len(rows), "carded": len(carded)})
    return {"ranked": [{"id": r["id"], "title": r["title"], "year": r["year"], "source": r["source"], "tier": r["tier"],
                        "similarity": r["similarity"], "triage": r["triage"]} for r in ordered],
            "carded": carded, "tokens": stats.total_tokens, "cost_usd": cost_usd}
