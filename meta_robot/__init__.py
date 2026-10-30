# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""META-Robot: evidence-grounded cognition and capability scaling."""

from .action_predicates import (
    EvidenceFrame, EvidenceRequirement, Observation, PredicateDefinition,
    PredicateLibrary, PredicateCoordinator, SkillDefinition, ValidationCase,
    Review, evaluate_predicate,
)

__version__ = "0.2.0"
__all__ = [
    "EvidenceFrame", "EvidenceRequirement", "Observation", "PredicateDefinition",
    "PredicateLibrary", "PredicateCoordinator", "SkillDefinition", "ValidationCase",
    "Review", "evaluate_predicate",
]
