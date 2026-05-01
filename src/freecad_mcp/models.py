"""Shared value objects for FreeCAD-MCP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

ParameterUnit = Literal["mm", "deg", "count", "string", "bool"]
ParameterSource = Literal["template", "user", "rule_engine"]
Severity = Literal["info", "warn", "error"]
JointType = Literal[
    "fixed",
    "revolute",
    "cylindrical",
    "slider",
    "ball",
    "distance",
    "parallel",
    "perpendicular",
    "angle",
    "rack_pinion",
    "screw",
    "gear_belt",
    "coincident",
    "concentric",
]
MateType = JointType

JOINT_TYPES: tuple[str, ...] = (
    "fixed",
    "revolute",
    "cylindrical",
    "slider",
    "ball",
    "distance",
    "parallel",
    "perpendicular",
    "angle",
    "rack_pinion",
    "screw",
    "gear_belt",
    "coincident",
    "concentric",
)


class ValidationError(ValueError):
    """Raised when an MCP payload does not meet local validation rules."""


@dataclass(frozen=True)
class Parameter:
    name: str
    unit: ParameterUnit
    value: float | int | str | bool
    min: float | None = None
    max: float | None = None
    description: str = ""
    category: str = "general"
    source: ParameterSource = "user"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name.startswith(("g_", "p_", "m_")):
            errors.append(f"{self.name}: name must start with g_, p_, or m_")
        if not self.description:
            errors.append(f"{self.name}: description is required")
        if self.unit in {"mm", "deg", "count"} and not isinstance(self.value, (int, float)):
            errors.append(f"{self.name}: numeric value required for {self.unit}")
        if self.unit == "count" and isinstance(self.value, (int, float)) and int(self.value) != self.value:
            errors.append(f"{self.name}: count value must be an integer")
        if self.unit == "bool" and not isinstance(self.value, bool):
            errors.append(f"{self.name}: boolean value required")
        if self.unit == "string" and not isinstance(self.value, str):
            errors.append(f"{self.name}: string value required")
        if isinstance(self.value, (int, float)):
            if self.min is not None and self.value < self.min:
                errors.append(f"{self.name}: value {self.value} is below minimum {self.min}")
            if self.max is not None and self.value > self.max:
                errors.append(f"{self.name}: value {self.value} is above maximum {self.max}")
            if self.min is not None and self.max is not None and self.min > self.max:
                errors.append(f"{self.name}: minimum cannot exceed maximum")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Parameter":
        return cls(
            name=str(data["name"]),
            unit=data["unit"],
            value=data["value"],
            min=data.get("min"),
            max=data.get("max"),
            description=str(data.get("description", "")),
            category=str(data.get("category", "general")),
            source=data.get("source", "user"),
        )


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    severity: Severity
    entity_ref: str
    message: str
    recommended_fix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.recommended_fix is None:
            data.pop("recommended_fix")
        return data


@dataclass(frozen=True)
class RecomputeReport:
    doc_id: str
    recompute_success: bool
    duration_ms: int
    topology_changes: list[str]
    constraint_status: str
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssemblyPart:
    part_id: str
    name: str
    path: str | None = None
    quantity: int = 1
    interface_ref: str = ""
    material: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.part_id:
            errors.append("part_id is required")
        if not self.name:
            errors.append(f"{self.part_id or 'part'}: name is required")
        if self.quantity < 1:
            errors.append(f"{self.part_id}: quantity must be at least 1")
        return errors

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.path is None:
            data.pop("path")
        return data

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AssemblyPart":
        return cls(
            part_id=str(data["part_id"]),
            name=str(data["name"]),
            path=data.get("path"),
            quantity=int(data.get("quantity", 1)),
            interface_ref=str(data.get("interface_ref", "")),
            material=str(data.get("material", "")),
        )


@dataclass(frozen=True)
class AssemblyMate:
    mate_id: str
    parent_part_id: str
    child_part_id: str
    mate_type: MateType
    parent_ref: str
    child_ref: str
    offset: float = 0
    unit: ParameterUnit = "mm"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.mate_id:
            errors.append("mate_id is required")
        if not self.parent_part_id:
            errors.append(f"{self.mate_id or 'mate'}: parent_part_id is required")
        if not self.child_part_id:
            errors.append(f"{self.mate_id or 'mate'}: child_part_id is required")
        if self.parent_part_id and self.parent_part_id == self.child_part_id:
            errors.append(f"{self.mate_id}: parent_part_id and child_part_id must differ")
        if self.mate_type not in JOINT_TYPES:
            errors.append(f"{self.mate_id}: unsupported mate_type {self.mate_type}")
        if not self.parent_ref:
            errors.append(f"{self.mate_id}: parent_ref is required")
        if not self.child_ref:
            errors.append(f"{self.mate_id}: child_ref is required")
        if self.unit not in {"mm", "deg"}:
            errors.append(f"{self.mate_id}: unit must be mm or deg")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AssemblyMate":
        return cls(
            mate_id=str(data["mate_id"]),
            parent_part_id=str(data["parent_part_id"]),
            child_part_id=str(data["child_part_id"]),
            mate_type=data["mate_type"],
            parent_ref=str(data["parent_ref"]),
            child_ref=str(data["child_ref"]),
            offset=float(data.get("offset", 0)),
            unit=data.get("unit", "mm"),
        )


@dataclass(frozen=True)
class AssemblyJoint:
    joint_id: str
    parent_part_id: str
    child_part_id: str
    joint_type: JointType
    parent_ref: str
    child_ref: str
    offset: float = 0
    unit: ParameterUnit = "mm"

    def validate(self) -> list[str]:
        mate = AssemblyMate(
            mate_id=self.joint_id,
            parent_part_id=self.parent_part_id,
            child_part_id=self.child_part_id,
            mate_type=self.joint_type,
            parent_ref=self.parent_ref,
            child_ref=self.child_ref,
            offset=self.offset,
            unit=self.unit,
        )
        errors = mate.validate()
        return [error.replace("mate_type", "joint_type") for error in errors]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AssemblyJoint":
        return cls(
            joint_id=str(data.get("joint_id", data.get("mate_id", ""))),
            parent_part_id=str(data["parent_part_id"]),
            child_part_id=str(data["child_part_id"]),
            joint_type=data.get("joint_type", data.get("mate_type", "fixed")),
            parent_ref=str(data["parent_ref"]),
            child_ref=str(data["child_ref"]),
            offset=float(data.get("offset", 0)),
            unit=data.get("unit", "mm"),
        )
