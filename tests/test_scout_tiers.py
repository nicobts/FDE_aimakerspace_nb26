import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "03_Retrieval" / "challenge"))
from scout import areas, tiers  # noqa: E402

def test_eight_areas_with_schema_categories():
    assert set(areas.AREAS) == {"roasting","processing","sustainability","agronomy","extraction","health","packaging","sensory"}
    assert all(a["category"] in {"agronomy","processing","roasting","health","sustainability","other"} for a in areas.AREAS.values())
    assert all(a["query"].strip() for a in areas.AREAS.values())

def test_tier_metadata_when_no_abstract():
    assert tiers.assign_tier({"abstract": None, "pdf_url": "https://x/y.pdf"}) == "metadata"

def test_tier_abstract_when_no_pdf_url():
    assert tiers.assign_tier({"abstract": "text", "pdf_url": None}) == "abstract"

def test_tier_pdf_when_both():
    assert tiers.assign_tier({"abstract": "text", "pdf_url": "https://x/y.pdf"}) == "pdf"
