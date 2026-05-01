"""Parameter editor dock for Workbench mode."""

from __future__ import annotations

from typing import Any

from freecad_mcp.orchestration import FreeCADMCPService
from freecad_mcp.workbench.qt import load_qt_widgets


class ParameterEditorDock:
    title = "MCP Parameters"

    headers = ["Name", "Unit", "Value", "Min", "Max", "Description", "Category", "Source"]

    def __init__(
        self,
        service: FreeCADMCPService | None = None,
        document_path: str | None = None,
        parent: Any | None = None,
    ) -> None:
        self.service = service
        self.document_path = document_path
        self.parameters: list[dict[str, Any]] = []
        self.parent = parent
        self._rendering = False
        self.widget = self._build_widget()

    def set_session(self, session: Any) -> None:
        self.service = session.service
        self.document_path = session.document_path

    def refresh_from_session(self) -> list[dict[str, Any]]:
        return self.refresh()

    def refresh(self, parameters: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if parameters is None and self.service is not None and self.document_path is not None:
            parameters = self.service.param_list(self.document_path)["parameters"]
        self.parameters = list(parameters or [])
        self._render()
        return self.parameters

    def apply_parameter(self, parameter: dict[str, Any]) -> dict[str, Any] | None:
        if self.service is None or self.document_path is None:
            self.refresh([*self.parameters, parameter])
            return None
        result = self.service.param_set(self.document_path, parameter)
        self.refresh()
        return result

    def _build_widget(self) -> Any:
        widgets, _core = load_qt_widgets()
        if widgets is None:
            return None
        dock = widgets.QDockWidget(self.title, self.parent)
        dock.setObjectName("MCPParameterEditorDock")
        table = widgets.QTableWidget(0, len(self.headers))
        table.setHorizontalHeaderLabels(self.headers)
        table.setAlternatingRowColors(True)
        table.itemChanged.connect(self._on_item_changed)
        dock.setWidget(table)
        self._table = table
        return dock

    def _render(self) -> None:
        table = getattr(self, "_table", None)
        if table is None:
            return
        self._rendering = True
        table.setRowCount(len(self.parameters))
        for row, parameter in enumerate(self.parameters):
            values = [
                parameter.get("name", ""),
                parameter.get("unit", ""),
                parameter.get("value", ""),
                parameter.get("min", ""),
                parameter.get("max", ""),
                parameter.get("description", ""),
                parameter.get("category", ""),
                parameter.get("source", ""),
            ]
            for col, value in enumerate(values):
                item = table.__class__.Item(str(value)) if hasattr(table.__class__, "Item") else None
                if item is None:
                    widgets, _core = load_qt_widgets()
                    item = widgets.QTableWidgetItem(str(value)) if widgets is not None else None
                if item is not None:
                    table.setItem(row, col, item)
        self._rendering = False

    def _on_item_changed(self, item: Any) -> None:
        if self._rendering or self.service is None or self.document_path is None:
            return
        row = item.row()
        if row < 0 or row >= len(self.parameters):
            return
        parameter = dict(self.parameters[row])
        for col, key in enumerate(["name", "unit", "value", "min", "max", "description", "category", "source"]):
            cell = self._table.item(row, col)
            if cell is None:
                continue
            parameter[key] = self._coerce_cell_value(key, cell.text())
        result = self.service.param_set(self.document_path, parameter)
        if result.get("ok") is False:
            self.refresh()
            return
        self.refresh()

    def _coerce_cell_value(self, key: str, value: str) -> Any:
        if key in {"value", "min", "max"}:
            if value == "":
                return None
            try:
                parsed = float(value)
            except ValueError:
                return value
            return int(parsed) if parsed.is_integer() else parsed
        return value
