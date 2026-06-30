from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"

for path in (SRC,):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
