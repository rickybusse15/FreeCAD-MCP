from __future__ import annotations

import json
from pathlib import Path

import pytest

from freecad_mcp.cli import main
from freecad_mcp.diagnostics import doctor_report, find_freecadcmd, smoke_test

pytestmark = pytest.mark.mock


def test_doctor_report_contains_freecad_and_workbench_status() -> None:
    report = doctor_report()
    assert "python_module_importable" in report["freecad"]
    assert report["workbench"]["init_gui_exists"] is True


def test_find_freecadcmd_returns_path_or_none() -> None:
    result = find_freecadcmd()
    assert result is None or result.exists()


def test_cli_catalog_prints_tool_catalog(capsys) -> None:
    assert main(["catalog"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "0.1.0"
    assert any(tool["name"] == "project.create" for tool in payload["tools"])


def test_smoke_test_runs_in_mock_mode_without_freecad(tmp_path: Path) -> None:
    report = smoke_test(tmp_path)
    assert report["ok"] is True
    assert report["parameter_count"] == 4
    assert (tmp_path / "exports" / "smoke_bracket.step").exists()
    assert (tmp_path / "logs" / "operations.jsonl").exists()
