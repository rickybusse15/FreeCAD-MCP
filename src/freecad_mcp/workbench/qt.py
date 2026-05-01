"""Qt loading helpers for FreeCAD, PySide6, and non-GUI tests."""

from __future__ import annotations

from typing import Any


def load_qt_widgets() -> tuple[Any, Any] | tuple[None, None]:
    for binding in ("PySide6", "PySide2"):
        try:
            widgets = __import__(f"{binding}.QtWidgets", fromlist=["QtWidgets"])
            core = __import__(f"{binding}.QtCore", fromlist=["QtCore"])
            app = widgets.QApplication.instance()
            if app is None:
                return None, None
            return widgets, core
        except ImportError:
            continue
    return None, None
