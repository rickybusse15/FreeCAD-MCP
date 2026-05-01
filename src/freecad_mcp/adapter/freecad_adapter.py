"""Lazy FreeCAD adapter with a deterministic fallback for tests."""

from __future__ import annotations

import json
import sys
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from freecad_mcp.models import AssemblyJoint, AssemblyMate, AssemblyPart, Parameter, RecomputeReport


class FreeCADUnavailableError(RuntimeError):
    """Raised when a real FreeCAD operation is requested without FreeCAD."""


class FreeCADAdapter:
    """Small adapter around FreeCAD APIs.

    FreeCAD is imported only when a real document operation needs it. When it is
    not installed, the adapter writes deterministic JSON-backed stand-ins so the
    MCP and orchestration layers remain testable on ordinary Python installs.
    """

    def __init__(
        self,
        workspace: str | Path = "workspace",
        prefer_real_freecad: bool = True,
        require_real_freecad: bool = False,
    ) -> None:
        self.workspace = Path(workspace)
        self.prefer_real_freecad = prefer_real_freecad
        self.require_real_freecad = require_real_freecad
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._freecad: Any | None = None

    @property
    def is_available(self) -> bool:
        try:
            self._load_freecad()
        except FreeCADUnavailableError:
            return False
        return True

    @property
    def runtime_mode(self) -> str:
        if self.prefer_real_freecad and self.is_available:
            return "freecad"
        if self.require_real_freecad:
            return "unavailable"
        return "mock"

    def runtime_status(self) -> dict[str, Any]:
        return {
            "runtime_mode": self.runtime_mode,
            "freecad_available": self.is_available,
            "prefer_real_freecad": self.prefer_real_freecad,
            "require_real_freecad": self.require_real_freecad,
        }

    def _runtime_fields(self) -> dict[str, Any]:
        mode = self.runtime_mode
        return {"runtime_mode": mode, "freecad_available": mode == "freecad"}

    def create_project(
        self,
        project_name: str,
        parameters: list[Parameter] | None = None,
        path: str | Path | None = None,
    ) -> dict[str, Any]:
        parameters = parameters or []
        project_path = self._project_path(project_name, path)
        project_path.parent.mkdir(parents=True, exist_ok=True)

        if self._use_real_freecad():
            return self._create_real_project(project_name, parameters, project_path)

        state = {
            "doc_id": project_name,
            "format": "freecad-mcp-mock-fcstd",
            "parameters": [param.to_dict() for param in parameters],
            "features": [],
            "assembly": None,
        }
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "doc_id": project_name,
            "path": str(project_path),
            "freecad_available": False,
            "recompute_report": self._mock_recompute(project_name).to_dict(),
            **self._runtime_fields(),
        }

    def open_project(self, path: str | Path) -> dict[str, Any]:
        project_path = Path(path)
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(project_path))
            return {"doc_id": doc.Name, "path": str(project_path), **self._runtime_fields()}

        state = self._read_mock_state(project_path)
        return {"doc_id": state["doc_id"], "path": str(project_path), **self._runtime_fields()}

    def save_project(self, path: str | Path) -> dict[str, Any]:
        project_path = Path(path)
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.ActiveDocument or fc.openDocument(str(project_path))
            if doc is None:
                raise RuntimeError("No active FreeCAD document to save")
            doc.saveAs(str(project_path))
            return {"doc_id": doc.Name, "path": str(project_path), **self._runtime_fields()}

        state = self._read_mock_state(project_path)
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"doc_id": state["doc_id"], "path": str(project_path), **self._runtime_fields()}

    def export_project(self, path: str | Path, output_path: str | Path, format: str) -> dict[str, Any]:
        project_path = Path(path)
        export_path = Path(output_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = format.lower()
        if normalized not in {"step", "stl", "dxf"}:
            raise ValueError("format must be one of: STEP, STL, DXF")

        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(project_path))
            objects = list(getattr(doc, "Objects", []))
            try:
                if normalized == "step":
                    import Import  # type: ignore[import-not-found]

                    Import.export(objects, str(export_path))
                elif normalized == "stl":
                    import Mesh  # type: ignore[import-not-found]

                    Mesh.export(objects, str(export_path))
                else:
                    import importDXF  # type: ignore[import-not-found]

                    importDXF.export(objects, str(export_path))
            except Exception as exc:
                return {
                    "ok": False,
                    "doc_id": doc.Name,
                    "path": str(export_path),
                    "format": normalized,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                    **self._runtime_fields(),
                }
            return {"ok": True, "doc_id": doc.Name, "path": str(export_path), "format": normalized, **self._runtime_fields()}

        state = self._read_mock_state(project_path)
        export_path.write_text(
            json.dumps({"source": str(project_path), "format": normalized, "doc_id": state["doc_id"]}, indent=2),
            encoding="utf-8",
        )
        return {"doc_id": state["doc_id"], "path": str(export_path), "format": normalized, **self._runtime_fields()}

    def list_parameters(self, path: str | Path) -> list[dict[str, Any]]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            sheet = self._find_spreadsheet(doc)
            if sheet is None:
                return []
            return self._read_sheet_parameters(sheet)
        return list(self._read_mock_state(Path(path)).get("parameters", []))

    def set_parameter(self, path: str | Path, parameter: Parameter) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            sheet = self._find_spreadsheet(doc) or doc.addObject("Spreadsheet::Sheet", "Spreadsheet")
            self._write_sheet_parameter(sheet, parameter)
            recompute_report = self._recompute_document(doc)
            if recompute_report.recompute_success:
                doc.saveAs(str(path))
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "parameter": parameter.to_dict(),
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        state = self._read_mock_state(Path(path))
        params = [item for item in state.get("parameters", []) if item["name"] != parameter.name]
        params.append(parameter.to_dict())
        state["parameters"] = sorted(params, key=lambda item: item["name"])
        Path(path).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"ok": True, "doc_id": state["doc_id"], "parameter": parameter.to_dict(), **self._runtime_fields()}

    def create_part_from_template(self, path: str | Path, template_name: str) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            feature = self._create_real_basic_bracket(doc, template_name)
            recompute_report = self._recompute_document(doc)
            if recompute_report.recompute_success:
                doc.saveAs(str(path))
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "template_name": template_name,
                "feature": feature,
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        state = self._read_mock_state(Path(path))
        feature = {"type": "template_part", "template_name": template_name}
        state.setdefault("features", []).append(feature)
        Path(path).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "ok": True,
            "doc_id": state["doc_id"],
            "template_name": template_name,
            "recompute_report": self._mock_recompute(state["doc_id"]).to_dict(),
            **self._runtime_fields(),
        }

    def create_assembly(self, path: str | Path, assembly_name: str) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            self._start_transaction(fc, "Create MCP assembly")
            try:
                assembly = self._ensure_real_assembly_object(doc, assembly_name)
                state = self._state_from_real_assembly(assembly)
                self._write_real_assembly_state(assembly, state)
                recompute_report = self._recompute_document(doc)
                if recompute_report.recompute_success:
                    doc.saveAs(str(path))
                    self._close_transaction(fc)
                else:
                    self._abort_transaction(fc)
            except Exception:
                self._abort_transaction(fc)
                raise
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "assembly": state,
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        project_path = Path(path)
        state = self._read_mock_state(project_path)
        assembly = self._empty_assembly_state(assembly_name)
        state["assembly"] = assembly
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "ok": True,
            "doc_id": state["doc_id"],
            "assembly": assembly,
            "recompute_report": self._mock_recompute(state["doc_id"]).to_dict(),
            **self._runtime_fields(),
        }

    def add_assembly_part(self, path: str | Path, part: AssemblyPart) -> dict[str, Any]:
        return self.insert_assembly_link(path, part)

    def insert_assembly_link(self, path: str | Path, part: AssemblyPart) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            self._start_transaction(fc, "Insert MCP assembly link")
            try:
                assembly = self._ensure_real_assembly_object(doc, "MCP Assembly")
                source = self._resolve_link_source(doc, part)
                links = self._create_real_part_links(doc, assembly, part, source)
                state = self._state_from_real_assembly(assembly)
                self._upsert_assembly_part(state, part)
                self._write_real_assembly_state(assembly, state)
                recompute_report = self._recompute_document(doc)
                if recompute_report.recompute_success:
                    doc.saveAs(str(path))
                    self._close_transaction(fc)
                else:
                    self._abort_transaction(fc)
            except Exception:
                self._abort_transaction(fc)
                raise
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "part": part.to_dict(),
                "links": links,
                "assembly": state,
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        project_path = Path(path)
        state = self._read_mock_state(project_path)
        assembly = self._ensure_mock_assembly(state)
        self._upsert_assembly_part(assembly, part)
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"ok": True, "doc_id": state["doc_id"], "part": part.to_dict(), "assembly": assembly, **self._runtime_fields()}

    def add_assembly_mate(self, path: str | Path, mate: AssemblyMate) -> dict[str, Any]:
        joint = AssemblyJoint(
            joint_id=mate.mate_id,
            parent_part_id=mate.parent_part_id,
            child_part_id=mate.child_part_id,
            joint_type=mate.mate_type,
            parent_ref=mate.parent_ref,
            child_ref=mate.child_ref,
            offset=mate.offset,
            unit=mate.unit,
        )
        return self.create_assembly_joint(path, joint)

    def ground_assembly_part(self, path: str | Path, part_id: str) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            self._start_transaction(fc, "Ground MCP assembly part")
            try:
                assembly = self._ensure_real_assembly_object(doc, "MCP Assembly")
                target = self._find_real_part_object(assembly, part_id)
                if target is None:
                    raise ValueError(f"Unknown assembly part: {part_id}")
                joint = self._create_real_grounded_joint(assembly, part_id, target)
                state = self._state_from_real_assembly(assembly)
                state.setdefault("grounded", [])
                if part_id not in state["grounded"]:
                    state["grounded"].append(part_id)
                self._write_real_assembly_state(assembly, state)
                recompute_report = self._recompute_document(doc)
                if recompute_report.recompute_success:
                    doc.saveAs(str(path))
                    self._close_transaction(fc)
                else:
                    self._abort_transaction(fc)
            except Exception:
                self._abort_transaction(fc)
                raise
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "part_id": part_id,
                "joint": joint,
                "assembly": state,
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        project_path = Path(path)
        state = self._read_mock_state(project_path)
        assembly = self._ensure_mock_assembly(state)
        part_ids = {part.get("part_id") for part in assembly.get("parts", [])}
        if part_id not in part_ids:
            raise ValueError(f"Unknown assembly part: {part_id}")
        assembly.setdefault("grounded", [])
        if part_id not in assembly["grounded"]:
            assembly["grounded"].append(part_id)
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"ok": True, "doc_id": state["doc_id"], "part_id": part_id, "assembly": assembly, **self._runtime_fields()}

    def create_assembly_joint(self, path: str | Path, joint: AssemblyJoint) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            self._start_transaction(fc, "Create MCP assembly joint")
            try:
                assembly = self._ensure_real_assembly_object(doc, "MCP Assembly")
                self._create_real_joint(assembly, joint)
                state = self._state_from_real_assembly(assembly)
                self._upsert_assembly_joint(state, joint)
                self._write_real_assembly_state(assembly, state)
                recompute_report = self._recompute_document(doc)
                if recompute_report.recompute_success:
                    doc.saveAs(str(path))
                    self._close_transaction(fc)
                else:
                    self._abort_transaction(fc)
            except Exception:
                self._abort_transaction(fc)
                raise
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "joint": joint.to_dict(),
                "assembly": state,
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        project_path = Path(path)
        state = self._read_mock_state(project_path)
        assembly = self._ensure_mock_assembly(state)
        self._upsert_assembly_joint(assembly, joint)
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"ok": True, "doc_id": state["doc_id"], "joint": joint.to_dict(), "assembly": assembly, **self._runtime_fields()}

    def update_assembly_joint(self, path: str | Path, joint: AssemblyJoint) -> dict[str, Any]:
        self.delete_assembly_joint(path, joint.joint_id)
        return self.create_assembly_joint(path, joint)

    def delete_assembly_joint(self, path: str | Path, joint_id: str) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            self._start_transaction(fc, "Delete MCP assembly joint")
            try:
                assembly = self._ensure_real_assembly_object(doc, "MCP Assembly")
                removed = self._delete_real_joint(assembly, joint_id)
                state = self._state_from_real_assembly(assembly)
                state["joints"] = [item for item in state.get("joints", []) if item.get("joint_id") != joint_id]
                state["mates"] = [item for item in state.get("mates", []) if item.get("mate_id") != joint_id]
                self._write_real_assembly_state(assembly, state)
                recompute_report = self._recompute_document(doc)
                if recompute_report.recompute_success:
                    doc.saveAs(str(path))
                    self._close_transaction(fc)
                else:
                    self._abort_transaction(fc)
            except Exception:
                self._abort_transaction(fc)
                raise
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "joint_id": joint_id,
                "removed": removed,
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        project_path = Path(path)
        state = self._read_mock_state(project_path)
        assembly = self._ensure_mock_assembly(state)
        before = len(assembly.get("joints", []))
        assembly["joints"] = [item for item in assembly.get("joints", []) if item.get("joint_id") != joint_id]
        assembly["mates"] = [item for item in assembly.get("mates", []) if item.get("mate_id") != joint_id]
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"ok": True, "doc_id": state["doc_id"], "joint_id": joint_id, "removed": before != len(assembly["joints"]), **self._runtime_fields()}

    def list_assembly_joints(self, path: str | Path) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            assembly = self._find_real_assembly_object(doc)
            state = self._state_from_real_assembly(assembly) if assembly is not None else self._empty_assembly_state()
            return {"doc_id": doc.Name, "joints": state.get("joints", []), "grounded": state.get("grounded", []), **self._runtime_fields()}

        state = self._read_mock_state(Path(path))
        assembly = self._ensure_mock_assembly(state)
        return {"doc_id": state["doc_id"], "joints": assembly.get("joints", []), "grounded": assembly.get("grounded", []), **self._runtime_fields()}

    def solve_assembly(self, path: str | Path) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            assembly = self._ensure_real_assembly_object(doc, "MCP Assembly")
            start = time.monotonic()
            errors: list[str] = []
            try:
                assembly.recompute(True)
                doc.recompute()
                solved = True
                doc.saveAs(str(path))
            except Exception as exc:
                solved = False
                errors.append(f"{type(exc).__name__}: {exc}")
            status = {
                "solved": solved,
                "duration_ms": int((time.monotonic() - start) * 1000),
                "errors": errors,
            }
            state = self._state_from_real_assembly(assembly)
            state["solve_status"] = status
            self._write_real_assembly_state(assembly, state)
            return {"ok": solved, "doc_id": doc.Name, "solve_status": status, "assembly": state, **self._runtime_fields()}

        project_path = Path(path)
        state = self._read_mock_state(project_path)
        assembly = self._ensure_mock_assembly(state)
        status = {"solved": True, "duration_ms": 0, "errors": []}
        assembly["solve_status"] = status
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"ok": True, "doc_id": state["doc_id"], "solve_status": status, "assembly": assembly, **self._runtime_fields()}

    def assembly_bom(self, path: str | Path) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            assembly = self._find_real_assembly_object(doc)
            state = self._state_from_real_assembly(assembly) if assembly is not None else self._empty_assembly_state()
            return {"doc_id": doc.Name, "bom": self._build_bom(state), **self._runtime_fields()}

        state = self._read_mock_state(Path(path))
        assembly = self._ensure_mock_assembly(state)
        return {"doc_id": state["doc_id"], "bom": self._build_bom(assembly), **self._runtime_fields()}

    def assembly_explode_view(self, path: str | Path, distance_mm: float = 25) -> dict[str, Any]:
        if self._use_real_freecad():
            fc = self._load_freecad()
            doc = fc.openDocument(str(path))
            assembly = self._ensure_real_assembly_object(doc, "MCP Assembly")
            state = self._state_from_real_assembly(assembly)
            exploded_view = self._build_exploded_view(state, distance_mm)
            state["exploded_view"] = exploded_view
            self._apply_real_exploded_view(assembly, exploded_view)
            self._write_real_assembly_state(assembly, state)
            recompute_report = self._recompute_document(doc)
            if recompute_report.recompute_success:
                doc.saveAs(str(path))
            return {
                "ok": recompute_report.recompute_success,
                "doc_id": doc.Name,
                "exploded_view": exploded_view,
                "recompute_report": recompute_report.to_dict(),
                **self._runtime_fields(),
            }

        project_path = Path(path)
        state = self._read_mock_state(project_path)
        assembly = self._ensure_mock_assembly(state)
        exploded_view = self._build_exploded_view(assembly, distance_mm)
        assembly["exploded_view"] = exploded_view
        project_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return {"ok": True, "doc_id": state["doc_id"], "exploded_view": exploded_view, **self._runtime_fields()}

    def _empty_assembly_state(self, assembly_name: str = "MCP Assembly") -> dict[str, Any]:
        return {
            "name": assembly_name,
            "parts": [],
            "mates": [],
            "joints": [],
            "grounded": [],
            "bom": [],
            "exploded_view": {"enabled": False, "distance_mm": 0, "vectors": []},
            "solve_status": {"solved": None, "duration_ms": 0, "errors": []},
        }

    def _ensure_mock_assembly(self, state: dict[str, Any]) -> dict[str, Any]:
        assembly = state.get("assembly")
        if not isinstance(assembly, dict):
            assembly = self._empty_assembly_state()
            state["assembly"] = assembly
        assembly.setdefault("parts", [])
        assembly.setdefault("mates", [])
        assembly.setdefault("joints", [])
        assembly.setdefault("grounded", [])
        assembly.setdefault("bom", [])
        assembly.setdefault("exploded_view", {"enabled": False, "distance_mm": 0, "vectors": []})
        assembly.setdefault("solve_status", {"solved": None, "duration_ms": 0, "errors": []})
        return assembly

    def _upsert_assembly_part(self, assembly: dict[str, Any], part: AssemblyPart) -> None:
        parts = [item for item in assembly.get("parts", []) if item.get("part_id") != part.part_id]
        parts.append(part.to_dict())
        assembly["parts"] = sorted(parts, key=lambda item: item["part_id"])
        assembly["bom"] = self._build_bom(assembly)

    def _upsert_assembly_mate(self, assembly: dict[str, Any], mate: AssemblyMate) -> None:
        joint = AssemblyJoint(
            joint_id=mate.mate_id,
            parent_part_id=mate.parent_part_id,
            child_part_id=mate.child_part_id,
            joint_type=mate.mate_type,
            parent_ref=mate.parent_ref,
            child_ref=mate.child_ref,
            offset=mate.offset,
            unit=mate.unit,
        )
        self._upsert_assembly_joint(assembly, joint)

    def _upsert_assembly_joint(self, assembly: dict[str, Any], joint: AssemblyJoint) -> None:
        part_ids = {part.get("part_id") for part in assembly.get("parts", [])}
        if joint.parent_part_id not in part_ids:
            raise ValueError(f"Unknown parent assembly part: {joint.parent_part_id}")
        if joint.child_part_id not in part_ids:
            raise ValueError(f"Unknown child assembly part: {joint.child_part_id}")
        joints = [item for item in assembly.get("joints", []) if item.get("joint_id") != joint.joint_id]
        joints.append(joint.to_dict())
        assembly["joints"] = sorted(joints, key=lambda item: item["joint_id"])
        mates = [item for item in assembly.get("mates", []) if item.get("mate_id") != joint.joint_id]
        mates.append(
            {
                "mate_id": joint.joint_id,
                "parent_part_id": joint.parent_part_id,
                "child_part_id": joint.child_part_id,
                "mate_type": joint.joint_type,
                "parent_ref": joint.parent_ref,
                "child_ref": joint.child_ref,
                "offset": joint.offset,
                "unit": joint.unit,
            }
        )
        assembly["mates"] = sorted(mates, key=lambda item: item["mate_id"])

    def _build_bom(self, assembly: dict[str, Any]) -> list[dict[str, Any]]:
        totals: dict[tuple[str, str, str], dict[str, Any]] = {}
        for part in assembly.get("parts", []):
            key = (str(part.get("part_id", "")), str(part.get("name", "")), str(part.get("material", "")))
            quantity = int(part.get("quantity", 1))
            if key not in totals:
                totals[key] = {
                    "part_id": key[0],
                    "name": key[1],
                    "material": key[2],
                    "quantity": 0,
                    "source_path": part.get("path"),
                }
            totals[key]["quantity"] += quantity
        return sorted(totals.values(), key=lambda item: item["part_id"])

    def _build_exploded_view(self, assembly: dict[str, Any], distance_mm: float) -> dict[str, Any]:
        vectors = []
        for index, part in enumerate(assembly.get("parts", []), start=1):
            vectors.append(
                {
                    "part_id": part.get("part_id", ""),
                    "x_mm": float(distance_mm) * index,
                    "y_mm": 0,
                    "z_mm": 0,
                }
            )
        return {"enabled": True, "distance_mm": float(distance_mm), "vectors": vectors}

    def _find_real_assembly_object(self, doc: Any) -> Any | None:
        for obj in getattr(doc, "Objects", []):
            is_assembly = False
            try:
                is_assembly = obj.isDerivedFrom("Assembly::AssemblyObject")
            except Exception:
                is_assembly = getattr(obj, "TypeId", "") == "Assembly::AssemblyObject"
            if is_assembly or hasattr(obj, "MCPAssemblyJson") or getattr(obj, "Name", "") == "MCP_Assembly":
                return obj
        return None

    def _ensure_real_assembly_object(self, doc: Any, assembly_name: str) -> Any:
        existing = self._find_real_assembly_object(doc)
        if existing is not None:
            self._ensure_real_joint_group(existing)
            return existing
        safe_name = self._safe_doc_name(assembly_name) or "MCP_Assembly"
        try:
            assembly = doc.addObject("Assembly::AssemblyObject", safe_name)
        except Exception as exc:
            raise RuntimeError("Unable to create a native FreeCAD Assembly::AssemblyObject") from exc
        if assembly is None:
            raise RuntimeError("Unable to create a FreeCAD assembly container")
        try:
            assembly.Label = assembly_name
        except Exception:
            pass
        self._ensure_real_joint_group(assembly)
        self._ensure_string_property(assembly, "MCPAssemblyJson")
        return assembly

    def _ensure_real_joint_group(self, assembly: Any) -> Any:
        for obj in getattr(assembly, "OutList", []):
            if getattr(obj, "TypeId", "") == "Assembly::JointGroup":
                return obj
        try:
            return assembly.newObject("Assembly::JointGroup", "Joints")
        except Exception as exc:
            raise RuntimeError("Unable to create a native FreeCAD Assembly::JointGroup") from exc

    def _state_from_real_assembly(self, assembly: Any | None) -> dict[str, Any]:
        if assembly is None:
            return self._empty_assembly_state()
        state = self._read_real_assembly_state(assembly) or self._empty_assembly_state(
            str(getattr(assembly, "Label", "MCP Assembly"))
        )
        self._ensure_mock_assembly({"assembly": state})
        link_parts: list[dict[str, Any]] = []
        joints: list[dict[str, Any]] = []
        grounded: list[str] = list(state.get("grounded", []))
        for obj in getattr(assembly, "OutListRecursive", getattr(assembly, "OutList", [])):
            raw = getattr(obj, "MCPPartJson", "") or ""
            if raw:
                try:
                    link_parts.append(json.loads(raw))
                except JSONDecodeError:
                    pass
            if hasattr(obj, "JointType"):
                raw_joint = getattr(obj, "MCPJointJson", "") or ""
                if raw_joint:
                    try:
                        joints.append(json.loads(raw_joint))
                        continue
                    except JSONDecodeError:
                        pass
                joints.append(
                    {
                        "joint_id": getattr(obj, "Label", getattr(obj, "Name", "")),
                        "joint_type": self._mcp_joint_type(str(getattr(obj, "JointType", "fixed"))),
                        "parent_part_id": "",
                        "child_part_id": "",
                        "parent_ref": "",
                        "child_ref": "",
                        "offset": 0,
                        "unit": "mm",
                    }
                )
            if hasattr(obj, "ObjectToGround"):
                target = getattr(obj, "ObjectToGround", None)
                part_id = self._part_id_from_object(target)
                if part_id and part_id not in grounded:
                    grounded.append(part_id)
        if link_parts:
            state["parts"] = sorted({item["part_id"]: item for item in link_parts}.values(), key=lambda item: item["part_id"])
        if joints:
            state["joints"] = sorted({item["joint_id"]: item for item in joints}.values(), key=lambda item: item["joint_id"])
            state["mates"] = [
                {
                    "mate_id": item["joint_id"],
                    "parent_part_id": item.get("parent_part_id", ""),
                    "child_part_id": item.get("child_part_id", ""),
                    "mate_type": item.get("joint_type", "fixed"),
                    "parent_ref": item.get("parent_ref", ""),
                    "child_ref": item.get("child_ref", ""),
                    "offset": item.get("offset", 0),
                    "unit": item.get("unit", "mm"),
                }
                for item in state["joints"]
            ]
        state["grounded"] = sorted(grounded)
        state["bom"] = self._build_bom(state)
        return state

    def _read_real_assembly_state(self, assembly: Any | None) -> dict[str, Any] | None:
        if assembly is None:
            return None
        raw = getattr(assembly, "MCPAssemblyJson", "") or ""
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _write_real_assembly_state(self, assembly: Any, state: dict[str, Any]) -> None:
        self._ensure_string_property(assembly, "MCPAssemblyJson")
        try:
            assembly.MCPAssemblyJson = json.dumps(state, sort_keys=True)
        except Exception:
            pass

    def _resolve_link_source(self, doc: Any, part: AssemblyPart) -> Any:
        if part.path:
            fc = self._load_freecad()
            source_doc = fc.openDocument(str(part.path))
            source = self._first_linkable_object(source_doc)
            if source is None:
                raise ValueError(f"No linkable object found in {part.path}")
            return source
        if part.interface_ref:
            found = self._find_object_by_name_or_label(doc, part.interface_ref)
            if found is not None:
                return found
        found = self._find_object_by_name_or_label(doc, part.name)
        if found is not None:
            return found
        source = self._first_linkable_object(doc)
        if source is None:
            raise ValueError("No linkable part/body/shape exists in the active document")
        return source

    def _first_linkable_object(self, doc: Any) -> Any | None:
        for obj in getattr(doc, "Objects", []):
            if getattr(obj, "TypeId", "") in {"Spreadsheet::Sheet", "Assembly::AssemblyObject"}:
                continue
            try:
                if obj.isDerivedFrom("PartDesign::Body") or obj.isDerivedFrom("Part::Feature") or obj.isDerivedFrom("App::Part"):
                    return obj
            except Exception:
                pass
            if hasattr(obj, "Shape"):
                return obj
        return None

    def _find_object_by_name_or_label(self, doc: Any, value: str) -> Any | None:
        needle = self._normalize_ref_name(value)
        for obj in getattr(doc, "Objects", []):
            if getattr(obj, "Name", "") == needle or getattr(obj, "Label", "") == value or getattr(obj, "Name", "") == value:
                return obj
        return None

    def _create_real_part_links(self, doc: Any, assembly: Any, part: AssemblyPart, source: Any) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []
        quantity = max(1, int(part.quantity))
        for index in range(quantity):
            object_name = self._safe_doc_name(f"part_{part.part_id}" if quantity == 1 else f"part_{part.part_id}_{index + 1}")
            existing = self._find_real_part_object(assembly, part.part_id, object_name=object_name)
            if existing is not None:
                links.append({"name": getattr(existing, "Name", object_name), "part_id": part.part_id})
                continue
            link = assembly.newObject("App::Link", object_name)
            link.LinkedObject = source
            link.Label = part.name if quantity == 1 else f"{part.name} {index + 1}"
            self._ensure_string_property(link, "MCPPartJson")
            link.MCPPartJson = json.dumps(part.to_dict(), sort_keys=True)
            try:
                link.Placement.Base.x = float(index) * 10
            except Exception:
                pass
            links.append({"name": link.Name, "part_id": part.part_id, "linked_object": getattr(source, "Name", "")})
        return links

    def _find_real_part_object(self, assembly: Any, part_id: str, object_name: str | None = None) -> Any | None:
        target_name = object_name or self._safe_doc_name(f"part_{part_id}")
        for obj in getattr(assembly, "OutListRecursive", getattr(assembly, "OutList", [])):
            if getattr(obj, "Name", "") == target_name:
                return obj
            raw = getattr(obj, "MCPPartJson", "") or ""
            if raw:
                try:
                    if json.loads(raw).get("part_id") == part_id:
                        return obj
                except JSONDecodeError:
                    pass
        return None

    def _create_real_grounded_joint(self, assembly: Any, part_id: str, target: Any) -> dict[str, Any]:
        self._ensure_assembly_module_path()
        import JointObject  # type: ignore[import-not-found]

        joint_group = self._ensure_real_joint_group(assembly)
        object_name = self._safe_doc_name(f"Ground_{part_id}")
        for obj in getattr(joint_group, "OutList", []):
            if getattr(obj, "Name", "") == object_name:
                return {"joint_id": obj.Name, "part_id": part_id, "joint_type": "grounded"}
        joint = joint_group.newObject("App::FeaturePython", object_name)
        joint.Label = f"Ground {part_id}"
        JointObject.GroundedJoint(joint, target)
        if getattr(joint, "ViewObject", None) is not None and hasattr(JointObject, "ViewProviderGroundedJoint"):
            try:
                JointObject.ViewProviderGroundedJoint(joint.ViewObject)
            except Exception:
                pass
        return {"joint_id": joint.Name, "part_id": part_id, "joint_type": "grounded"}

    def _create_real_joint(self, assembly: Any, joint_payload: AssemblyJoint) -> Any:
        self._ensure_assembly_module_path()
        import JointObject  # type: ignore[import-not-found]

        joint_group = self._ensure_real_joint_group(assembly)
        self._delete_real_joint(assembly, joint_payload.joint_id)
        native_type = self._native_joint_type(joint_payload.joint_type)
        type_index = JointObject.JointTypes.index(native_type)
        joint = joint_group.newObject("App::FeaturePython", self._safe_doc_name(joint_payload.joint_id))
        joint.Label = joint_payload.joint_id
        JointObject.Joint(joint, type_index)
        if getattr(joint, "ViewObject", None) is not None and hasattr(JointObject, "ViewProviderJoint"):
            try:
                JointObject.ViewProviderJoint(joint.ViewObject)
            except Exception:
                pass
        parent_obj = self._find_real_part_object(assembly, joint_payload.parent_part_id)
        child_obj = self._find_real_part_object(assembly, joint_payload.child_part_id)
        if parent_obj is None:
            raise ValueError(f"Unknown parent assembly part: {joint_payload.parent_part_id}")
        if child_obj is None:
            raise ValueError(f"Unknown child assembly part: {joint_payload.child_part_id}")
        refs = [
            [parent_obj, self._joint_subrefs(joint_payload.parent_ref)],
            [child_obj, self._joint_subrefs(joint_payload.child_ref)],
        ]
        joint.Proxy.setJointConnectors(joint, refs)
        if joint_payload.joint_type == "angle" and hasattr(joint, "Angle"):
            joint.Angle = joint_payload.offset
        if joint_payload.joint_type in {"distance", "rack_pinion", "screw", "gear_belt"} and hasattr(joint, "Distance"):
            joint.Distance = joint_payload.offset
        self._ensure_string_property(joint, "MCPJointJson")
        joint.MCPJointJson = json.dumps(joint_payload.to_dict(), sort_keys=True)
        return joint

    def _delete_real_joint(self, assembly: Any, joint_id: str) -> bool:
        joint_group = self._ensure_real_joint_group(assembly)
        target_names = {self._safe_doc_name(joint_id), joint_id}
        for obj in list(getattr(joint_group, "OutList", [])):
            if getattr(obj, "Name", "") in target_names or getattr(obj, "Label", "") == joint_id:
                joint_group.removeObject(obj)
                doc = getattr(assembly, "Document", None)
                if doc is not None:
                    try:
                        doc.removeObject(obj.Name)
                    except Exception:
                        pass
                return True
        return False

    def _apply_real_exploded_view(self, assembly: Any, exploded_view: dict[str, Any]) -> None:
        vector_by_part = {item.get("part_id"): item for item in exploded_view.get("vectors", [])}
        fc = self._load_freecad()
        for obj in getattr(assembly, "OutListRecursive", getattr(assembly, "OutList", [])):
            part_id = self._part_id_from_object(obj)
            vector = vector_by_part.get(part_id)
            if not vector or not hasattr(obj, "Placement"):
                continue
            try:
                obj.Placement.Base = fc.Vector(float(vector.get("x_mm", 0)), float(vector.get("y_mm", 0)), float(vector.get("z_mm", 0)))
            except Exception:
                pass

    def _part_id_from_object(self, obj: Any | None) -> str | None:
        if obj is None:
            return None
        raw = getattr(obj, "MCPPartJson", "") or ""
        if raw:
            try:
                value = json.loads(raw).get("part_id")
                return str(value) if value else None
            except JSONDecodeError:
                return None
        name = getattr(obj, "Name", "")
        return name[5:] if name.startswith("part_") else name or None

    def _native_joint_type(self, joint_type: str) -> str:
        return {
            "fixed": "Fixed",
            "revolute": "Revolute",
            "cylindrical": "Cylindrical",
            "slider": "Slider",
            "ball": "Ball",
            "distance": "Distance",
            "parallel": "Parallel",
            "perpendicular": "Perpendicular",
            "angle": "Angle",
            "rack_pinion": "RackPinion",
            "screw": "Screw",
            "gear_belt": "Gears",
            "coincident": "Fixed",
            "concentric": "Cylindrical",
        }.get(joint_type, "Fixed")

    def _mcp_joint_type(self, native_type: str) -> str:
        return {
            "Fixed": "fixed",
            "Revolute": "revolute",
            "Cylindrical": "cylindrical",
            "Slider": "slider",
            "Ball": "ball",
            "Distance": "distance",
            "Parallel": "parallel",
            "Perpendicular": "perpendicular",
            "Angle": "angle",
            "RackPinion": "rack_pinion",
            "Screw": "screw",
            "Gears": "gear_belt",
            "Belt": "gear_belt",
        }.get(native_type, native_type.lower())

    def _joint_subrefs(self, ref: str) -> list[str]:
        if not ref:
            return ["", ""]
        sub = ref.split(".", 1)[1] if "." in ref else ref
        return [sub, sub]

    def _normalize_ref_name(self, value: str) -> str:
        return value.split(".", 1)[0] if "." in value else value

    def _ensure_assembly_module_path(self) -> None:
        try:
            import FreeCAD  # type: ignore[import-not-found]

            home = Path(FreeCAD.getHomePath())
        except Exception:
            return
        assembly_path = home / "Mod" / "Assembly"
        if assembly_path.exists() and str(assembly_path) not in sys.path:
            sys.path.insert(0, str(assembly_path))

    def _create_real_part_placeholder(self, doc: Any, assembly: Any, part: AssemblyPart) -> None:
        object_name = self._safe_doc_name(f"part_{part.part_id}")
        for obj in getattr(doc, "Objects", []):
            if getattr(obj, "Name", "") == object_name:
                return
        try:
            placeholder = doc.addObject("App::DocumentObjectGroup", object_name)
            placeholder.Label = part.name
            self._ensure_string_property(placeholder, "MCPPartJson")
            placeholder.MCPPartJson = json.dumps(part.to_dict(), sort_keys=True)
            add_object = getattr(assembly, "addObject", None)
            if add_object is not None:
                add_object(placeholder)
        except Exception:
            return

    def _ensure_string_property(self, obj: Any, property_name: str) -> None:
        if hasattr(obj, property_name):
            return
        add_property = getattr(obj, "addProperty", None)
        if add_property is None:
            return
        try:
            add_property("App::PropertyString", property_name, "MCP", "FreeCAD-MCP metadata")
        except Exception:
            pass

    def _start_transaction(self, fc: Any, name: str) -> None:
        try:
            fc.setActiveTransaction(name)
        except Exception:
            pass

    def _close_transaction(self, fc: Any) -> None:
        try:
            fc.closeActiveTransaction()
        except Exception:
            pass

    def _abort_transaction(self, fc: Any) -> None:
        try:
            fc.abortTransaction()
        except Exception:
            pass

    def _load_freecad(self) -> Any:
        if self._freecad is not None:
            return self._freecad
        try:
            import FreeCAD  # type: ignore[import-not-found]
        except ImportError as exc:
            raise FreeCADUnavailableError("FreeCAD Python module is not available") from exc
        self._freecad = FreeCAD
        return self._freecad

    def _use_real_freecad(self) -> bool:
        if not self.prefer_real_freecad and not self.require_real_freecad:
            return False
        available = self.is_available
        if self.require_real_freecad and not available:
            raise FreeCADUnavailableError("Real FreeCAD mode was required, but FreeCAD is not importable")
        return self.prefer_real_freecad and available

    def _create_real_project(self, project_name: str, parameters: list[Parameter], path: Path) -> dict[str, Any]:
        fc = self._load_freecad()
        doc = fc.newDocument(self._safe_doc_name(project_name))
        sheet = doc.addObject("Spreadsheet::Sheet", "Spreadsheet")
        headers = ["Name", "Expression", "Unit", "Value", "Min", "Max", "Description", "Category"]
        for col, header in enumerate(headers, start=1):
            sheet.set(f"{chr(64 + col)}1", header)
        for row, param in enumerate(parameters, start=2):
            self._write_sheet_parameter(sheet, param, row=row)
        recompute_report = self._recompute_document(doc)
        doc.saveAs(str(path))
        return {
            "doc_id": doc.Name,
            "path": str(path),
            "freecad_available": True,
            "recompute_report": recompute_report.to_dict(),
            **self._runtime_fields(),
        }

    def _read_mock_state(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(path)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, JSONDecodeError) as exc:
            raise FreeCADUnavailableError(
                f"{path} is not a mock FreeCAD-MCP JSON document. Install/import FreeCAD or run with real FreeCAD mode."
            ) from exc

    def _find_spreadsheet(self, doc: Any) -> Any | None:
        for obj in getattr(doc, "Objects", []):
            if getattr(obj, "Name", "") == "Spreadsheet" or getattr(obj, "TypeId", "") == "Spreadsheet::Sheet":
                return obj
        return None

    def _read_sheet_parameters(self, sheet: Any) -> list[dict[str, Any]]:
        parameters: list[dict[str, Any]] = []
        for row in range(2, 1000):
            name = self._sheet_get(sheet, f"A{row}")
            if not name:
                break
            parameters.append(
                {
                    "name": name,
                    "unit": self._sheet_get(sheet, f"C{row}") or "mm",
                    "value": self._coerce_sheet_value(self._sheet_get(sheet, f"D{row}")),
                    "min": self._coerce_optional_number(self._sheet_get(sheet, f"E{row}")),
                    "max": self._coerce_optional_number(self._sheet_get(sheet, f"F{row}")),
                    "description": self._sheet_get(sheet, f"G{row}"),
                    "category": self._sheet_get(sheet, f"H{row}") or "general",
                    "source": "user",
                }
            )
        return parameters

    def _write_sheet_parameter(self, sheet: Any, parameter: Parameter, row: int | None = None) -> None:
        row = row or self._find_parameter_row(sheet, parameter.name) or self._next_empty_row(sheet)
        values = [
            parameter.name,
            str(parameter.value),
            parameter.unit,
            str(parameter.value),
            "" if parameter.min is None else str(parameter.min),
            "" if parameter.max is None else str(parameter.max),
            parameter.description,
            parameter.category,
        ]
        for col, value in enumerate(values, start=1):
            sheet.set(f"{chr(64 + col)}{row}", value)
        if hasattr(sheet, "setAlias"):
            try:
                sheet.setAlias(f"D{row}", parameter.name)
            except Exception:
                pass

    def _create_real_basic_bracket(self, doc: Any, template_name: str) -> dict[str, Any]:
        try:
            return self._create_sketch_pad_body(doc, template_name)
        except Exception as exc:
            try:
                fallback = self._create_additive_box_body(doc, template_name)
            except Exception as fallback_exc:
                fallback = self._create_part_box(doc, template_name)
                fallback["fallback_reason"] = (
                    f"sketch_pad={type(exc).__name__}: {exc}; "
                    f"additive_box={type(fallback_exc).__name__}: {fallback_exc}"
                )
                return fallback
            fallback["fallback_reason"] = f"{type(exc).__name__}: {exc}"
            return fallback

    def _create_sketch_pad_body(self, doc: Any, template_name: str) -> dict[str, Any]:
        fc = self._load_freecad()
        import Part  # type: ignore[import-not-found]
        import Sketcher  # type: ignore[import-not-found]

        body = doc.addObject("PartDesign::Body", self._safe_doc_name(f"{template_name}_body"))
        sketch = body.newObject("Sketcher::SketchObject", "BaseSketch")
        vector = fc.Vector
        line_ids = [
            sketch.addGeometry(Part.LineSegment(vector(0, 0, 0), vector(120, 0, 0)), False),
            sketch.addGeometry(Part.LineSegment(vector(120, 0, 0), vector(120, 40, 0)), False),
            sketch.addGeometry(Part.LineSegment(vector(120, 40, 0), vector(0, 40, 0)), False),
            sketch.addGeometry(Part.LineSegment(vector(0, 40, 0), vector(0, 0, 0)), False),
        ]
        sketch.addConstraint(Sketcher.Constraint("Coincident", line_ids[0], 2, line_ids[1], 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", line_ids[1], 2, line_ids[2], 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", line_ids[2], 2, line_ids[3], 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", line_ids[3], 2, line_ids[0], 1))
        sketch.addConstraint(Sketcher.Constraint("Horizontal", line_ids[0]))
        sketch.addConstraint(Sketcher.Constraint("Horizontal", line_ids[2]))
        sketch.addConstraint(Sketcher.Constraint("Vertical", line_ids[1]))
        sketch.addConstraint(Sketcher.Constraint("Vertical", line_ids[3]))
        width_constraint = sketch.addConstraint(Sketcher.Constraint("DistanceX", line_ids[0], 1, line_ids[0], 2, 120))
        height_constraint = sketch.addConstraint(Sketcher.Constraint("DistanceY", line_ids[1], 1, line_ids[1], 2, 40))
        self._set_constraint_expression(sketch, width_constraint, "p_base_len_mm", "Spreadsheet.p_base_len_mm")
        self._set_constraint_expression(sketch, height_constraint, "p_base_w_mm", "Spreadsheet.p_base_w_mm")
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 3
        self._set_expression_if_available(pad, "Length", "Spreadsheet.p_wall_thickness_mm")
        return {"body": body.Name, "sketch": sketch.Name, "feature": pad.Name, "feature_type": "sketch_pad"}

    def _create_additive_box_body(self, doc: Any, template_name: str) -> dict[str, Any]:
        body = doc.addObject("PartDesign::Body", self._safe_doc_name(f"{template_name}_body"))
        box = body.newObject("PartDesign::AdditiveBox", "BasicBracket")
        self._set_expression_if_available(box, "Length", "Spreadsheet.p_base_len_mm")
        self._set_expression_if_available(box, "Width", "Spreadsheet.p_base_w_mm")
        self._set_expression_if_available(box, "Height", "Spreadsheet.p_wall_thickness_mm")
        return {"body": body.Name, "feature": box.Name, "feature_type": "additive_box"}

    def _create_part_box(self, doc: Any, template_name: str) -> dict[str, Any]:
        box = doc.addObject("Part::Box", self._safe_doc_name(template_name))
        self._set_expression_if_available(box, "Length", "Spreadsheet.p_base_len_mm")
        self._set_expression_if_available(box, "Width", "Spreadsheet.p_base_w_mm")
        self._set_expression_if_available(box, "Height", "Spreadsheet.p_wall_thickness_mm")
        return {"feature": box.Name, "feature_type": "part_box"}

    def _set_constraint_expression(self, sketch: Any, index: int, name: str, expression: str) -> None:
        try:
            sketch.renameConstraint(index, name)
            sketch.setExpression(f"Constraints.{name}", expression)
            return
        except Exception:
            pass
        try:
            sketch.setExpression(f"Constraints[{index}]", expression)
        except Exception:
            pass

    def _recompute_document(self, doc: Any) -> RecomputeReport:
        start = time.monotonic()
        try:
            doc.recompute()
        except Exception as exc:
            return RecomputeReport(
                doc_id=getattr(doc, "Name", "document"),
                recompute_success=False,
                duration_ms=int((time.monotonic() - start) * 1000),
                topology_changes=[],
                constraint_status="failed",
                errors=[f"{type(exc).__name__}: {exc}"],
            )
        return RecomputeReport(
            doc_id=getattr(doc, "Name", "document"),
            recompute_success=True,
            duration_ms=int((time.monotonic() - start) * 1000),
            topology_changes=[],
            constraint_status="ok",
            errors=[],
        )

    def _find_parameter_row(self, sheet: Any, name: str) -> int | None:
        for row in range(2, 1000):
            current = self._sheet_get(sheet, f"A{row}")
            if current == name:
                return row
            if not current:
                return None
        return None

    def _next_empty_row(self, sheet: Any) -> int:
        for row in range(2, 1000):
            if not self._sheet_get(sheet, f"A{row}"):
                return row
        raise RuntimeError("Spreadsheet parameter table is full")

    def _sheet_get(self, sheet: Any, cell: str) -> str:
        for method_name in ("get", "getContents"):
            method = getattr(sheet, method_name, None)
            if method is None:
                continue
            try:
                return str(method(cell) or "")
            except Exception:
                continue
        return ""

    def _coerce_sheet_value(self, value: str) -> float | int | str | bool:
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        try:
            parsed = float(value)
        except ValueError:
            return value
        return int(parsed) if parsed.is_integer() else parsed

    def _coerce_optional_number(self, value: str) -> float | None:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _set_expression_if_available(self, obj: Any, property_name: str, expression: str) -> None:
        if hasattr(obj, "setExpression"):
            try:
                obj.setExpression(property_name, expression)
                return
            except Exception:
                pass
        fallback_name = property_name.lower()
        fallback_values = {"length": 120, "width": 40, "height": 3}
        if hasattr(obj, property_name):
            setattr(obj, property_name, fallback_values.get(fallback_name, 1))

    def _project_path(self, project_name: str, path: str | Path | None) -> Path:
        if path is not None:
            return Path(path)
        return self.workspace / project_name / f"{project_name}.FCStd"

    def _mock_recompute(self, doc_id: str) -> RecomputeReport:
        return RecomputeReport(
            doc_id=doc_id,
            recompute_success=True,
            duration_ms=0,
            topology_changes=[],
            constraint_status="mocked",
            errors=[],
        )

    def _safe_doc_name(self, project_name: str) -> str:
        return "".join(char if char.isalnum() else "_" for char in project_name)
