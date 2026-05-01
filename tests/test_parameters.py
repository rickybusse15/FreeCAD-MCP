from __future__ import annotations

import pytest

from freecad_mcp.models import Parameter, ValidationError
from freecad_mcp.orchestration import FreeCADMCPService

pytestmark = pytest.mark.mock


def valid_parameter() -> dict:
    return {
        "name": "p_base_len_mm",
        "unit": "mm",
        "value": 120,
        "min": 20,
        "max": 400,
        "description": "Base length",
        "category": "geometry",
        "source": "template",
    }


def test_parameter_validation_accepts_good_payload() -> None:
    assert Parameter.from_mapping(valid_parameter()).validate() == []


def test_service_rejects_out_of_bounds_parameter() -> None:
    service = FreeCADMCPService()
    bad = valid_parameter() | {"value": 10}
    with pytest.raises(ValidationError):
        service.project_create("bad_project", [bad])


def test_param_validate_reports_errors_without_raising() -> None:
    service = FreeCADMCPService()
    result = service.param_validate([valid_parameter() | {"value": 10}])
    assert result["valid"] is False
    assert "below minimum" in result["errors"][0]


def test_param_validate_reports_missing_required_fields() -> None:
    service = FreeCADMCPService()
    result = service.param_validate([{"name": "p_base_len_mm"}])
    assert result["valid"] is False
    assert "missing required field" in result["errors"][0]
