from __future__ import annotations

import json
from pathlib import Path

import pytest

from freecad_mcp.adapter import FreeCADAdapter
from freecad_mcp.diagnostics import basic_bracket_parameters
from freecad_mcp.orchestration import FreeCADMCPService

pytestmark = pytest.mark.mock


def test_successful_transactions_write_operation_log(tmp_path: Path) -> None:
    adapter = FreeCADAdapter(workspace=tmp_path, prefer_real_freecad=False)
    service = FreeCADMCPService(adapter=adapter, workspace=tmp_path)
    result = service.project_create("logged_bracket", [parameter.to_dict() for parameter in basic_bracket_parameters()])
    service.part_create_from_template(result["path"], "basic_bracket")

    log_path = tmp_path / "logs" / "operations.jsonl"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert [entry["tool_name"] for entry in entries] == ["project.create", "part.create_from_template"]
    assert (tmp_path / "artifacts" / "logged_bracket_recompute_report.json").exists()
