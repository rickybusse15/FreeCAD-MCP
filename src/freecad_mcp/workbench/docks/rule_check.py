"""Rule check dock for Workbench mode."""

from __future__ import annotations

from typing import Any

from freecad_mcp.workbench.qt import load_qt_widgets


class RuleCheckDock:
    title = "MCP Rule Checks"

    headers = ["Severity", "Rule", "Entity", "Message", "Recommended Fix"]

    def __init__(self, parent: Any | None = None) -> None:
        self.results: list[dict[str, Any]] = []
        self.parent = parent
        self.widget = self._build_widget()

    def set_session(self, session: Any) -> None:
        self.session = session

    def refresh_from_session(self) -> list[dict[str, Any]]:
        session = getattr(self, "session", None)
        path = getattr(session, "document_path", None)
        if session is None or path is None:
            return self.refresh()
        parameters = session.service.param_list(path)["parameters"]
        return self.refresh(session.service.design_check_rules(parameters)["results"])

    def refresh(self, results: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        self.results = list(results or [])
        self._render()
        return self.results

    def _build_widget(self) -> Any:
        widgets, _core = load_qt_widgets()
        if widgets is None:
            return None
        dock = widgets.QDockWidget(self.title, self.parent)
        dock.setObjectName("MCPRuleCheckDock")
        table = widgets.QTableWidget(0, len(self.headers))
        table.setHorizontalHeaderLabels(self.headers)
        table.setAlternatingRowColors(True)
        table.cellDoubleClicked.connect(self._on_row_activated)
        dock.setWidget(table)
        self._table = table
        return dock

    def _render(self) -> None:
        table = getattr(self, "_table", None)
        if table is None:
            return
        widgets, _core = load_qt_widgets()
        if widgets is None:
            return
        table.setRowCount(len(self.results))
        for row, result in enumerate(self.results):
            values = [
                result.get("severity", ""),
                result.get("rule_id", ""),
                result.get("entity_ref", ""),
                result.get("message", ""),
                result.get("recommended_fix", ""),
            ]
            for col, value in enumerate(values):
                table.setItem(row, col, widgets.QTableWidgetItem(str(value)))

    def _on_row_activated(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self.results):
            return
        entity_ref = str(self.results[row].get("entity_ref", ""))
        if not entity_ref:
            return
        try:
            import FreeCADGui  # type: ignore[import-not-found]

            object_name = entity_ref.split(".", 1)[0].split("[", 1)[0]
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(object_name)
        except Exception:
            return
