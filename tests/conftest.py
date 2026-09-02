from __future__ import annotations

import sys
from pathlib import Path

# Make both `resolveai` (src layout) and `evals` (repo-root package) importable
# without requiring an editable install -- keeps `pytest` runnable straight
# out of a fresh clone with just `pip install -r requirements.txt`.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
