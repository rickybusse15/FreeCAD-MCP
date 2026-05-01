"""FreeCAD Addon Manager entrypoint for MCPDesignWorkbench."""

from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parent
src = root / "src"
if src.exists() and str(src) not in sys.path:
    sys.path.insert(0, str(src))

from freecad_mcp.workbench.Init import *  # noqa: F401,F403
