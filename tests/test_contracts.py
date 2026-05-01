from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.mock


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contracts_are_valid_json_schema() -> None:
    for path in sorted((ROOT / "contracts").glob("*.schema.json")):
        Draft202012Validator.check_schema(load_json(path))


def test_manifest_matches_schema() -> None:
    schema = load_json(ROOT / "contracts" / "manifest.schema.json")
    payload = load_json(ROOT / "artifacts" / "manifest.json")
    Draft202012Validator(schema).validate(payload)


def test_tool_catalog_matches_schema() -> None:
    from freecad_mcp.mcp_tools import ToolRegistry

    schema = load_json(ROOT / "contracts" / "mcp_tools.schema.json")
    Draft202012Validator(schema).validate(ToolRegistry().as_catalog())


def test_contract_helper_loads_repo_local_schema() -> None:
    from freecad_mcp.contracts import load_schema

    assert load_schema("param.schema.json")["title"] == "FreeCAD MCP Parameter"


def test_contract_helper_falls_back_to_package_resources(tmp_path, monkeypatch) -> None:
    import freecad_mcp.contracts as contracts

    monkeypatch.setattr(contracts, "CONTRACT_DIR", tmp_path)
    assert contracts.load_schema("param.schema.json")["title"] == "FreeCAD MCP Parameter"


def test_create_project_example_parameter_matches_schema() -> None:
    schema = load_json(ROOT / "contracts" / "param.schema.json")
    payload = load_json(ROOT / "contracts" / "api_examples" / "create_project.json")
    Draft202012Validator(schema).validate(payload["parameters"][0])
