import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def add_scout_paths():
    # Scout tests import `scout` (03_Retrieval) and later `schema` (Week 1), neither packaged.
    for sub in ("03_Retrieval", "01_Product_Engineering"):
        path = str(ROOT / sub / "challenge")
        if path not in sys.path:
            sys.path.insert(0, path)


def work(i, **over):
    base = {"id": f"W{i}", "doi": None, "title": f"t{i}", "year": 2025, "publication_date": "2025-03-01", "type": "article",
            "source": None, "cited_by_count": 0, "is_retracted": False, "institutions": [], "is_oa": True, "oa_status": "gold",
            "pdf_url": None, "landing_url": None, "abstract": "a", "language": "en"}
    return {**base, **over}
