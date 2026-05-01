from __future__ import annotations

from pathlib import Path

import pytest

from freecad_mcp.intelligence import RuleEngine
from freecad_mcp.models import Parameter

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.mock


def test_default_rules_flag_wall_thickness() -> None:
    engine = RuleEngine.from_yaml_dir(ROOT / "data" / "material_rules")
    results = engine.check_parameters(
        [
            Parameter(
                name="p_wall_thickness_mm",
                unit="mm",
                value=0.8,
                min=0.1,
                max=20,
                description="Wall thickness",
                category="geometry",
                source="template",
            )
        ]
    )
    assert results
    assert results[0].rule_id == "min_wall_thickness"
