"""MVP MCP tool registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from freecad_mcp.models import JOINT_TYPES
from freecad_mcp.orchestration import FreeCADMCPService

ToolHandler = Callable[..., dict[str, Any]]


class ToolRegistry:
    def __init__(self, service: FreeCADMCPService | None = None) -> None:
        self.service = service or FreeCADMCPService()
        self._tools: dict[str, ToolHandler] = {}
        self._register_defaults()

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, name: str, **kwargs: Any) -> dict[str, Any]:
        try:
            handler = self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc
        validation_error = self._validate_tool_input(name, kwargs)
        if validation_error is not None:
            return validation_error
        return handler(**kwargs)

    def as_catalog(self) -> dict[str, Any]:
        return {
            "version": "0.1.0",
            "tools": [
                {
                    "name": name,
                    "description": TOOL_DESCRIPTIONS[name],
                    "input_schema": TOOL_INPUT_SCHEMAS[name],
                }
                for name in self.names
            ],
        }

    def _register_defaults(self) -> None:
        self._tools = {
            "assembly.add_part": self.service.assembly_add_part,
            "assembly.bom": self.service.assembly_bom,
            "assembly.create": self.service.assembly_create,
            "assembly.explode_view": self.service.assembly_explode_view,
            "assembly.ground": self.service.assembly_ground,
            "assembly.insert_link": self.service.assembly_insert_link,
            "assembly.joint.create": self.service.assembly_joint_create,
            "assembly.joint.delete": self.service.assembly_joint_delete,
            "assembly.joint.list": self.service.assembly_joint_list,
            "assembly.joint.update": self.service.assembly_joint_update,
            "assembly.mate": self.service.assembly_mate,
            "assembly.solve": self.service.assembly_solve,
            "assistant.execute": self.service.assistant_execute,
            "assistant.plan": self.service.assistant_plan,
            "runtime.status": self.service.runtime_status,
            "project.create": self.service.project_create,
            "project.open": self.service.project_open,
            "project.save": self.service.project_save,
            "project.export": self.service.project_export,
            "param.list": self.service.param_list,
            "param.set": self.service.param_set,
            "param.batch_set": self.service.param_batch_set,
            "param.validate": self.service.param_validate,
            "part.create_from_template": self.service.part_create_from_template,
            "design.check_rules": self.service.design_check_rules,
        }

    def _validate_tool_input(self, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        schema = TOOL_INPUT_SCHEMAS[name]
        try:
            Draft202012Validator(schema).validate(payload)
        except JsonSchemaValidationError as exc:
            return {
                "ok": False,
                "error": {
                    "type": "schema_validation",
                    "tool": name,
                    "message": exc.message,
                    "path": list(exc.path),
                    "schema_path": list(exc.schema_path),
                },
            }
        return None


TOOL_DESCRIPTIONS: dict[str, str] = {
    "project.create": "Create a new FreeCAD project document with optional spreadsheet parameters.",
    "project.open": "Open an existing FreeCAD project document.",
    "project.save": "Save the active or mock project document.",
    "project.export": "Export a project to STEP, STL, or DXF.",
    "param.list": "List spreadsheet-backed parameters for a project.",
    "param.set": "Set one named spreadsheet parameter.",
    "param.batch_set": "Set multiple named spreadsheet parameters.",
    "param.validate": "Validate parameter names, units, values, and bounds.",
    "part.create_from_template": "Generate an initial parametric part from a named template.",
    "assembly.create": "Create an assembly container in a project document.",
    "assembly.add_part": "Compatibility alias for inserting or updating an assembly part link.",
    "assembly.insert_link": "Insert or update a native App::Link in the active assembly.",
    "assembly.ground": "Create a native grounded joint for an assembly part.",
    "assembly.joint.create": "Create a native FreeCAD Assembly joint between two linked parts.",
    "assembly.joint.update": "Replace an existing native FreeCAD Assembly joint.",
    "assembly.joint.delete": "Delete a native FreeCAD Assembly joint.",
    "assembly.joint.list": "List native FreeCAD Assembly joints tracked for the active assembly.",
    "assembly.mate": "Compatibility alias for creating a native FreeCAD Assembly joint.",
    "assembly.solve": "Run the native FreeCAD Assembly solver/recompute path.",
    "assembly.bom": "Return a bill of materials for the active assembly.",
    "assembly.explode_view": "Compute and persist an exploded-view offset plan for the active assembly.",
    "design.check_rules": "Run manufacturability and parameter validation rules.",
    "assistant.plan": "Convert a local workbench prompt into deterministic MCP tool actions.",
    "assistant.execute": "Execute a recognized local workbench prompt through MCP service actions.",
    "runtime.status": "Report whether the adapter is using real FreeCAD, mock mode, or unavailable real mode.",
}

PARAMETER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "unit", "value", "description", "category", "source"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "unit": {"type": "string", "enum": ["mm", "deg", "count", "string", "bool"]},
        "value": {"type": ["number", "string", "boolean"]},
        "min": {"type": ["number", "null"]},
        "max": {"type": ["number", "null"]},
        "description": {"type": "string"},
        "category": {"type": "string"},
        "source": {"type": "string", "enum": ["template", "user", "rule_engine"]},
    },
}

ASSEMBLY_PART_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["part_id", "name"],
    "additionalProperties": False,
    "properties": {
        "part_id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "path": {"type": ["string", "null"]},
        "quantity": {"type": "integer", "minimum": 1},
        "interface_ref": {"type": "string"},
        "material": {"type": "string"},
    },
}

ASSEMBLY_MATE_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["mate_id", "parent_part_id", "child_part_id", "mate_type", "parent_ref", "child_ref"],
    "additionalProperties": False,
    "properties": {
        "mate_id": {"type": "string", "minLength": 1},
        "parent_part_id": {"type": "string", "minLength": 1},
        "child_part_id": {"type": "string", "minLength": 1},
        "mate_type": {"type": "string", "enum": list(JOINT_TYPES)},
        "parent_ref": {"type": "string", "minLength": 1},
        "child_ref": {"type": "string", "minLength": 1},
        "offset": {"type": "number"},
        "unit": {"type": "string", "enum": ["mm", "deg"]},
    },
}

ASSEMBLY_JOINT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["joint_id", "parent_part_id", "child_part_id", "joint_type", "parent_ref", "child_ref"],
    "additionalProperties": False,
    "properties": {
        "joint_id": {"type": "string", "minLength": 1},
        "parent_part_id": {"type": "string", "minLength": 1},
        "child_part_id": {"type": "string", "minLength": 1},
        "joint_type": {"type": "string", "enum": list(JOINT_TYPES)},
        "parent_ref": {"type": "string", "minLength": 1},
        "child_ref": {"type": "string", "minLength": 1},
        "offset": {"type": "number"},
        "unit": {"type": "string", "enum": ["mm", "deg"]},
    },
}

TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "project.create": {
        "type": "object",
        "required": ["project_name"],
        "additionalProperties": False,
        "properties": {
            "project_name": {"type": "string", "minLength": 1},
            "parameters": {"type": ["array", "null"], "items": PARAMETER_INPUT_SCHEMA},
            "workspace": {"type": ["string", "null"]},
        },
    },
    "project.open": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}},
    },
    "project.save": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}},
    },
    "project.export": {
        "type": "object",
        "required": ["path", "output_path", "format"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1},
            "output_path": {"type": "string", "minLength": 1},
            "format": {"type": "string", "enum": ["STEP", "STL", "DXF", "step", "stl", "dxf"]},
        },
    },
    "param.list": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}},
    },
    "param.set": {
        "type": "object",
        "required": ["path", "parameter"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "parameter": PARAMETER_INPUT_SCHEMA},
    },
    "param.batch_set": {
        "type": "object",
        "required": ["path", "parameters"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1},
            "parameters": {"type": "array", "items": PARAMETER_INPUT_SCHEMA},
        },
    },
    "param.validate": {
        "type": "object",
        "required": ["parameters"],
        "additionalProperties": False,
        "properties": {"parameters": {"type": "array", "items": PARAMETER_INPUT_SCHEMA}},
    },
    "part.create_from_template": {
        "type": "object",
        "required": ["path", "template_name"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1},
            "template_name": {"type": "string", "minLength": 1},
        },
    },
    "assembly.create": {
        "type": "object",
        "required": ["path", "assembly_name"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1},
            "assembly_name": {"type": "string", "minLength": 1},
        },
    },
    "assembly.add_part": {
        "type": "object",
        "required": ["path", "part"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "part": ASSEMBLY_PART_INPUT_SCHEMA},
    },
    "assembly.insert_link": {
        "type": "object",
        "required": ["path", "part"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "part": ASSEMBLY_PART_INPUT_SCHEMA},
    },
    "assembly.ground": {
        "type": "object",
        "required": ["path", "part_id"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "part_id": {"type": "string", "minLength": 1}},
    },
    "assembly.mate": {
        "type": "object",
        "required": ["path", "mate"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "mate": ASSEMBLY_MATE_INPUT_SCHEMA},
    },
    "assembly.joint.create": {
        "type": "object",
        "required": ["path", "joint"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "joint": ASSEMBLY_JOINT_INPUT_SCHEMA},
    },
    "assembly.joint.update": {
        "type": "object",
        "required": ["path", "joint"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "joint": ASSEMBLY_JOINT_INPUT_SCHEMA},
    },
    "assembly.joint.delete": {
        "type": "object",
        "required": ["path", "joint_id"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}, "joint_id": {"type": "string", "minLength": 1}},
    },
    "assembly.joint.list": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}},
    },
    "assembly.solve": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}},
    },
    "assembly.bom": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {"path": {"type": "string", "minLength": 1}},
    },
    "assembly.explode_view": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string", "minLength": 1},
            "distance_mm": {"type": "number", "minimum": 0},
        },
    },
    "design.check_rules": {
        "type": "object",
        "required": ["parameters"],
        "additionalProperties": False,
        "properties": {"parameters": {"type": "array", "items": PARAMETER_INPUT_SCHEMA}},
    },
    "assistant.plan": {
        "type": "object",
        "required": ["prompt"],
        "additionalProperties": False,
        "properties": {"prompt": {"type": "string", "minLength": 1}, "path": {"type": ["string", "null"]}},
    },
    "assistant.execute": {
        "type": "object",
        "required": ["prompt"],
        "additionalProperties": False,
        "properties": {
            "prompt": {"type": "string", "minLength": 1},
            "path": {"type": ["string", "null"]},
            "workspace": {"type": ["string", "null"]},
        },
    },
    "runtime.status": {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    },
}
