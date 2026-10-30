# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Regression tests for the coupled action-level predicate library."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from meta_robot.action_predicates import (
    EvidenceCollector, EvidenceFrame, EvidenceRequirement, Observation,
    PredicateCoordinator, PredicateDefinition, PredicateLibrary, Review,
    SignalSample, SkillDefinition, ValidationCase, evaluate_predicate, sustained_threshold,
    predicate_templates,
)


def frame(value=True, *, timestamp=100.0, modality="force", source="test-sensor"):
    return EvidenceFrame({"signals.contact": Observation(value, modality, source, timestamp)}, 100.0)


def predicate(id="predicate.contact"):
    return PredicateDefinition(id, "contact-detected", "Physical contact is detected",
                               {"fact": "signals.contact", "op": "eq", "value": True},
                               (EvidenceRequirement("signals.contact", "force", 2.0),))


def skill(id="skill.contact", **changes):
    value = SkillDefinition(id, "Contact-aware interaction", "examples/contact.py:act",
                            "no stable contact", "establish contact", "adjust approach",
                            postconditions=("predicate.contact",))
    return replace(value, **changes)


class PredicateLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "validation.json"
        self.artifact.write_text('{"fixture":true,"success":true}')
        self.review = Review("test-reviewer", "Synthetic test fixture", (str(self.artifact),))
        self.lib = PredicateLibrary(self.root / "library")
        self.cases = {"predicate.contact": (ValidationCase(frame(True), True), ValidationCase(frame(False), False))}

    def tearDown(self):
        self.tmp.cleanup()

    def admit(self, value=None):
        return self.lib.consolidate(value or skill(), (predicate(),), self.cases, self.review)

    def coordinator(self):
        return PredicateCoordinator(self.lib, self.root / "trace.jsonl", clock=lambda: 100.0)

    def test_required_evidence_is_three_valued(self):
        self.assertIs(evaluate_predicate(predicate(), frame()).value, True)
        self.assertIs(evaluate_predicate(predicate(), frame(False)).value, False)
        self.assertIsNone(evaluate_predicate(predicate(), EvidenceFrame({}, 100)).value)

    def test_stale_wrong_modality_missing_source_nan_and_null_are_unknown(self):
        for evidence in (frame(timestamp=90), frame(modality="vision"), frame(source=""),
                         frame(float("nan")), frame(None), frame(timestamp=101)):
            with self.subTest(evidence=evidence):
                result = evaluate_predicate(predicate(), evidence)
                self.assertIsNone(result.value)
                self.assertTrue(result.reasons)

    def test_unsupported_or_ambiguous_expressions_are_rejected(self):
        for expr in ({}, {"all": []}, {"fact": "a", "op": "exec", "value": "x"},
                     {"all": [{"fact": "signals.contact", "value": True}], "not": {}},
                     {"fact": "signals.contact", "op": "gt", "value": float("nan")}):
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                replace(predicate(), expression=expr)

    def test_requirements_must_cover_all_expression_facts(self):
        with self.assertRaises(ValueError):
            replace(predicate(), requirements=())

    def test_numeric_one_does_not_establish_a_boolean_condition(self):
        result = evaluate_predicate(predicate(), frame(1))
        self.assertIsNone(result.value)
        self.assertIn("type-mismatch:signals.contact", result.reasons)

    def test_invalid_timestamp_is_unresolved(self):
        self.assertIsNone(evaluate_predicate(predicate(), frame(timestamp="unknown")).value)

    def test_contact_does_not_establish_acquisition(self):
        held = PredicateDefinition(
            "predicate.held", "held-object", "Contact and verified acquisition",
            {"all": [{"fact": "signals.contact", "value": True},
                     {"fact": "vision.acquired", "value": True}]},
            (EvidenceRequirement("signals.contact", "force"), EvidenceRequirement("vision.acquired", "vision")),
        )
        evidence = frame()
        evidence = EvidenceFrame({**evidence.observations,
                                  "vision.acquired": Observation(False, "vision", "camera", 100)}, 100)
        self.assertTrue(evaluate_predicate(predicate(), evidence).value)
        self.assertFalse(evaluate_predicate(held, evidence).value)

    def test_admission_persists_review_and_reloads(self):
        result = self.admit()
        reloaded = PredicateLibrary(self.lib.root)
        self.assertEqual(reloaded.verify()["predicates"], 1)
        self.assertEqual(reloaded.snapshot(result["snapshot_hash"])["revision"], 1)
        self.assertEqual(reloaded.snapshot()["reviews"][0]["reviewer"], "test-reviewer")

    def test_rejected_candidate_does_not_partially_publish(self):
        self.admit()
        old = self.lib.snapshot()
        bad = replace(predicate("predicate.other"), semantic_key="different")
        with self.assertRaises(ValueError):
            self.lib.consolidate(skill("skill.other"), (bad,), {}, self.review)
        self.assertEqual(self.lib.snapshot(), old)

    def test_positive_and_negative_cases_must_both_pass(self):
        for cases in ((ValidationCase(frame(), True),),
                      (ValidationCase(frame(), True), ValidationCase(frame(), False))):
            with self.assertRaises(ValueError):
                self.lib.consolidate(skill(), (predicate(),), {predicate().id: cases}, self.review)
        self.assertEqual(self.lib.snapshot()["revision"], 0)

    def test_semantic_reuse_preserves_shared_identity(self):
        self.admit()
        alias = predicate("predicate.same-contact")
        result = self.lib.consolidate(skill("skill.other", postconditions=(alias.id,)),
                                      (alias,), {}, self.review)
        self.assertEqual(result["aliases"][alias.id], "predicate.contact")
        self.assertEqual(len(self.lib.snapshot()["predicates"]), 1)
        self.assertEqual(self.lib.snapshot()["skills"]["skill.other"]["postconditions"], ["predicate.contact"])

    def test_feedback_semantics_cannot_be_overwritten(self):
        self.admit()
        with self.assertRaises(ValueError):
            self.lib.consolidate(skill(), (replace(predicate(), expression={"fact": "signals.contact", "value": False}),),
                                 self.cases, self.review)

    def test_inheritance_and_category_union(self):
        self.admit()
        self.lib.consolidate(skill("skill.child", parent_id="skill.contact", postconditions=()), (), {}, self.review)
        self.assertEqual(self.lib.associations(self.lib.snapshot(), "skill.child")["postconditions"], ["predicate.contact"])
        self.assertEqual(self.lib.category_index("skill.contact"), ["predicate.contact"])

    def test_reparenting_preserves_predicate_ids_and_archived_state(self):
        old = self.admit()
        self.lib.consolidate(skill("skill.other"), (), {}, self.review)
        self.lib.consolidate(skill(parent_id="skill.other"), (), {}, self.review)
        self.assertEqual(self.lib.category_index("skill.other"), ["predicate.contact"])
        self.assertIsNone(self.lib.snapshot(old["snapshot_hash"])["skills"]["skill.contact"]["parent_id"])

    def test_cycle_and_dangling_links_are_rejected(self):
        self.admit()
        for changed in (skill(parent_id="skill.contact"), skill(parent_id="skill.missing"),
                        skill(postconditions=("predicate.absent",))):
            with self.assertRaises(ValueError):
                self.lib.consolidate(changed, (), {}, self.review)
        self.assertEqual(self.lib.snapshot()["revision"], 1)

    def test_deepest_applicable_skill_respects_feedback_and_ancestor_conditions(self):
        self.admit(skill(applicability={"fact": "task.grasp", "value": True}))
        child = skill("skill.thin", parent_id="skill.contact", feedback_requirements=("torque",),
                      applicability={"fact": "task.thin", "value": True})
        self.lib.consolidate(child, (), {}, self.review)
        facts = {"task.grasp": True, "task.thin": True}
        self.assertEqual(self.lib.retrieve(facts, {"force"})["skill"]["id"], "skill.contact")
        self.assertEqual(self.lib.retrieve(facts, {"force", "torque"})["skill"]["id"], "skill.thin")
        self.assertIsNone(self.lib.retrieve({"task.thin": True}, {"force", "torque"}))
        self.assertIsNone(self.lib.retrieve(facts, {"vision"}))

    def test_snapshot_and_review_evidence_tampering_are_detected(self):
        result = self.admit()
        self.artifact.write_text("changed")
        with self.assertRaisesRegex(ValueError, "evidence missing or changed"):
            self.lib.verify()
        path = self.lib.root / "snapshots" / (result["snapshot_hash"] + ".json")
        data = json.loads(path.read_text())
        data["revision"] = 500
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            self.lib.snapshot()

    def test_real_callable_records_pre_and_post_predicate_states(self):
        self.admit()
        values = iter([frame(False), frame(True)])
        calls = []
        event = self.coordinator().invoke("skill.contact", lambda: calls.append("called"), lambda: next(values),
                                           facts={}, feedback={"force"})
        self.assertEqual(calls, ["called"])
        self.assertEqual(event["decision"], "continue")
        self.assertFalse(event["pre"][0]["value"])
        self.assertTrue(event["post"][0]["value"])

    def test_unknown_precondition_blocks_action(self):
        self.admit(skill(preconditions=("predicate.contact",)))
        calls = []
        event = self.coordinator().invoke("skill.contact", lambda: calls.append(1),
                                           lambda: EvidenceFrame({}, 100), facts={}, feedback={"force"})
        self.assertEqual(event["decision"], "probe-required")
        self.assertFalse(calls)

    def test_post_action_old_evidence_cannot_confirm_success(self):
        self.admit()
        values = iter([frame(False), frame(True, timestamp=99.9)])
        event = self.coordinator().invoke("skill.contact", lambda: None, lambda: next(values),
                                           facts={}, feedback={"force"})
        self.assertEqual(event["decision"], "probe-required")
        self.assertIn("pre-action-evidence:signals.contact", event["post"][0]["reasons"])

    def test_local_repair_has_finite_budget_and_records_each_attempt(self):
        self.admit()
        calls = []
        event = self.coordinator().invoke("skill.contact", lambda: calls.append(1), lambda: frame(False),
                                           facts={}, feedback={"force"}, max_repairs=2,
                                           repair=lambda event: lambda: calls.append(1))
        self.assertEqual(len(calls), 3)
        self.assertEqual(event["decision"], "repair-required")
        self.assertEqual(len((self.root / "trace.jsonl").read_text().splitlines()), 3)

    def test_unknown_postcondition_requests_probe_without_blind_retry(self):
        self.admit()
        calls = []
        event = self.coordinator().invoke("skill.contact", lambda: calls.append(1),
                                           lambda: EvidenceFrame({}, 100), facts={}, feedback={"force"},
                                           max_repairs=3, repair=lambda event: lambda: calls.append(1))
        self.assertEqual(event["decision"], "probe-required")
        self.assertEqual(len(calls), 1)

    def test_exception_cannot_be_reported_as_success(self):
        self.admit()
        def fail():
            raise RuntimeError("action failed")
        event = self.coordinator().invoke("skill.contact", fail, lambda: frame(True), facts={}, feedback={"force"})
        self.assertEqual(event["decision"], "repair-required")
        self.assertEqual(event["action_error"]["type"], "RuntimeError")

    def test_finish_requires_all_terminal_conditions_and_explicit_milestones(self):
        self.admit()
        coordinator = self.coordinator()
        for milestones, expected in (({}, "incomplete"), ({"placed": True}, "complete")):
            event = coordinator.finish(("predicate.contact",), lambda: frame(),
                                       milestones=milestones, required_milestones=("placed",))
            self.assertEqual(event["decision"], expected)
        with self.assertRaises(ValueError):
            coordinator.finish((), lambda: frame(), milestones={}, required_milestones=())

    def test_cli_is_runnable_without_simulator_dependencies(self):
        self.admit()
        result = subprocess.run([sys.executable, "-m", "meta_robot", "--library", str(self.lib.root), "verify"],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["skills"], 1)

    def test_cli_consolidates_a_proposal_with_relative_review_evidence(self):
        from dataclasses import asdict
        proposal = self.root / "proposal.json"
        proposal.write_text(json.dumps({
            "skill": asdict(skill()), "predicates": [asdict(predicate())],
            "validation": {key: [asdict(case) for case in cases] for key, cases in self.cases.items()},
            "review": {"reviewer": "test-reviewer", "rationale": "synthetic fixture",
                       "evidence": [self.artifact.name]},
        }))
        result = subprocess.run([sys.executable, "-m", "meta_robot", "--library", str(self.lib.root),
                                 "consolidate", str(proposal)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["revision"], 1)
        self.assertEqual(self.lib.verify()["predicates"], 1)


class SignalTests(unittest.TestCase):
    def test_catalog_has_distinct_contact_closure_and_acquisition_criteria(self):
        templates = {p.id: p for p in predicate_templates()}
        self.assertEqual(len(templates), 11)
        self.assertNotEqual(templates["predicate.contact"].semantic_hash, templates["predicate.held"].semantic_hash)
        self.assertNotEqual(templates["predicate.closed"].semantic_hash, templates["predicate.held"].semantic_hash)
        self.assertIsNone(evaluate_predicate(templates["predicate.held"], frame()).value)

    def test_release_readiness_retains_verified_acquisition_requirements(self):
        templates = {p.id: p for p in predicate_templates()}
        held = templates["predicate.held"]
        release = templates["predicate.release-ready"]
        self.assertLessEqual({r.fact for r in held.requirements}, {r.fact for r in release.requirements})
        observations = {r.fact: Observation(r.fact != "signals.contact", r.modality, "fixture", 100)
                        for r in release.requirements}
        self.assertFalse(evaluate_predicate(release, EvidenceFrame(observations, 100)).value)

    def test_temporal_contact_requires_coverage_and_stability(self):
        policy = dict(start=0, end=1, threshold=2, min_samples=3, max_gap_s=0.4)
        self.assertIsNone(sustained_threshold((SignalSample(0, 3), SignalSample(1, 3)), **policy))
        samples = tuple(SignalSample(t, 3) for t in (0, .3, .6, 1))
        self.assertTrue(sustained_threshold(samples, **policy))
        self.assertFalse(sustained_threshold((*samples[:-1], SignalSample(1, 1)), **policy))

    def test_feedback_adapter_preserves_missing_measurements(self):
        collector = EvidenceCollector(clock=lambda: 100)
        collector.register("signals.contact", "force", "force-sensor", lambda: True)
        self.assertEqual(collector.missing(predicate().requirements), [])
        self.assertTrue(evaluate_predicate(predicate(), collector.collect()).value)
        collector.register("signals.torque", "torque", "joint-driver", lambda: 1 / 0)
        self.assertIsNone(collector.collect().observations["signals.torque"].value)


if __name__ == "__main__":
    unittest.main()
