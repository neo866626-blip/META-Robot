# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Ground predicate decisions in fresh, modality-matched evidence."""

from __future__ import annotations

import math
from typing import Any

from aspire.sim.cap.knowledge.predicates import evaluate
from aspire.sim.cap.knowledge.serialization import content_hash
from .models import EvidenceFrame, PredicateDefinition, PredicateResult


def finite_time(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def finite_json(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, list):
        return all(finite_json(x) for x in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and finite_json(v) for k, v in value.items())
    return False


def evaluate_predicate(
    predicate: PredicateDefinition, frame: EvidenceFrame, *, not_before: float | None = None,
) -> PredicateResult:
    reasons: list[str] = []
    facts: dict[str, Any] = {}
    if not finite_time(frame.captured_at):
        reasons.append("invalid-frame-time")
    for requirement in predicate.requirements:
        obs = frame.observations.get(requirement.fact)
        if obs is None:
            reasons.append(f"missing:{requirement.fact}")
            continue
        if obs.modality != requirement.modality:
            reasons.append(f"modality-mismatch:{requirement.fact}")
        if not isinstance(obs.source, str) or not obs.source.strip():
            reasons.append(f"missing-source:{requirement.fact}")
        if not finite_json(obs.value):
            reasons.append(f"unresolved:{requirement.fact}")
        if not finite_time(obs.observed_at):
            reasons.append(f"invalid-time:{requirement.fact}")
        elif not finite_time(frame.captured_at):
            pass
        elif obs.observed_at > frame.captured_at:
            reasons.append(f"future:{requirement.fact}")
        elif frame.captured_at - obs.observed_at > requirement.max_age_s:
            reasons.append(f"stale:{requirement.fact}")
        if not_before is not None and finite_time(obs.observed_at) and obs.observed_at < not_before:
            reasons.append(f"pre-action-evidence:{requirement.fact}")
        facts[requirement.fact] = obs.value
    def check_types(expr: dict[str, Any]) -> None:
        if "all" in expr or "any" in expr:
            for child in expr.get("all", expr.get("any", [])):
                check_types(child)
        elif "not" in expr:
            check_types(expr["not"])
        else:
            actual = facts.get(expr["fact"])
            expected = expr.get("value")
            op = expr.get("op", "eq")
            if op in {"eq", "ne"} and isinstance(expected, bool) and type(actual) is not bool:
                reasons.append(f"type-mismatch:{expr['fact']}")
            if op in {"gt", "gte", "lt", "lte"} and not finite_time(actual):
                reasons.append(f"type-mismatch:{expr['fact']}")
    check_types(predicate.expression)
    value = None
    if not reasons:
        try:
            value = evaluate(predicate.expression, facts)
        except (TypeError, ValueError, OverflowError) as exc:
            reasons.append(f"incompatible-evidence:{type(exc).__name__}")
        if value is None and not reasons:
            reasons.append("unresolved-expression")
    return PredicateResult(
        predicate.id, value, tuple(reasons), content_hash(predicate.__dict__),
        content_hash(frame.to_dict()),
    )
