# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Run the full library/transition workflow using synthetic observations.

This example never opens a camera, connects to a robot, or claims validation of
physical manipulation. Replace the explicit callbacks with a reviewed adapter
to use the same coordinator with a simulator or robot runtime.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from meta_robot.action_predicates import (
    EvidenceCollector, EvidenceFrame, EvidenceRequirement, Observation,
    PredicateCoordinator, PredicateDefinition, PredicateLibrary, Review,
    SkillDefinition, ValidationCase,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/predicate-demo"))
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = args.output / "synthetic-validation.json"
    evidence.write_text(json.dumps({"kind": "synthetic-example", "physical_validation": False}))
    contact = PredicateDefinition(
        "predicate.contact", "physical-contact", "Contact is detected at the action boundary",
        {"fact": "signals.contact", "value": True},
        (EvidenceRequirement("signals.contact", "force"),),
    )
    held = PredicateDefinition(
        "predicate.held", "verified-object-acquisition", "Contact, visual acquisition and load agree",
        {"all": [{"fact": key, "value": True} for key in
                 ("signals.contact", "vision.acquired", "signals.load_stable")]},
        (EvidenceRequirement("signals.contact", "force"),
         EvidenceRequirement("vision.acquired", "vision"),
         EvidenceRequirement("signals.load_stable", "torque")),
    )

    def validation_frame(acquired):
        now = time.time()
        return EvidenceFrame({
            "signals.contact": Observation(True, "force", "synthetic-force", now),
            "vision.acquired": Observation(acquired, "vision", "synthetic-camera", now),
            "signals.load_stable": Observation(True, "torque", "synthetic-joints", now),
        }, now)

    library = PredicateLibrary(args.output / "library")
    review = Review("example-fixture", "Synthetic workflow validation only", (str(evidence),))
    contact_skill = SkillDefinition(
        "skill.contact", "Contact-aware acquisition", "examples.predicate_loop:close",
        "no verified acquisition", "establish contact", "adjust the approach",
        postconditions=(contact.id,),
    )
    no_contact = validation_frame(False)
    no_contact = EvidenceFrame({**no_contact.observations,
                               "signals.contact": Observation(False, "force", "synthetic-force", no_contact.captured_at)},
                              no_contact.captured_at)
    library.consolidate(contact_skill, (contact,), {contact.id: (
        ValidationCase(validation_frame(True), True), ValidationCase(no_contact, False),
    )}, review)
    grasp_skill = SkillDefinition(
        "skill.grasp", "Verified grasp", "examples.predicate_loop:close",
        "contact without acquisition", "acquire and retain the object", "adjust and verify again",
        parent_id=contact_skill.id, postconditions=(held.id,),
    )
    library.consolidate(grasp_skill, (held,), {held.id: (
        ValidationCase(validation_frame(True), True), ValidationCase(validation_frame(False), False),
    )}, review)
    state = {"contact": False, "acquired": False, "load": True}
    collector = EvidenceCollector()
    collector.register("signals.contact", "force", "synthetic-force", lambda: state["contact"])
    collector.register("vision.acquired", "vision", "synthetic-camera", lambda: state["acquired"])
    collector.register("signals.load_stable", "torque", "synthetic-joints", lambda: state["load"])

    def close():
        state["contact"] = True

    def repair(_event):
        return lambda: state.update(acquired=True)

    coordinator = PredicateCoordinator(library, args.output / "predicate-transitions.jsonl")
    transition = coordinator.invoke(grasp_skill.id, close, collector.collect, facts={},
                                    feedback=collector.modalities, max_repairs=1, repair=repair)
    finish = coordinator.finish((held.id,), collector.collect,
                                 milestones={"verified-grasp": transition["decision"] == "continue"},
                                 required_milestones=("verified-grasp",))
    print(json.dumps({"library": library.verify(), "transition": transition["decision"],
                      "finish": finish["decision"], "physical_validation": False,
                      "trace": str(coordinator.trace_path)}, indent=2))


if __name__ == "__main__":
    main()
