"""Assembly dock for Workbench mode."""

from __future__ import annotations

from typing import Any

from freecad_mcp.orchestration import FreeCADMCPService
from freecad_mcp.workbench.qt import load_qt_widgets


class AssemblyDock:
    title = "MCP Assembly"

    part_headers = ["Part ID", "Name", "Qty", "Material", "Interface", "Path"]
    mate_headers = ["Joint ID", "Type", "Parent", "Child", "Parent Ref", "Child Ref", "Offset"]
    bom_headers = ["Part ID", "Name", "Qty", "Material", "Source"]

    def __init__(
        self,
        service: FreeCADMCPService | None = None,
        document_path: str | None = None,
        parent: Any | None = None,
    ) -> None:
        self.service = service
        self.document_path = document_path
        self.parent = parent
        self.state: dict[str, Any] = self._empty_state()
        self.widget = self._build_widget()

    def set_session(self, session: Any) -> None:
        self.service = session.service
        self.document_path = session.document_path

    def refresh_from_session(self) -> dict[str, Any]:
        self.refresh_bom()
        return self.state

    def refresh(self, assembly: dict[str, Any] | None = None) -> dict[str, Any]:
        if assembly is not None:
            self.state = self._normalize_state(assembly)
        self._render()
        return self.state

    def create_assembly(self, assembly_name: str = "MCP Assembly") -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            self.state = self._empty_state(assembly_name)
            self._render()
            return None
        result = self.service.assembly_create(self.document_path, assembly_name)
        self.refresh(result.get("assembly"))
        return result

    def add_part(self, part: dict[str, Any]) -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            parts = [item for item in self.state["parts"] if item.get("part_id") != part.get("part_id")]
            parts.append(part)
            self.state["parts"] = sorted(parts, key=lambda item: item.get("part_id", ""))
            self.state["bom"] = self._build_bom(self.state["parts"])
            self._render()
            return None
        result = self.service.assembly_insert_link(self.document_path, part)
        self.refresh(result.get("assembly"))
        return result

    def add_mate(self, mate: dict[str, Any]) -> dict[str, Any] | None:
        return self.add_joint(
            {
                "joint_id": mate.get("mate_id", "joint"),
                "parent_part_id": mate.get("parent_part_id", ""),
                "child_part_id": mate.get("child_part_id", ""),
                "joint_type": mate.get("mate_type", "fixed"),
                "parent_ref": mate.get("parent_ref", ""),
                "child_ref": mate.get("child_ref", ""),
                "offset": mate.get("offset", 0),
                "unit": mate.get("unit", "mm"),
            }
        )

    def add_joint(self, joint: dict[str, Any]) -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            joints = [item for item in self.state["joints"] if item.get("joint_id") != joint.get("joint_id")]
            joints.append(joint)
            self.state["joints"] = sorted(joints, key=lambda item: item.get("joint_id", ""))
            self.state["mates"] = [
                {
                    "mate_id": item.get("joint_id", ""),
                    "mate_type": item.get("joint_type", ""),
                    "parent_part_id": item.get("parent_part_id", ""),
                    "child_part_id": item.get("child_part_id", ""),
                    "parent_ref": item.get("parent_ref", ""),
                    "child_ref": item.get("child_ref", ""),
                    "offset": item.get("offset", 0),
                    "unit": item.get("unit", "mm"),
                }
                for item in self.state["joints"]
            ]
            self._render()
            return None
        result = self.service.assembly_joint_create(self.document_path, joint)
        self.refresh(result.get("assembly"))
        return result

    def ground_part(self, part_id: str) -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            self.state.setdefault("grounded", [])
            if part_id not in self.state["grounded"]:
                self.state["grounded"].append(part_id)
            self._render()
            return None
        result = self.service.assembly_ground(self.document_path, part_id)
        self.refresh(result.get("assembly"))
        return result

    def solve(self) -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            self.state["solve_status"] = {"solved": True, "duration_ms": 0, "errors": []}
            self._render()
            return None
        result = self.service.assembly_solve(self.document_path)
        self.refresh(result.get("assembly"))
        return result

    def refresh_bom(self) -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            self.state["bom"] = self._build_bom(self.state["parts"])
            self._render()
            return None
        result = self.service.assembly_bom(self.document_path)
        self.state["bom"] = list(result.get("bom", []))
        self._render()
        return result

    def explode_view(self, distance_mm: float = 25) -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            self.state["exploded_view"] = self._build_exploded_view(distance_mm)
            self._render()
            return None
        result = self.service.assembly_explode_view(self.document_path, distance_mm)
        self.state["exploded_view"] = result.get("exploded_view", self.state["exploded_view"])
        self._render()
        return result

    def _build_widget(self) -> Any:
        widgets, _core = load_qt_widgets()
        if widgets is None:
            return None
        dock = widgets.QDockWidget(self.title, self.parent)
        dock.setObjectName("MCPAssemblyDock")
        root = widgets.QWidget()
        layout = widgets.QVBoxLayout(root)

        self._summary = widgets.QLabel()
        layout.addWidget(self._summary)

        actions = widgets.QHBoxLayout()
        self._create_button = widgets.QPushButton("Create")
        self._insert_button = widgets.QPushButton("Insert Link")
        self._ground_button = widgets.QPushButton("Ground")
        self._joint_button = widgets.QPushButton("Joint")
        self._solve_button = widgets.QPushButton("Solve")
        self._bom_button = widgets.QPushButton("BOM")
        self._explode_button = widgets.QPushButton("Explode")
        actions.addWidget(self._create_button)
        actions.addWidget(self._insert_button)
        actions.addWidget(self._ground_button)
        actions.addWidget(self._joint_button)
        actions.addWidget(self._solve_button)
        actions.addWidget(self._bom_button)
        actions.addWidget(self._explode_button)
        layout.addLayout(actions)

        tabs = widgets.QTabWidget()
        self._parts_table = self._make_table(widgets, self.part_headers)
        self._mates_table = self._make_table(widgets, self.mate_headers)
        self._bom_table = self._make_table(widgets, self.bom_headers)
        tabs.addTab(self._parts_table, "Parts")
        tabs.addTab(self._mates_table, "Mates")
        tabs.addTab(self._bom_table, "BOM")
        layout.addWidget(tabs)

        self._connect_buttons()
        dock.setWidget(root)
        return dock

    def _connect_buttons(self) -> None:
        if hasattr(self, "_create_button"):
            self._create_button.clicked.connect(lambda: self.create_assembly())
            self._insert_button.clicked.connect(self._insert_part_from_prompt)
            self._ground_button.clicked.connect(self._ground_from_prompt)
            self._joint_button.clicked.connect(self._joint_from_prompt)
            self._solve_button.clicked.connect(self.solve)
            self._bom_button.clicked.connect(self.refresh_bom)
            self._explode_button.clicked.connect(lambda: self.explode_view())

    def _make_table(self, widgets: Any, headers: list[str]) -> Any:
        table = widgets.QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        return table

    def _render(self) -> None:
        summary = getattr(self, "_summary", None)
        if summary is not None:
            exploded = self.state.get("exploded_view", {})
            suffix = "exploded" if exploded.get("enabled") else "assembled"
            solved = self.state.get("solve_status", {}).get("solved")
            solve_text = "unsolved" if solved is False else "solved" if solved is True else "not solved"
            summary.setText(
                f"{self.state['name']} | {len(self.state['parts'])} parts | "
                f"{len(self.state.get('joints', self.state['mates']))} joints | {suffix} | {solve_text}"
            )
        self._render_table(getattr(self, "_parts_table", None), self.part_headers, self._part_rows())
        self._render_table(getattr(self, "_mates_table", None), self.mate_headers, self._mate_rows())
        self._render_table(getattr(self, "_bom_table", None), self.bom_headers, self._bom_rows())

    def _render_table(self, table: Any, headers: list[str], rows: list[list[Any]]) -> None:
        if table is None:
            return
        widgets, _core = load_qt_widgets()
        if widgets is None:
            return
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row[: len(headers)]):
                table.setItem(row_index, col_index, widgets.QTableWidgetItem(str(value)))

    def _part_rows(self) -> list[list[Any]]:
        return [
            [
                part.get("part_id", ""),
                part.get("name", ""),
                part.get("quantity", 1),
                part.get("material", ""),
                part.get("interface_ref", ""),
                part.get("path", ""),
            ]
            for part in self.state["parts"]
        ]

    def _mate_rows(self) -> list[list[Any]]:
        rows = self.state.get("joints") or [
            {
                "joint_id": mate.get("mate_id", ""),
                "joint_type": mate.get("mate_type", ""),
                "parent_part_id": mate.get("parent_part_id", ""),
                "child_part_id": mate.get("child_part_id", ""),
                "parent_ref": mate.get("parent_ref", ""),
                "child_ref": mate.get("child_ref", ""),
                "offset": mate.get("offset", 0),
                "unit": mate.get("unit", "mm"),
            }
            for mate in self.state["mates"]
        ]
        return [
            [
                joint.get("joint_id", ""),
                joint.get("joint_type", ""),
                joint.get("parent_part_id", ""),
                joint.get("child_part_id", ""),
                joint.get("parent_ref", ""),
                joint.get("child_ref", ""),
                f"{joint.get('offset', 0)} {joint.get('unit', 'mm')}",
            ]
            for joint in rows
        ]

    def _bom_rows(self) -> list[list[Any]]:
        return [
            [
                item.get("part_id", ""),
                item.get("name", ""),
                item.get("quantity", 0),
                item.get("material", ""),
                item.get("source_path", ""),
            ]
            for item in self.state["bom"]
        ]

    def _normalize_state(self, assembly: dict[str, Any]) -> dict[str, Any]:
        state = self._empty_state(str(assembly.get("name", "MCP Assembly")))
        state["parts"] = list(assembly.get("parts", []))
        state["mates"] = list(assembly.get("mates", []))
        state["joints"] = list(assembly.get("joints", []))
        state["grounded"] = list(assembly.get("grounded", []))
        state["bom"] = list(assembly.get("bom", self._build_bom(state["parts"])))
        state["exploded_view"] = dict(assembly.get("exploded_view", state["exploded_view"]))
        state["solve_status"] = dict(assembly.get("solve_status", state["solve_status"]))
        return state

    def _empty_state(self, name: str = "MCP Assembly") -> dict[str, Any]:
        return {
            "name": name,
            "parts": [],
            "mates": [],
            "joints": [],
            "grounded": [],
            "bom": [],
            "exploded_view": {"enabled": False, "distance_mm": 0, "vectors": []},
            "solve_status": {"solved": None, "duration_ms": 0, "errors": []},
        }

    def _build_bom(self, parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, Any]] = {}
        for part in parts:
            part_id = str(part.get("part_id", ""))
            if part_id not in totals:
                totals[part_id] = {
                    "part_id": part_id,
                    "name": part.get("name", ""),
                    "material": part.get("material", ""),
                    "quantity": 0,
                    "source_path": part.get("path"),
                }
            totals[part_id]["quantity"] += int(part.get("quantity", 1))
        return sorted(totals.values(), key=lambda item: item["part_id"])

    def _build_exploded_view(self, distance_mm: float) -> dict[str, Any]:
        return {
            "enabled": True,
            "distance_mm": float(distance_mm),
            "vectors": [
                {"part_id": part.get("part_id", ""), "x_mm": float(distance_mm) * index, "y_mm": 0, "z_mm": 0}
                for index, part in enumerate(self.state["parts"], start=1)
            ],
        }

    def _insert_part_from_prompt(self) -> None:
        part_id = self._prompt("Insert Link", "Part ID", f"part_{len(self.state['parts']) + 1}")
        if not part_id:
            return
        name = self._prompt("Insert Link", "Display name", part_id) or part_id
        self.add_part({"part_id": part_id, "name": name, "quantity": 1})

    def _ground_from_prompt(self) -> None:
        part_id = self._prompt("Ground Part", "Part ID", self.state["parts"][0]["part_id"] if self.state["parts"] else "part_1")
        if part_id:
            self.ground_part(part_id)

    def _joint_from_prompt(self) -> None:
        joint_id = self._prompt("Create Joint", "Joint ID", f"joint_{len(self.state.get('joints', [])) + 1}")
        if not joint_id:
            return
        parent = self._prompt("Create Joint", "Parent part ID", self.state["parts"][0]["part_id"] if self.state["parts"] else "part_1")
        child = self._prompt("Create Joint", "Child part ID", self.state["parts"][1]["part_id"] if len(self.state["parts"]) > 1 else "part_2")
        joint_type = self._prompt("Create Joint", "Joint type", "fixed") or "fixed"
        self.add_joint(
            {
                "joint_id": joint_id,
                "parent_part_id": parent or "",
                "child_part_id": child or "",
                "joint_type": joint_type,
                "parent_ref": f"{parent}.Face1" if parent else "Face1",
                "child_ref": f"{child}.Face1" if child else "Face1",
                "offset": 0,
                "unit": "mm",
            }
        )

    def _prompt(self, title: str, label: str, default: str) -> str | None:
        widgets, _core = load_qt_widgets()
        if widgets is None:
            return default
        value, ok = widgets.QInputDialog.getText(None, title, label, text=default)
        return str(value) if ok else None
