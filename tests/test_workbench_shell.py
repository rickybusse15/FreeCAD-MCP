from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from freecad_mcp.workbench.commands import CmdGeneratePart, command_resources
from freecad_mcp.workbench.docks import AssemblyDock, DesignAssistantDock, ParameterEditorDock, RuleCheckDock

pytestmark = pytest.mark.workbench


def test_workbench_commands_are_described_without_freecad() -> None:
    resources = command_resources()
    assert set(resources) == {
        "MCP_CreateProject",
        "MCP_GeneratePart",
        "MCP_RunRuleCheck",
        "MCP_CreateAssembly",
        "MCP_InsertAssemblyLink",
        "MCP_GroundAssemblyPart",
        "MCP_CreateAssemblyJoint",
        "MCP_SolveAssembly",
        "MCP_ExportProject",
        "MCP_AssistantPrompt",
        "MCP_SyncMCP",
    }
    assert resources["MCP_CreateProject"]["MenuText"] == "Create MCP Project"


def test_describing_commands_does_not_create_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    command_resources()
    assert not Path("workspace").exists()


def test_docks_hold_data_without_qt() -> None:
    parameter_dock = ParameterEditorDock()
    assert parameter_dock.refresh([{"name": "p_base_len_mm", "value": 120}])[0]["name"] == "p_base_len_mm"
    assert RuleCheckDock().refresh([{"rule_id": "r1"}])[0]["rule_id"] == "r1"
    assert DesignAssistantDock().append_message("Created bracket") == ["Created bracket"]
    assembly_dock = AssemblyDock()
    assembly_dock.add_part({"part_id": "base", "name": "Base Plate", "quantity": 1})
    assert assembly_dock.refresh()["bom"][0]["part_id"] == "base"


def test_generate_part_command_uses_active_document_path(monkeypatch) -> None:
    calls = {}

    class Service:
        def part_create_from_template(self, path, template_name):
            calls["path"] = path
            calls["template_name"] = template_name
            return {"ok": True}

    monkeypatch.setattr("freecad_mcp.workbench.commands.active_document_path", lambda: "/tmp/demo.FCStd")
    command = CmdGeneratePart(service=Service())
    assert command.Activated() == {"ok": True}
    assert calls == {"path": "/tmp/demo.FCStd", "template_name": "basic_bracket"}


def test_initgui_registers_workbench_with_mocked_freecadgui(monkeypatch) -> None:
    registered = []
    fake_gui = SimpleNamespace(addWorkbench=registered.append)
    monkeypatch.setitem(sys.modules, "FreeCADGui", fake_gui)
    sys.modules.pop("freecad_mcp.workbench.InitGui", None)
    module = importlib.import_module("freecad_mcp.workbench.InitGui")
    assert registered
    assert registered[0].GetClassName() == "Gui::PythonWorkbench"
    sys.modules.pop(module.__name__, None)
