"""Small FreeCAD GUI helpers used by Workbench commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from freecad_mcp.adapter import FreeCADAdapter
from freecad_mcp.orchestration import FreeCADMCPService


def active_document_path() -> str | None:
    try:
        import FreeCAD  # type: ignore[import-not-found]
    except ImportError:
        return None
    doc = getattr(FreeCAD, "ActiveDocument", None)
    if doc is None:
        return None
    filename = getattr(doc, "FileName", "") or ""
    return str(filename) if filename else None


def show_error(message: str) -> None:
    _console_print("PrintError", f"{message}\n")


def show_info(message: str) -> None:
    _console_print("PrintMessage", f"{message}\n")


def workbench_workspace() -> Path:
    try:
        import FreeCAD  # type: ignore[import-not-found]

        root = Path(FreeCAD.getUserAppDataDir())
    except ImportError:
        root = Path.home() / ".freecad-mcp"
    return root / "MCPDesignWorkbench" / "workspace"


def workbench_service() -> FreeCADMCPService:
    workspace = workbench_workspace()
    return FreeCADMCPService(
        adapter=FreeCADAdapter(workspace=workspace, prefer_real_freecad=True, require_real_freecad=True),
        workspace=workspace,
    )


def active_selection_refs() -> list[dict[str, str]]:
    try:
        import FreeCADGui  # type: ignore[import-not-found]
    except ImportError:
        return []
    refs: list[dict[str, str]] = []
    for selection in FreeCADGui.Selection.getSelectionEx():
        obj = getattr(selection, "Object", None)
        for sub_name in getattr(selection, "SubElementNames", []) or [""]:
            refs.append(
                {
                    "document": getattr(getattr(obj, "Document", None), "Name", ""),
                    "object": getattr(obj, "Name", ""),
                    "label": getattr(obj, "Label", ""),
                    "subelement": str(sub_name),
                    "ref": f"{getattr(obj, 'Name', '')}.{sub_name}" if sub_name else getattr(obj, "Name", ""),
                }
            )
    return refs


def _console_print(method_name: str, message: str) -> None:
    try:
        import FreeCAD  # type: ignore[import-not-found]

        console: Any = getattr(FreeCAD, "Console", None)
        method = getattr(console, method_name, None)
        if method is not None:
            method(message)
            return
    except ImportError:
        pass
    print(message, end="")
