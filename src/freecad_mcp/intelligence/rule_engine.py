"""Minimal manufacturability rule engine for MVP checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from freecad_mcp.models import Parameter, RuleResult


@dataclass(frozen=True)
class NumericThresholdRule:
    rule_id: str
    parameter: str
    min_value: float | None
    max_value: float | None
    severity: str
    message: str
    recommended_fix: str | None = None


class RuleFile(Protocol):
    name: str

    def read_text(self, encoding: str = "utf-8") -> str: ...


class RuleDirectory(Protocol):
    def iterdir(self) -> Any: ...


class RuleEngine:
    def __init__(self, rules: list[NumericThresholdRule] | None = None) -> None:
        self.rules = rules or []

    @classmethod
    def from_yaml_dir(cls, path: str | Path | RuleDirectory) -> "RuleEngine":
        rules: list[NumericThresholdRule] = []
        rule_dir = Path(path) if isinstance(path, (str, Path)) else path
        if isinstance(rule_dir, Path) and not rule_dir.exists():
            return cls([])
        rule_files = [item for item in rule_dir.iterdir() if getattr(item, "name", "").endswith(".yaml")]
        for rule_file in sorted(rule_files, key=lambda item: item.name):
            data = yaml.safe_load(rule_file.read_text(encoding="utf-8")) or {}
            for item in data.get("numeric_thresholds", []):
                rules.append(
                    NumericThresholdRule(
                        rule_id=str(item["rule_id"]),
                        parameter=str(item["parameter"]),
                        min_value=item.get("min"),
                        max_value=item.get("max"),
                        severity=str(item.get("severity", "warn")),
                        message=str(item["message"]),
                        recommended_fix=item.get("recommended_fix"),
                    )
                )
        return cls(rules)

    def check_parameters(self, parameters: list[Parameter]) -> list[RuleResult]:
        by_name = {parameter.name: parameter for parameter in parameters}
        results: list[RuleResult] = []
        for rule in self.rules:
            parameter = by_name.get(rule.parameter)
            if parameter is None or not isinstance(parameter.value, (int, float)):
                continue
            if rule.min_value is not None and parameter.value < rule.min_value:
                results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        severity=rule.severity,  # type: ignore[arg-type]
                        entity_ref=f"Spreadsheet.{parameter.name}",
                        message=rule.message,
                        recommended_fix=rule.recommended_fix,
                    )
                )
            if rule.max_value is not None and parameter.value > rule.max_value:
                results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        severity=rule.severity,  # type: ignore[arg-type]
                        entity_ref=f"Spreadsheet.{parameter.name}",
                        message=rule.message,
                        recommended_fix=rule.recommended_fix,
                    )
                )
        for parameter in parameters:
            for error in parameter.validate():
                results.append(
                    RuleResult(
                        rule_id="parameter.validation",
                        severity="error",
                        entity_ref=f"Spreadsheet.{parameter.name}",
                        message=error,
                    )
                )
        return results

    def check_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        parameters = [Parameter.from_mapping(item) for item in payload.get("parameters", [])]
        return [result.to_dict() for result in self.check_parameters(parameters)]
