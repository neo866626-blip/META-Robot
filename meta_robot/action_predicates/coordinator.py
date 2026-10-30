# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Evidence-aligned action boundaries, bounded repair, and completion gates."""

from __future__ import annotations

import fcntl
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from aspire.sim.cap.knowledge.serialization import canonical_json, content_hash
from .evaluation import evaluate_predicate
from .library import PredicateLibrary
from .models import EvidenceFrame, PredicateDefinition


class PredicateCoordinator:
    """Wrap actual skill callables; the host supplies sensors and repair policy.

    No robot is created and no motion is enabled by constructing this object.
    ``invoke`` executes only the explicitly supplied action callable.
    """

    def __init__(self, library: PredicateLibrary, trace_path: str | Path, *, clock=time.time):
        self.library = library
        self.trace_path = Path(trace_path)
        self.clock = clock

    def _record(self, event: dict[str, Any]) -> dict[str, Any]:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.seek(0)
            previous = ""
            for line in stream:
                prior = json.loads(line)
                digest = prior.pop("event_hash")
                if prior.get("previous_hash") != previous or content_hash(prior) != digest:
                    raise ValueError("predicate trace integrity mismatch")
                previous = digest
            payload = {**event, "previous_hash": previous}
            payload["event_hash"] = content_hash(payload)
            stream.seek(0, 2)
            stream.write(canonical_json(payload) + "\n")
            stream.flush()
            import os
            os.fsync(stream.fileno())
            return payload

    def invoke(
        self, skill_id: str, action: Callable[[], Any], observe: Callable[[], EvidenceFrame],
        *, facts: dict[str, Any], feedback: set[str], max_repairs: int = 0,
        repair: Callable[[dict[str, Any]], Callable[[], Any]] | None = None,
    ) -> dict[str, Any]:
        if type(max_repairs) is not int or not 0 <= max_repairs <= 32:
            raise ValueError("max_repairs must be an integer from 0 through 32")
        self.library.verify()
        bundle = self.library.retrieve(facts, feedback, root_id=skill_id, exact=True)
        if bundle is None:
            raise ValueError("skill is inapplicable or required feedback is unavailable")
        definitions = [PredicateDefinition.from_dict(p) for p in bundle["predicates"]]
        roles = bundle["associations"]
        invocation = str(uuid.uuid4())
        current_action = action
        for attempt in range(max_repairs + 1):
            before = observe()
            if before.captured_at > self.clock():
                raise ValueError("observation frame is in the future")
            # Age is measured against wall time, not a caller-selected old frame.
            before = EvidenceFrame(before.observations, self.clock())
            pre = [evaluate_predicate(p, before) for p in definitions]
            required_pre = set(roles["preconditions"]) | set(roles["invariants"])
            pre_values = [r.value for r in pre if r.predicate_id in required_pre]
            event = {"kind": "skill-transition", "invocation_id": invocation,
                     "skill_id": skill_id, "attempt": attempt,
                     "snapshot_hash": bundle["snapshot_hash"], "associations": roles,
                     "before": before.to_dict(), "pre": [asdict(r) for r in pre]}
            if any(value is not True for value in pre_values):
                event["decision"] = "probe-required" if None in pre_values else "precondition-failed"
                return self._record(event)
            error = None
            try:
                current_action()
            except Exception as exc:
                error = {"type": type(exc).__name__, "message": str(exc)}
            ended_at = self.clock()
            try:
                after = observe()
                if after.captured_at > self.clock():
                    raise ValueError("observation frame is in the future")
                after = EvidenceFrame(after.observations, self.clock())
                post = [evaluate_predicate(p, after, not_before=ended_at) for p in definitions]
                event.update(after=after.to_dict(), post=[asdict(r) for r in post])
                required_post = set(roles["postconditions"]) | set(roles["invariants"])
                values = [r.value for r in post if r.predicate_id in required_post]
                if None in values:
                    decision = "probe-required"
                elif error is not None or False in values:
                    decision = "repair-required"
                else:
                    decision = "continue"
            except Exception as exc:
                decision = "probe-required"
                event["observation_error"] = {"type": type(exc).__name__, "message": str(exc)}
            event.update(decision=decision, action_error=error, action_ended_at=ended_at)
            recorded = self._record(event)
            if decision != "repair-required" or attempt == max_repairs or repair is None:
                return recorded
            current_action = repair(recorded)
            if not callable(current_action):
                raise ValueError("repair must return an action callable")
        raise AssertionError("unreachable")

    def finish(
        self, predicate_ids: tuple[str, ...], observe: Callable[[], EvidenceFrame], *,
        milestones: dict[str, bool], required_milestones: tuple[str, ...],
    ) -> dict[str, Any]:
        """Require explicit terminal criteria AND every declared milestone."""
        if not predicate_ids or not required_milestones:
            raise ValueError("finish requires terminal predicates and declared milestones")
        self.library.verify()
        state = self.library.snapshot()
        frame = observe()
        if frame.captured_at > self.clock():
            raise ValueError("observation frame is in the future")
        frame = EvidenceFrame(frame.observations, self.clock())
        results = [evaluate_predicate(PredicateDefinition.from_dict(state["predicates"][p]), frame)
                   for p in predicate_ids]
        complete = all(r.value is True for r in results) and all(
            milestones.get(name) is True for name in required_milestones
        )
        return self._record({
            "kind": "finish-gate", "snapshot_hash": content_hash(state),
            "evidence": frame.to_dict(), "results": [asdict(r) for r in results],
            "milestones": milestones, "required_milestones": required_milestones,
            "decision": "complete" if complete else "incomplete",
        })
