"""Document-bound Workbench session state."""

from __future__ import annotations

from typing import Any

from freecad_mcp.orchestration import FreeCADMCPService
from freecad_mcp.workbench.context import active_document_path, show_error, show_info, workbench_service


class WorkbenchSession:  # pragma: no cover - exercised inside FreeCAD GUI
    def __init__(self, service: FreeCADMCPService | None = None) -> None:
        self.service = service or workbench_service()
        self.document_path: str | None = active_document_path()
        self.docks: list[Any] = []
        self.history: list[str] = []

    def bind_docks(self, docks: list[Any]) -> None:
        self.docks = docks
        for dock in self.docks:
            if hasattr(dock, "set_session"):
                dock.set_session(self)
            elif hasattr(dock, "service"):
                dock.service = self.service
                dock.document_path = self.document_path
        self.refresh()

    def refresh_document(self) -> str | None:
        current = active_document_path()
        if current != self.document_path:
            self.document_path = current
            for dock in self.docks:
                if hasattr(dock, "document_path"):
                    dock.document_path = current
            self.append_history(f"Active document: {current or 'unsaved document'}")
        return self.document_path

    def refresh(self) -> None:
        path = self.refresh_document()
        for dock in self.docks:
            try:
                if hasattr(dock, "refresh_from_session"):
                    dock.refresh_from_session()
                elif hasattr(dock, "refresh") and path is not None:
                    dock.refresh()
            except Exception as exc:
                self.append_history(f"{dock.__class__.__name__} refresh failed: {type(exc).__name__}: {exc}")

    def require_document_path(self) -> str | None:
        path = self.refresh_document()
        if path is None:
            show_error("Save or open a FreeCAD document before running MCP actions.")
        return path

    def append_history(self, message: str) -> None:
        self.history.append(message)
        for dock in self.docks:
            if dock.__class__.__name__ == "DesignAssistantDock" and hasattr(dock, "refresh"):
                dock.refresh(self.history)
        show_info(message)

    def run(self, label: str, callback: Any) -> dict[str, Any] | None:
        try:
            result = callback()
        except Exception as exc:
            message = f"{label} failed: {type(exc).__name__}: {exc}"
            self.append_history(message)
            show_error(message)
            return None
        status = "ok" if result is None or result.get("ok", True) is not False else "failed"
        self.append_history(f"{label}: {status}")
        self.refresh()
        return result
