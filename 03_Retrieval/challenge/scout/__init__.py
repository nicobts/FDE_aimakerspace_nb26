import sys
from pathlib import Path

# The scout reuses the Week 1 contract (schema, card) and the root helpers without
# packaging either, so every entry point needs both directories on sys.path.
_ROOT = Path(__file__).resolve().parents[3]
for _path in (_ROOT / "01_Product_Engineering" / "challenge", _ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
