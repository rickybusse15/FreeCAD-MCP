"""Dock widgets for the FreeCAD Workbench MVP."""

from __future__ import annotations

from .assembly import AssemblyDock
from .design_assistant import DesignAssistantDock
from .parameter_editor import ParameterEditorDock
from .rule_check import RuleCheckDock

__all__ = ["AssemblyDock", "DesignAssistantDock", "ParameterEditorDock", "RuleCheckDock"]
