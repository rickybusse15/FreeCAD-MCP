from __future__ import annotations

import pytest

from freecad_mcp.mcp_tools import ToolRegistry
from freecad_mcp.models import JOINT_TYPES

pytestmark = pytest.mark.mock


def test_registry_exposes_initial_mvp_tools() -> None:
    registry = ToolRegistry()
    assert registry.names == [
        "assembly.add_part",
        "assembly.bom",
        "assembly.create",
        "assembly.explode_view",
        "assembly.ground",
        "assembly.insert_link",
        "assembly.joint.create",
        "assembly.joint.delete",
        "assembly.joint.list",
        "assembly.joint.update",
        "assembly.mate",
        "assembly.solve",
        "assistant.execute",
        "assistant.plan",
        "design.check_rules",
        "param.batch_set",
        "param.list",
        "param.set",
        "param.validate",
        "part.create_from_template",
        "project.create",
        "project.export",
        "project.open",
        "project.save",
        "runtime.status",
    ]


def test_registry_can_validate_parameters() -> None:
    registry = ToolRegistry()
    result = registry.call(
        "param.validate",
        parameters=[
            {
                "name": "p_wall_thickness_mm",
                "unit": "mm",
                "value": 3,
                "min": 1.2,
                "max": 20,
                "description": "Wall thickness",
                "category": "geometry",
                "source": "template",
            }
        ],
    )
    assert result == {"valid": True, "errors": []}


def test_registry_catalog_has_strict_export_format_schema() -> None:
    registry = ToolRegistry()
    tools = {tool["name"]: tool for tool in registry.as_catalog()["tools"]}
    export_schema = tools["project.export"]["input_schema"]
    assert export_schema["additionalProperties"] is False
    assert export_schema["properties"]["format"]["enum"] == ["STEP", "STL", "DXF", "step", "stl", "dxf"]


def test_registry_returns_structured_schema_errors() -> None:
    registry = ToolRegistry()
    result = registry.call("project.export", path="demo.FCStd", output_path="demo.iges", format="IGES")
    assert result["ok"] is False
    assert result["error"]["type"] == "schema_validation"
    assert result["error"]["tool"] == "project.export"


def test_registry_exposes_assembly_tool_schemas() -> None:
    registry = ToolRegistry()
    tools = {tool["name"]: tool for tool in registry.as_catalog()["tools"]}
    mate_schema = tools["assembly.mate"]["input_schema"]["properties"]["mate"]
    assert mate_schema["properties"]["mate_type"]["enum"] == list(JOINT_TYPES)


def test_registry_exposes_prompt_and_runtime_tools() -> None:
    registry = ToolRegistry()
    assert registry.call("runtime.status")["runtime_mode"] in {"freecad", "mock", "unavailable"}
    plan = registry.call("assistant.plan", prompt="make a bracket")
    assert plan["ok"] is True
    assert plan["actions"][-1]["tool"] == "part.create_from_template"
