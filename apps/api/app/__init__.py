"""API service package."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the agent-runtime package (and the skill packages) are importable
# before any app submodule touches ``agent_runtime``.  This centralises the
# sys.path bootstrap that previously lived only in app/runtime.py.
_RUNTIME_SRC = Path(__file__).resolve().parents[3] / "packages" / "agent-runtime" / "src"
if _RUNTIME_SRC.exists() and str(_RUNTIME_SRC) not in sys.path:
    sys.path.append(str(_RUNTIME_SRC))
