from __future__ import annotations

from pathlib import Path

import pytest

from freecad_mcp.adapter import FreeCADAdapter
from freecad_mcp.diagnostics import basic_bracket_parameters
from freecad_mcp.orchestration import FreeCADMCPService

pytestmark = pytest.mark.freecad


def test_real_freecad_basic_bracket_workflow(tmp_path: Path) -> None:
    pytest.importorskip("FreeCAD")

    adapter = FreeCADAdapter(workspace=tmp_path, prefer_real_freecad=True, require_real_freecad=True)
    service = FreeCADMCPService(adapter=adapter, workspace=tmp_path)
    project = service.project_create("real_bracket", [parameter.to_dict() for parameter in basic_bracket_parameters()])
    project_path = project["path"]
    part = service.part_create_from_template(project_path, "basic_bracket")
    assert part["ok"] is True

    updated = service.param_set(project_path, basic_bracket_parameters()[0].to_dict() | {"value": 160, "source": "user"})
    assert updated["ok"] is True
    parameters = {item["name"]: item for item in service.param_list(project_path)["parameters"]}
    assert parameters["p_base_len_mm"]["value"] == 160

    step = service.project_export(project_path, str(tmp_path / "real_bracket.step"), "STEP")
    stl = service.project_export(project_path, str(tmp_path / "real_bracket.stl"), "STL")
    assert step["ok"] is True
    assert stl["ok"] is True
    assert Path(step["path"]).exists()
    assert Path(stl["path"]).exists()


def test_real_freecad_native_assembly_workflow(tmp_path: Path) -> None:
    pytest.importorskip("FreeCAD")

    adapter = FreeCADAdapter(workspace=tmp_path, prefer_real_freecad=True, require_real_freecad=True)
    service = FreeCADMCPService(adapter=adapter, workspace=tmp_path)
    project = service.project_create("real_assembly", [parameter.to_dict() for parameter in basic_bracket_parameters()])
    project_path = project["path"]
    part = service.part_create_from_template(project_path, "basic_bracket")
    assert part["ok"] is True

    assembly = service.assembly_create(project_path, "Fixture")
    assert assembly["ok"] is True
    link = service.assembly_insert_link(project_path, {"part_id": "bracket", "name": "Bracket", "quantity": 1})
    assert link["ok"] is True
    grounded = service.assembly_ground(project_path, "bracket")
    assert grounded["ok"] is True
    solved = service.assembly_solve(project_path)
    assert solved["ok"] is True
    bom = service.assembly_bom(project_path)
    assert bom["bom"][0]["part_id"] == "bracket"
