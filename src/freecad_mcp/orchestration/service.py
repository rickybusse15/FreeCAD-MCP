"""Application service used by MCP tools and the workbench shell."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

from freecad_mcp.adapter import FreeCADAdapter
from freecad_mcp.intelligence import RuleEngine
from freecad_mcp.models import AssemblyJoint, AssemblyPart, Parameter, RuleResult, ValidationError


class FreeCADMCPService:
    def __init__(
        self,
        adapter: FreeCADAdapter | None = None,
        rule_engine: RuleEngine | None = None,
        workspace: str | Path = "workspace",
    ) -> None:
        self.workspace = Path(workspace)
        self.adapter = adapter or FreeCADAdapter(workspace=self.workspace)
        self.rule_engine = rule_engine or self._load_default_rules()

    def project_create(
        self,
        project_name: str,
        parameters: list[dict[str, Any]] | None = None,
        workspace: str | None = None,
    ) -> dict[str, Any]:
        parsed = self._parse_parameters(parameters or [])
        result = self.adapter.create_project(project_name, parsed, path=self._project_path(project_name, workspace))
        self._record_operation("project.create", result)
        return result

    def project_open(self, path: str) -> dict[str, Any]:
        return self.adapter.open_project(path)

    def project_save(self, path: str) -> dict[str, Any]:
        result = self.adapter.save_project(path)
        self._record_operation("project.save", result)
        return result

    def project_export(self, path: str, output_path: str, format: str) -> dict[str, Any]:
        result = self.adapter.export_project(path, output_path, format)
        self._record_operation("project.export", result)
        return result

    def runtime_status(self) -> dict[str, Any]:
        return self.adapter.runtime_status()

    def param_list(self, path: str) -> dict[str, Any]:
        return {"parameters": self.adapter.list_parameters(path)}

    def param_set(self, path: str, parameter: dict[str, Any]) -> dict[str, Any]:
        parsed = Parameter.from_mapping(parameter)
        self._raise_for_parameter_errors([parsed])
        result = self.adapter.set_parameter(path, parsed)
        self._record_operation("param.set", result)
        return result

    def param_batch_set(self, path: str, parameters: list[dict[str, Any]]) -> dict[str, Any]:
        parsed = self._parse_parameters(parameters)
        updated = [self.adapter.set_parameter(path, parameter)["parameter"] for parameter in parsed]
        result = {"parameters": updated}
        self._record_operation("param.batch_set", result)
        return result

    def param_validate(self, parameters: list[dict[str, Any]]) -> dict[str, Any]:
        parsed, field_errors = self._try_parse_parameters(parameters)
        errors = [error for parameter in parsed for error in parameter.validate()]
        errors.extend(field_errors)
        return {"valid": not errors, "errors": errors}

    def part_create_from_template(self, path: str, template_name: str) -> dict[str, Any]:
        result = self.adapter.create_part_from_template(path, template_name)
        self._record_operation("part.create_from_template", result)
        return result

    def assembly_create(self, path: str, assembly_name: str) -> dict[str, Any]:
        result = self.adapter.create_assembly(path, assembly_name)
        self._record_operation("assembly.create", result)
        return result

    def assembly_add_part(self, path: str, part: dict[str, Any]) -> dict[str, Any]:
        parsed = AssemblyPart.from_mapping(part)
        self._raise_for_assembly_errors(parsed.validate())
        result = self.adapter.insert_assembly_link(path, parsed)
        self._record_operation("assembly.add_part", result)
        return result

    def assembly_insert_link(self, path: str, part: dict[str, Any]) -> dict[str, Any]:
        parsed = AssemblyPart.from_mapping(part)
        self._raise_for_assembly_errors(parsed.validate())
        result = self.adapter.insert_assembly_link(path, parsed)
        self._record_operation("assembly.insert_link", result)
        return result

    def assembly_ground(self, path: str, part_id: str) -> dict[str, Any]:
        result = self.adapter.ground_assembly_part(path, part_id)
        self._record_operation("assembly.ground", result)
        return result

    def assembly_mate(self, path: str, mate: dict[str, Any]) -> dict[str, Any]:
        parsed = AssemblyJoint.from_mapping(mate)
        self._raise_for_assembly_errors(parsed.validate())
        result = self.adapter.create_assembly_joint(path, parsed)
        self._record_operation("assembly.mate", result)
        return result

    def assembly_joint_create(self, path: str, joint: dict[str, Any]) -> dict[str, Any]:
        parsed = AssemblyJoint.from_mapping(joint)
        self._raise_for_assembly_errors(parsed.validate())
        result = self.adapter.create_assembly_joint(path, parsed)
        self._record_operation("assembly.joint.create", result)
        return result

    def assembly_joint_update(self, path: str, joint: dict[str, Any]) -> dict[str, Any]:
        parsed = AssemblyJoint.from_mapping(joint)
        self._raise_for_assembly_errors(parsed.validate())
        result = self.adapter.update_assembly_joint(path, parsed)
        self._record_operation("assembly.joint.update", result)
        return result

    def assembly_joint_delete(self, path: str, joint_id: str) -> dict[str, Any]:
        result = self.adapter.delete_assembly_joint(path, joint_id)
        self._record_operation("assembly.joint.delete", result)
        return result

    def assembly_joint_list(self, path: str) -> dict[str, Any]:
        return self.adapter.list_assembly_joints(path)

    def assembly_solve(self, path: str) -> dict[str, Any]:
        result = self.adapter.solve_assembly(path)
        self._record_operation("assembly.solve", result)
        return result

    def assembly_bom(self, path: str) -> dict[str, Any]:
        return self.adapter.assembly_bom(path)

    def assembly_explode_view(self, path: str, distance_mm: float = 25) -> dict[str, Any]:
        result = self.adapter.assembly_explode_view(path, distance_mm)
        self._record_operation("assembly.explode_view", result)
        return result

    def design_check_rules(self, parameters: list[dict[str, Any]]) -> dict[str, Any]:
        parsed, field_errors = self._try_parse_parameters(parameters)
        results = [result.to_dict() for result in self.rule_engine.check_parameters(parsed)]
        results.extend(
            RuleResult(
                rule_id="parameter.schema",
                severity="error",
                entity_ref=f"parameters[{index}]",
                message=message,
            ).to_dict()
            for index, message in enumerate(field_errors)
        )
        return {"results": results}

    def assistant_plan(self, prompt: str, path: str | None = None) -> dict[str, Any]:
        prompt_lower = prompt.lower()
        actions: list[dict[str, Any]] = []
        if "assembly" in prompt_lower and "bracket" in prompt_lower:
            if path is None:
                actions.append({"tool": "project.create", "args": {"project_name": "mcp_prompt_project"}})
            actions.extend(
                [
                    {"tool": "part.create_from_template", "args": {"template_name": "basic_bracket"}},
                    {"tool": "part.create_from_template", "args": {"template_name": "basic_bracket"}},
                    {"tool": "assembly.create", "args": {"assembly_name": "MCP Assembly"}},
                    {
                        "tool": "assembly.insert_link",
                        "args": {"part": {"part_id": "bracket_a", "name": "Bracket A", "quantity": 1}},
                    },
                    {
                        "tool": "assembly.insert_link",
                        "args": {"part": {"part_id": "bracket_b", "name": "Bracket B", "quantity": 1}},
                    },
                ]
            )
        elif "bracket" in prompt_lower and any(word in prompt_lower for word in ("make", "create", "generate")):
            if path is None:
                actions.append({"tool": "project.create", "args": {"project_name": "mcp_prompt_project"}})
            actions.append({"tool": "part.create_from_template", "args": {"template_name": "basic_bracket"}})
        elif "thickness" in prompt_lower:
            value = self._extract_first_number(prompt_lower)
            if value is None:
                return {"ok": False, "actions": [], "error": "No numeric thickness was found in the prompt."}
            actions.append(
                {
                    "tool": "param.set",
                    "args": {
                        "parameter": {
                            "name": "p_wall_thickness_mm",
                            "unit": "mm",
                            "value": value,
                            "min": 1.2,
                            "max": 20,
                            "description": "Nominal wall thickness",
                            "category": "geometry",
                            "source": "user",
                        }
                    },
                }
            )
        else:
            return {"ok": False, "actions": [], "error": "Prompt is not recognized by the local V1 action parser."}
        return {"ok": True, "actions": actions, "path": path}

    def assistant_execute(self, prompt: str, path: str | None = None, workspace: str | None = None) -> dict[str, Any]:
        plan = self.assistant_plan(prompt, path=path)
        if plan.get("ok") is False:
            return plan
        current_path = path
        results: list[dict[str, Any]] = []
        for action in plan["actions"]:
            tool = action["tool"]
            args = dict(action.get("args", {}))
            if tool == "project.create":
                parameters = [parameter.to_dict() for parameter in self._default_bracket_parameters()]
                result = self.project_create(args["project_name"], parameters, workspace=workspace)
                current_path = result.get("path")
            elif tool == "part.create_from_template":
                self._raise_for_missing_prompt_path(current_path, tool)
                result = self.part_create_from_template(str(current_path), args["template_name"])
            elif tool == "param.set":
                self._raise_for_missing_prompt_path(current_path, tool)
                result = self.param_set(str(current_path), args["parameter"])
            elif tool == "assembly.create":
                self._raise_for_missing_prompt_path(current_path, tool)
                result = self.assembly_create(str(current_path), args["assembly_name"])
            elif tool == "assembly.insert_link":
                self._raise_for_missing_prompt_path(current_path, tool)
                result = self.assembly_insert_link(str(current_path), args["part"])
            else:
                result = {"ok": False, "error": f"Unsupported assistant action: {tool}"}
            results.append({"tool": tool, "result": result})
            if result.get("ok") is False:
                return {"ok": False, "path": current_path, "actions": plan["actions"], "results": results}
        return {"ok": True, "path": current_path, "actions": plan["actions"], "results": results}

    def _parse_parameters(self, parameters: list[dict[str, Any]]) -> list[Parameter]:
        parsed = [Parameter.from_mapping(item) for item in parameters]
        self._raise_for_parameter_errors(parsed)
        return parsed

    def _raise_for_parameter_errors(self, parameters: list[Parameter]) -> None:
        errors = [error for parameter in parameters for error in parameter.validate()]
        if errors:
            raise ValidationError("; ".join(errors))

    def _raise_for_assembly_errors(self, errors: list[str]) -> None:
        if errors:
            raise ValidationError("; ".join(errors))

    def _try_parse_parameters(self, parameters: list[dict[str, Any]]) -> tuple[list[Parameter], list[str]]:
        parsed: list[Parameter] = []
        errors: list[str] = []
        for index, item in enumerate(parameters):
            try:
                parsed.append(Parameter.from_mapping(item))
            except KeyError as exc:
                errors.append(f"parameters[{index}]: missing required field {exc.args[0]}")
            except TypeError as exc:
                errors.append(f"parameters[{index}]: {exc}")
        return parsed, errors

    def _default_bracket_parameters(self) -> list[Parameter]:
        return [
            Parameter("p_base_len_mm", "mm", 120, 20, 400, "Overall bracket base length", "geometry", "template"),
            Parameter("p_base_w_mm", "mm", 40, 10, 200, "Overall bracket base width", "geometry", "template"),
            Parameter("p_wall_thickness_mm", "mm", 3, 1.2, 20, "Nominal wall thickness", "geometry", "template"),
            Parameter("m_clearance_fit_mm", "mm", 0.3, 0.2, 5, "Default assembly clearance", "manufacturing", "template"),
        ]

    def _extract_first_number(self, text: str) -> float | None:
        import re

        match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
        if match is None:
            return None
        value = float(match.group(0))
        return int(value) if value.is_integer() else value

    def _raise_for_missing_prompt_path(self, path: str | None, tool: str) -> None:
        if path is None:
            raise ValidationError(f"{tool} requires an active or newly created FreeCAD document path")

    def _load_default_rules(self) -> RuleEngine:
        try:
            return RuleEngine.from_yaml_dir(files("freecad_mcp.resources.material_rules"))
        except ModuleNotFoundError:
            rule_dir = Path(__file__).resolve().parents[3] / "data" / "material_rules"
            return RuleEngine.from_yaml_dir(rule_dir)

    def _project_path(self, project_name: str, workspace: str | None) -> Path | None:
        if workspace is None:
            return None
        root = Path(workspace)
        return root / project_name / f"{project_name}.FCStd"

    def _record_operation(self, tool_name: str, result: dict[str, Any]) -> None:
        if result.get("ok") is False:
            return
        self.workspace.mkdir(parents=True, exist_ok=True)
        recompute_report = result.get("recompute_report")
        recompute_path = None
        if isinstance(recompute_report, dict):
            artifact_dir = self.workspace / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            recompute_path = artifact_dir / f"{result.get('doc_id', 'document')}_recompute_report.json"
            recompute_path.write_text(json.dumps(recompute_report, indent=2, sort_keys=True), encoding="utf-8")
        log_dir = self.workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "ok": True,
            "doc_id": result.get("doc_id"),
            "path": result.get("path"),
            "recompute_report_path": str(recompute_path) if recompute_path else None,
        }
        with (log_dir / "operations.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
