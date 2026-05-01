from __future__ import annotations

from pathlib import Path

import pytest

from freecad_mcp.adapter import FreeCADAdapter
from freecad_mcp.models import AssemblyJoint, AssemblyMate, AssemblyPart, Parameter

pytestmark = pytest.mark.mock


def test_mock_adapter_creates_project_and_updates_parameters(tmp_path: Path) -> None:
    adapter = FreeCADAdapter(workspace=tmp_path, prefer_real_freecad=False)
    parameter = Parameter(
        name="p_base_len_mm",
        unit="mm",
        value=120,
        min=20,
        max=400,
        description="Base length",
        category="geometry",
        source="template",
    )
    created = adapter.create_project("demo", [parameter])
    project_path = Path(created["path"])
    assert project_path.exists()

    adapter.set_parameter(project_path, parameter.__class__(**(parameter.to_dict() | {"value": 160})))
    assert adapter.list_parameters(project_path)[0]["value"] == 160

    feature = adapter.create_part_from_template(project_path, "basic_bracket")
    assert feature["template_name"] == "basic_bracket"

    export = adapter.export_project(project_path, tmp_path / "demo.step", "STEP")
    assert export["format"] == "step"


def test_mock_adapter_tracks_assembly_parts_mates_bom_and_exploded_view(tmp_path: Path) -> None:
    adapter = FreeCADAdapter(workspace=tmp_path, prefer_real_freecad=False)
    created = adapter.create_project("demo")
    project_path = Path(created["path"])

    assembly = adapter.create_assembly(project_path, "fixture")["assembly"]
    assert assembly["name"] == "fixture"

    adapter.add_assembly_part(
        project_path,
        AssemblyPart(
            part_id="base",
            name="Base Plate",
            quantity=1,
            material="6061-T6",
            interface_ref="datum/base",
        ),
    )
    adapter.add_assembly_part(
        project_path,
        AssemblyPart(
            part_id="bracket",
            name="Bracket",
            quantity=2,
            material="6061-T6",
            interface_ref="datum/bracket",
        ),
    )
    mate = AssemblyMate(
        mate_id="m1",
        parent_part_id="base",
        child_part_id="bracket",
        mate_type="fixed",
        parent_ref="Face.Top",
        child_ref="Face.Bottom",
    )
    adapter.add_assembly_mate(project_path, mate)
    adapter.ground_assembly_part(project_path, "base")
    adapter.create_assembly_joint(
        project_path,
        AssemblyJoint(
            joint_id="m2",
            parent_part_id="base",
            child_part_id="bracket",
            joint_type="angle",
            parent_ref="Face.Top",
            child_ref="Face.Side",
            offset=90,
            unit="deg",
        ),
    )

    bom = adapter.assembly_bom(project_path)["bom"]
    assert bom == [
        {"part_id": "base", "name": "Base Plate", "material": "6061-T6", "quantity": 1, "source_path": None},
        {"part_id": "bracket", "name": "Bracket", "material": "6061-T6", "quantity": 2, "source_path": None},
    ]

    exploded = adapter.assembly_explode_view(project_path, distance_mm=30)["exploded_view"]
    assert exploded["enabled"] is True
    assert exploded["vectors"][1] == {"part_id": "bracket", "x_mm": 60.0, "y_mm": 0, "z_mm": 0}

    assert adapter.list_assembly_joints(project_path)["grounded"] == ["base"]
    solved = adapter.solve_assembly(project_path)
    assert solved["solve_status"]["solved"] is True


def test_mock_adapter_reports_runtime_mode(tmp_path: Path) -> None:
    adapter = FreeCADAdapter(workspace=tmp_path, prefer_real_freecad=False)
    assert adapter.runtime_status()["runtime_mode"] == "mock"
