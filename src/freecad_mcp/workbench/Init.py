"""FreeCAD module init for MCPDesignWorkbench."""

from __future__ import annotations

import sys
from pathlib import Path

# FreeCAD imports this file for module discovery. GUI registration lives in
# InitGui.py so command-line FreeCAD can import the package without FreeCADGui.
module_file = globals().get("__file__")
candidate_paths = []
if module_file:
    candidate_paths.append(Path(module_file).resolve().parents[2])
try:
    import FreeCAD  # type: ignore[import-not-found]

    candidate_paths.append(Path(FreeCAD.getUserAppDataDir()) / "Mod" / "MCPDesignWorkbench")
except Exception:
    pass

for candidate in candidate_paths:
    resolved = candidate.resolve()
    for src_path in (resolved, *resolved.parents):
        if (src_path / "freecad_mcp" / "__init__.py").exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
            break
