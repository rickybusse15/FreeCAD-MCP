"""Helpers for loading and validating versioned contracts."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts"
PACKAGED_CONTRACT_MODULE = "freecad_mcp.resources.contracts"


def load_schema(name: str) -> dict[str, Any]:
    path = CONTRACT_DIR / name
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    resource = files(PACKAGED_CONTRACT_MODULE).joinpath(name)
    return json.loads(resource.read_text(encoding="utf-8"))


def validate_payload(schema_name: str, payload: dict[str, Any]) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema).validate(payload)
