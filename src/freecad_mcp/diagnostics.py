"""Environment diagnostics and smoke-test helpers."""

from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from freecad_mcp.adapter import FreeCADAdapter
from freecad_mcp.models import Parameter
from freecad_mcp.orchestration import FreeCADMCPService


def doctor_report() -> dict[str, Any]:
    freecad_spec = importlib.util.find_spec("FreeCAD")
    freecadcmd = find_freecadcmd()
    freecad_usable = freecad_spec is not None or freecadcmd is not None
    report = {
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "packages": {
            "freecad_mcp": _package_version("freecad-mcp"),
            "mcp": _package_version("mcp"),
        },
        "freecad": {
            "usable": freecad_usable,
            "python_module_importable": freecad_spec is not None,
            "python_module_origin": getattr(freecad_spec, "origin", None) if freecad_spec else None,
            "freecadcmd": str(freecadcmd) if freecadcmd else None,
        },
        "workbench": {
            "module_path": str(Path(__file__).resolve().parent / "workbench"),
            "init_gui_exists": (Path(__file__).resolve().parent / "workbench" / "InitGui.py").exists(),
            "addon_package_xml_exists": (Path(__file__).resolve().parents[2] / "package.xml").exists(),
        },
        "assembly": _assembly_report(freecad_spec is not None),
        "exporters": _exporter_report(freecad_spec is not None),
    }
    report["ok"] = bool(report["packages"]["mcp"]["installed"] and report["workbench"]["init_gui_exists"])
    return report


def workbench_verify_report() -> dict[str, Any]:
    report = doctor_report()
    required = {
        "freecad_usable": report["freecad"]["usable"],
        "workbench_init_gui": report["workbench"]["init_gui_exists"],
        "addon_metadata": report["workbench"]["addon_package_xml_exists"],
        "native_assembly": report["assembly"]["native_module_available"] or report["freecad"]["freecadcmd"] is not None,
    }
    report["verification"] = required
    report["ok"] = all(required.values())
    return report


def smoke_test(workspace: str | Path, require_freecad: bool = False) -> dict[str, Any]:
    workspace_path = Path(workspace)
    adapter = FreeCADAdapter(workspace=workspace_path, prefer_real_freecad=True, require_real_freecad=require_freecad)
    service = FreeCADMCPService(adapter=adapter, workspace=workspace_path)
    parameters = [parameter.to_dict() for parameter in basic_bracket_parameters()]
    project = service.project_create("smoke_bracket", parameters)
    project_path = project["path"]
    part = service.part_create_from_template(project_path, "basic_bracket")
    updated = service.param_set(
        project_path,
        basic_bracket_parameters()[0].to_dict() | {"value": 160, "source": "user"},
    )
    listed = service.param_list(project_path)
    rules = service.design_check_rules(listed["parameters"])
    assembly = service.assembly_create(project_path, "Smoke Assembly")
    link = service.assembly_insert_link(project_path, {"part_id": "bracket", "name": "Bracket", "quantity": 1})
    solved = service.assembly_solve(project_path)
    bom = service.assembly_bom(project_path)
    step = service.project_export(project_path, str(workspace_path / "exports" / "smoke_bracket.step"), "STEP")
    stl = service.project_export(project_path, str(workspace_path / "exports" / "smoke_bracket.stl"), "STL")
    return {
        "ok": True,
        "mode": "freecad" if project.get("freecad_available") else "mock",
        "project": project,
        "part": part,
        "updated_parameter": updated,
        "parameter_count": len(listed["parameters"]),
        "rule_result_count": len(rules["results"]),
        "assembly": assembly,
        "assembly_link": link,
        "assembly_solve": solved,
        "bom_count": len(bom["bom"]),
        "exports": [step, stl],
        "operation_log": str(workspace_path / "logs" / "operations.jsonl"),
    }


def smoke_test_via_freecadcmd(workspace: str | Path, freecadcmd: str | Path | None = None) -> dict[str, Any]:
    command = Path(freecadcmd) if freecadcmd is not None else find_freecadcmd()
    if command is None:
        raise FileNotFoundError("Could not locate FreeCADCmd/freecadcmd")
    package_path = Path(__file__).resolve().parents[1]
    workspace_path = Path(workspace)
    marker_start = "FREECAD_MCP_SMOKE_JSON_START"
    marker_end = "FREECAD_MCP_SMOKE_JSON_END"
    script = f"""
import json
from pathlib import Path
from freecad_mcp.diagnostics import smoke_test
payload = smoke_test(Path({str(workspace_path)!r}), require_freecad=True)
print({marker_start!r})
print(json.dumps(payload, indent=2, sort_keys=True))
print({marker_end!r})
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        completed = subprocess.run(
            [str(command), "-P", str(package_path), str(script_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        script_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "freecadcmd smoke test failed").strip())
    output = completed.stdout
    if marker_start not in output or marker_end not in output:
        raise RuntimeError(f"Could not parse freecadcmd smoke-test output:\n{output}")
    payload_text = output.split(marker_start, 1)[1].split(marker_end, 1)[0].strip()
    payload = json.loads(payload_text)
    payload["freecadcmd"] = str(command)
    return payload


def basic_bracket_parameters() -> list[Parameter]:
    return [
        Parameter("p_base_len_mm", "mm", 120, 20, 400, "Overall bracket base length", "geometry", "template"),
        Parameter("p_base_w_mm", "mm", 40, 10, 200, "Overall bracket base width", "geometry", "template"),
        Parameter("p_wall_thickness_mm", "mm", 3, 1.2, 20, "Nominal wall thickness", "geometry", "template"),
        Parameter("m_clearance_fit_mm", "mm", 0.3, 0.2, 5, "Default assembly clearance", "manufacturing", "template"),
    ]


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def find_freecadcmd() -> Path | None:
    for executable in ("FreeCADCmd", "freecadcmd", "FreeCAD", "freecad"):
        found = shutil.which(executable)
        if found:
            return Path(found)
    candidates = [
        Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"),
        Path("/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd"),
        Path("/Applications/FreeCAD.app/Contents/MacOS/FreeCAD"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _package_version(package_name: str) -> dict[str, Any]:
    try:
        return {"installed": True, "version": version(package_name)}
    except PackageNotFoundError:
        return {"installed": False, "version": None}


def _exporter_report(can_import_freecad: bool) -> dict[str, Any]:
    if not can_import_freecad:
        return {
            "Import": False,
            "Mesh": False,
            "importDXF": False,
        }
    return {name: importlib.util.find_spec(name) is not None for name in ("Import", "Mesh", "importDXF")}


def _assembly_report(can_import_freecad: bool) -> dict[str, Any]:
    if not can_import_freecad:
        return {"native_module_available": False, "joint_object_available": False}
    return {
        "native_module_available": importlib.util.find_spec("Assembly") is not None,
        "joint_object_available": importlib.util.find_spec("JointObject") is not None,
    }
