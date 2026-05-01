"""FreeCAD GUI registration for MCPDesignWorkbench."""

from __future__ import annotations

import sys
import os
from pathlib import Path

module_file = globals().get("__file__")
candidate_paths = []
if module_file:
    candidate_paths.append(Path(module_file).resolve().parents[2])
try:
    import FreeCAD  # type: ignore[import-not-found]

    candidate_paths.append(Path(FreeCAD.getUserAppDataDir()) / "Mod" / "MCPDesignWorkbench")
except Exception:
    pass

for candidate in candidate_paths:
    resolved = candidate.resolve()
    for src_path in (resolved, *resolved.parents):
        if (src_path / "freecad_mcp" / "__init__.py").exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
            break

try:
    BaseWorkbench = Workbench  # type: ignore[name-defined]
except NameError:
    BaseWorkbench = object


class MCPDesignWorkbench(BaseWorkbench):  # pragma: no cover - exercised inside FreeCAD
    MenuText = "MCP Design"
    ToolTip = "Parametric FreeCAD design through MCP"
    Icon = ""

    def Initialize(self) -> None:
        import FreeCADGui  # type: ignore[import-not-found]

        from freecad_mcp.workbench.commands import register_commands

        commands = register_commands()
        self.appendToolbar("MCP Design", commands)
        self.appendMenu("MCP Design", commands)

    def Activated(self) -> None:
        if os.environ.get("FREECAD_MCP_DISABLE_DOCKS") == "1":
            return None

        import FreeCADGui  # type: ignore[import-not-found]

        from freecad_mcp.workbench.qt import load_qt_widgets

        widgets, core = load_qt_widgets()
        if widgets is None or core is None:
            return None
        if hasattr(self, "_docks"):
            return None
        main_window = FreeCADGui.getMainWindow()

        def create_docks() -> None:
            if hasattr(self, "_docks"):
                return None
            from freecad_mcp.workbench.docks import AssemblyDock, DesignAssistantDock, ParameterEditorDock, RuleCheckDock
            from freecad_mcp.workbench.session import WorkbenchSession

            self._session = WorkbenchSession()
            service = self._session.service
            document_path = self._session.document_path
            self._docks = [
                ParameterEditorDock(service=service, document_path=document_path, parent=main_window),
                RuleCheckDock(parent=main_window),
                DesignAssistantDock(parent=main_window),
                AssemblyDock(service=service, document_path=document_path, parent=main_window),
            ]
            self._session.bind_docks(self._docks)
            for dock in self._docks:
                if dock.widget is not None:
                    main_window.addDockWidget(core.Qt.RightDockWidgetArea, dock.widget)
                    dock.widget.setAttribute(core.Qt.WA_DeleteOnClose, False)
            return None

        core.QTimer.singleShot(0, create_docks)
        return None

    def Deactivated(self) -> None:
        return None

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"


try:  # pragma: no cover - exercised inside FreeCAD
    import FreeCADGui  # type: ignore[import-not-found]

    FreeCADGui.addWorkbench(MCPDesignWorkbench())
except (ImportError, AttributeError):
    pass
