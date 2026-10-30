# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Serializable action criteria, feedback requirements, and skill associations."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from aspire.sim.cap.knowledge.serialization import content_hash


def identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", value):
        raise ValueError(f"invalid identifier: {value!r}")


def text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


def validate_expression(expr: dict[str, Any], *, depth: int = 0) -> set[str]:
    """Validate the data-only grammar and return all referenced fact paths."""
    if depth > 32 or not isinstance(expr, dict) or not expr:
        raise ValueError("predicate expression must be nonempty and at most 32 levels deep")
    logical = set(expr) & {"all", "any", "not"}
    if logical:
        if len(logical) != 1 or len(expr) != 1:
            raise ValueError("a logical predicate must have exactly one operator")
        op = next(iter(logical))
        children = [expr[op]] if op == "not" else expr[op]
        if not isinstance(children, list) or not children:
            raise ValueError("logical predicates require nonempty operands")
        return set().union(*(validate_expression(x, depth=depth + 1) for x in children))
    if set(expr) - {"fact", "op", "value"} or not isinstance(expr.get("fact"), str):
        raise ValueError("atomic predicate requires a fact path")
    identifier(expr["fact"])
    op = expr.get("op", "eq")
    if op not in {"eq", "ne", "exists", "in", "contains", "gt", "gte", "lt", "lte", "regex"}:
        raise ValueError(f"unsupported predicate operator: {op}")
    if op != "exists" and "value" not in expr:
        raise ValueError("atomic predicate requires a comparison value")
    if op in {"gt", "gte", "lt", "lte"}:
        value = expr["value"]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError("ordered comparison requires a finite numeric threshold")
    if op == "in" and not isinstance(expr["value"], (list, str, dict)):
        raise ValueError("in requires a container")
    if op == "exists" and "value" in expr and not isinstance(expr["value"], bool):
        raise ValueError("exists requires a boolean value")
    if op == "regex":
        if not isinstance(expr["value"], str) or len(expr["value"]) > 256:
            raise ValueError("regex requires a pattern of at most 256 characters")
        re.compile(expr["value"])
    return {expr["fact"]}


@dataclass(frozen=True)
class EvidenceRequirement:
    fact: str
    modality: str
    max_age_s: float = 2.0

    def __post_init__(self):
        identifier(self.fact)
        identifier(self.modality)
        if not math.isfinite(self.max_age_s) or self.max_age_s <= 0:
            raise ValueError("evidence maximum age must be finite and positive")


@dataclass(frozen=True)
class Observation:
    value: Any
    modality: str
    source: str
    observed_at: float


@dataclass(frozen=True)
class EvidenceFrame:
    observations: dict[str, Observation]
    captured_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EvidenceFrame:
        return cls(
            {key: Observation(**item) for key, item in value["observations"].items()},
            value["captured_at"],
        )


@dataclass(frozen=True)
class PredicateDefinition:
    id: str
    semantic_key: str
    description: str
    expression: dict[str, Any]
    requirements: tuple[EvidenceRequirement, ...]

    def __post_init__(self):
        identifier(self.id)
        text(self.semantic_key, "semantic_key")
        text(self.description, "description")
        facts = validate_expression(self.expression)
        paths = [r.fact for r in self.requirements]
        if len(set(paths)) != len(paths) or set(paths) != facts:
            raise ValueError("requirements must cover each referenced fact exactly once")

    @property
    def semantic_hash(self) -> str:
        return content_hash({
            "semantic_key": self.semantic_key,
            "expression": self.expression,
            "requirements": sorted((asdict(x) for x in self.requirements), key=lambda x: x["fact"]),
        })

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PredicateDefinition:
        return cls(**{**value, "requirements": tuple(EvidenceRequirement(**x) for x in value["requirements"])})


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    title: str
    implementation: str
    failure_signature: str
    intent: str
    repair: str
    parent_id: str | None = None
    applicability: dict[str, Any] = field(default_factory=dict)
    feedback_requirements: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.id)
        if self.parent_id is not None:
            identifier(self.parent_id)
        for name in ("title", "implementation", "failure_signature", "intent", "repair"):
            text(getattr(self, name), name)
        if self.applicability:
            validate_expression(self.applicability)
        for item in (*self.preconditions, *self.postconditions, *self.invariants):
            identifier(item)
        if not self.postconditions and self.parent_id is None:
            raise ValueError("a root skill requires at least one postcondition")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SkillDefinition:
        data = dict(value)
        for key in ("feedback_requirements", "preconditions", "postconditions", "invariants"):
            data[key] = tuple(data.get(key, ()))
        return cls(**data)


@dataclass(frozen=True)
class ValidationCase:
    frame: EvidenceFrame
    expected: bool


@dataclass(frozen=True)
class Review:
    reviewer: str
    rationale: str
    evidence: tuple[str, ...]

    def __post_init__(self):
        text(self.reviewer, "reviewer")
        text(self.rationale, "rationale")
        if not self.evidence:
            raise ValueError("review requires validation artifact paths")


@dataclass(frozen=True)
class PredicateResult:
    predicate_id: str
    value: bool | None
    reasons: tuple[str, ...]
    predicate_hash: str
    evidence_hash: str
