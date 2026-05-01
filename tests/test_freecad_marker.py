from __future__ import annotations

import shutil
import importlib.util

import pytest


@pytest.mark.freecad
def test_freecadcmd_is_available_for_real_integration() -> None:
    if shutil.which("FreeCADCmd") is None and shutil.which("freecadcmd") is None:
        pytest.skip("FreeCADCmd is not installed in this environment")
    if importlib.util.find_spec("FreeCAD") is None:
        pytest.skip("FreeCAD Python module is not importable in this interpreter")
