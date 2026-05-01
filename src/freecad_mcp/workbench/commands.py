"""Workbench command implementations."""

from __future__ import annotations

from typing import Any

from freecad_mcp.orchestration import FreeCADMCPService
from freecad_mcp.workbench.context import active_document_path, active_selection_refs, show_error, show_info, workbench_service, workbench_workspace


class BaseCommand:  # pragma: no cover - FreeCAD GUI exercised manually
    menu_text = ""
    tooltip = ""

    def __init__(self, service: FreeCADMCPService | None = None) -> None:
        self._service = service

    @property
    def service(self) -> FreeCADMCPService:
        if self._service is None:
            self._service = workbench_service()
        return self._service

    def GetResources(self) -> dict[str, str]:
        return {"MenuText": self.menu_text, "ToolTip": self.tooltip}

    def IsActive(self) -> bool:
        return True


class CmdCreateProject(BaseCommand):
    menu_text = "Create MCP Project"
    tooltip = "Create a spreadsheet-backed MCP project"

    def Activated(self) -> dict[str, Any] | None:
        project_name = _prompt_text("Create MCP Project", "Project name", "mcp_project")
        if not project_name:
            return None
        result = self.service.project_create(project_name, _default_bracket_parameters(), workspace=str(workbench_workspace()))
        show_info(f"Created MCP project: {result['path']}")
        return result


class CmdGeneratePart(BaseCommand):
    menu_text = "Generate Template Part"
    tooltip = "Generate a parametric part from the default template"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before generating a part.")
            return None
        template_name = _prompt_text("Generate Template Part", "Template name", "basic_bracket") or "basic_bracket"
        result = self.service.part_create_from_template(path, template_name)
        if result.get("ok") is False:
            show_error(f"Part generation failed: {result.get('error', result)}")
        else:
            show_info(f"Generated {template_name} from template.")
        return result


class CmdRunRuleCheck(BaseCommand):
    menu_text = "Run Rule Check"
    tooltip = "Run design-rule checks for the active parameter set"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before running rule checks.")
            return None
        parameters = self.service.param_list(path)["parameters"]
        result = self.service.design_check_rules(parameters)
        show_info(f"Rule check complete: {len(result['results'])} result(s).")
        return result


class CmdCreateAssembly(BaseCommand):
    menu_text = "Create Assembly"
    tooltip = "Create an MCP assembly container in the active document"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before creating an assembly.")
            return None
        assembly_name = _prompt_text("Create Assembly", "Assembly name", "MCP Assembly") or "MCP Assembly"
        result = self.service.assembly_create(path, assembly_name)
        if result.get("ok") is False:
            show_error(f"Assembly creation failed: {result.get('error', result)}")
        else:
            show_info("Created MCP assembly container.")
        return result


class CmdInsertAssemblyLink(BaseCommand):
    menu_text = "Insert Assembly Link"
    tooltip = "Insert the active or named object as a native App::Link in the MCP assembly"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before inserting an assembly link.")
            return None
        part_id = _prompt_text("Insert Assembly Link", "Part ID", "part_1") or "part_1"
        name = _prompt_text("Insert Assembly Link", "Display name", part_id) or part_id
        result = self.service.assembly_insert_link(path, {"part_id": part_id, "name": name, "quantity": 1})
        show_info(f"Inserted assembly link: {part_id}")
        return result


class CmdGroundAssemblyPart(BaseCommand):
    menu_text = "Ground Assembly Part"
    tooltip = "Ground a linked assembly part using a native grounded joint"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before grounding an assembly part.")
            return None
        part_id = _prompt_text("Ground Assembly Part", "Part ID", "part_1") or "part_1"
        result = self.service.assembly_ground(path, part_id)
        show_info(f"Grounded assembly part: {part_id}")
        return result


class CmdCreateAssemblyJoint(BaseCommand):
    menu_text = "Create Assembly Joint"
    tooltip = "Create a native FreeCAD Assembly joint between two linked parts"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before creating a joint.")
            return None
        selections = active_selection_refs()
        parent_ref = selections[0]["ref"] if len(selections) > 0 else "part_1.Face1"
        child_ref = selections[1]["ref"] if len(selections) > 1 else "part_2.Face1"
        joint = {
            "joint_id": _prompt_text("Create Assembly Joint", "Joint ID", "joint_1") or "joint_1",
            "parent_part_id": _prompt_text("Create Assembly Joint", "Parent part ID", "part_1") or "part_1",
            "child_part_id": _prompt_text("Create Assembly Joint", "Child part ID", "part_2") or "part_2",
            "joint_type": _prompt_text("Create Assembly Joint", "Joint type", "fixed") or "fixed",
            "parent_ref": parent_ref,
            "child_ref": child_ref,
            "offset": 0,
            "unit": "mm",
        }
        result = self.service.assembly_joint_create(path, joint)
        show_info(f"Created assembly joint: {joint['joint_id']}")
        return result


class CmdSolveAssembly(BaseCommand):
    menu_text = "Solve Assembly"
    tooltip = "Run native FreeCAD Assembly solve/recompute"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before solving an assembly.")
            return None
        result = self.service.assembly_solve(path)
        show_info(f"Assembly solve: {result.get('solve_status', {}).get('solved')}")
        return result


class CmdExportProject(BaseCommand):
    menu_text = "Export Project"
    tooltip = "Export the active MCP project as STEP, STL, or DXF"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before exporting.")
            return None
        export_format = (_prompt_text("Export Project", "Format", "STEP") or "STEP").upper()
        output_path = _prompt_text("Export Project", "Output path", f"{path}.{export_format.lower()}")
        if not output_path:
            return None
        result = self.service.project_export(path, output_path, export_format)
        show_info(f"Exported {export_format}: {output_path}")
        return result


class CmdAssistantPrompt(BaseCommand):
    menu_text = "Assistant Prompt"
    tooltip = "Run a local prompt-to-actions workflow against the active document"

    def Activated(self) -> dict[str, Any] | None:
        prompt = _prompt_text("MCP Design Assistant", "Prompt", "make a bracket")
        if not prompt:
            return None
        path = active_document_path()
        result = self.service.assistant_execute(prompt, path=path, workspace=str(workbench_workspace()))
        show_info(f"Assistant prompt complete: {result.get('ok')}")
        return result


class CmdSyncMCP(BaseCommand):
    menu_text = "Sync MCP"
    tooltip = "Synchronize the active FreeCAD document with MCP state"

    def Activated(self) -> dict[str, Any] | None:
        path = active_document_path()
        if path is None:
            show_error("Save or open an MCP-managed FreeCAD document before syncing MCP state.")
            return None
        result = self.service.project_save(path)
        show_info(f"Synced MCP document: {path}")
        return result


COMMANDS: dict[str, type[BaseCommand]] = {
    "MCP_CreateProject": CmdCreateProject,
    "MCP_GeneratePart": CmdGeneratePart,
    "MCP_RunRuleCheck": CmdRunRuleCheck,
    "MCP_CreateAssembly": CmdCreateAssembly,
    "MCP_InsertAssemblyLink": CmdInsertAssemblyLink,
    "MCP_GroundAssemblyPart": CmdGroundAssemblyPart,
    "MCP_CreateAssemblyJoint": CmdCreateAssemblyJoint,
    "MCP_SolveAssembly": CmdSolveAssembly,
    "MCP_ExportProject": CmdExportProject,
    "MCP_AssistantPrompt": CmdAssistantPrompt,
    "MCP_SyncMCP": CmdSyncMCP,
}


def register_commands() -> list[str]:  # pragma: no cover - requires FreeCADGui
    import FreeCADGui  # type: ignore[import-not-found]

    for name, command in COMMANDS.items():
        FreeCADGui.addCommand(name, command())
    return list(COMMANDS)


def command_resources() -> dict[str, dict[str, Any]]:
    return {name: {"MenuText": command.menu_text, "ToolTip": command.tooltip} for name, command in COMMANDS.items()}


def _prompt_text(title: str, label: str, default: str) -> str | None:
    try:
        from freecad_mcp.workbench.qt import load_qt_widgets

        widgets, _core = load_qt_widgets()
        if widgets is None:
            return default
        value, ok = widgets.QInputDialog.getText(None, title, label, text=default)
        return str(value) if ok else None
    except Exception:
        return default


def _default_bracket_parameters() -> list[dict[str, Any]]:
    return [
        {
            "name": "p_base_len_mm",
            "unit": "mm",
            "value": 120,
            "min": 20,
            "max": 400,
            "description": "Overall bracket base length",
            "category": "geometry",
            "source": "template",
        },
        {
            "name": "p_base_w_mm",
            "unit": "mm",
            "value": 40,
            "min": 10,
            "max": 200,
            "description": "Overall bracket base width",
            "category": "geometry",
            "source": "template",
        },
        {
            "name": "p_wall_thickness_mm",
            "unit": "mm",
            "value": 3,
            "min": 1.2,
            "max": 20,
            "description": "Nominal wall thickness",
            "category": "geometry",
            "source": "template",
        },
        {
            "name": "m_clearance_fit_mm",
            "unit": "mm",
            "value": 0.3,
            "min": 0.2,
            "max": 5,
            "description": "Default assembly clearance",
            "category": "manufacturing",
            "source": "template",
        },
    ]
