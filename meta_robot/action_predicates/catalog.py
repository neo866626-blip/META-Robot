# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Reusable action-criterion templates; admission still requires validation."""

from .models import EvidenceRequirement, PredicateDefinition


def predicate_templates(*, max_age_s: float = 2.0) -> tuple[PredicateDefinition, ...]:
    """Return unadmitted definitions for the paper's action-state vocabulary.

    Boolean inputs are resolved by the host's perception or signal adapter.
    Returning templates does not claim these detectors have been calibrated.
    """
    atomic = (
        ("visible", "Target is visible", "vision.target_visible", "vision"),
        ("localized", "Target has a metric localization", "geometry.target_localized", "geometry"),
        ("role-bound", "Target is bound to its task role", "task.role_bound", "semantic"),
        ("contact", "Physical contact is detected", "signals.contact", "force"),
        ("closed", "Gripper closure is observed", "gripper.closed", "gripper"),
        ("cloth-elevated", "Cloth is elevated above its support", "geometry.cloth_elevated", "geometry"),
        ("aligned", "Object and destination are aligned", "geometry.aligned", "geometry"),
        ("inside", "Object is inside its target region", "geometry.inside", "geometry"),
        ("at-target-pose", "Object satisfies the target pose criterion", "geometry.at_target_pose", "geometry"),
    )
    result = [PredicateDefinition(
        f"predicate.{key}", key, description,
        {"fact": fact, "op": "eq", "value": True},
        (EvidenceRequirement(fact, modality, max_age_s),),
    ) for key, description, fact, modality in atomic]
    for key, description, facts in (
        ("held", "Acquisition is supported by contact, vision and stable load",
         (("signals.contact", "force"), ("vision.acquired", "vision"), ("signals.load_stable", "torque"))),
        ("release-ready", "Verified acquisition and placement geometry permit release",
         (("signals.contact", "force"), ("vision.acquired", "vision"), ("signals.load_stable", "torque"),
          ("geometry.inside", "geometry"), ("geometry.aligned", "geometry"))),
    ):
        result.append(PredicateDefinition(
            f"predicate.{key}", key, description,
            {"all": [{"fact": fact, "value": True} for fact, _ in facts]},
            tuple(EvidenceRequirement(fact, modality, max_age_s) for fact, modality in facts),
        ))
    return tuple(result)
