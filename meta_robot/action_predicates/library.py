# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Transactional shared predicates and a coupled, revisioned skill forest."""

from __future__ import annotations

import copy
import fcntl
import json
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Iterator

from aspire.sim.cap.knowledge.predicates import evaluate
from aspire.sim.cap.knowledge.serialization import content_hash, sha256_file, write_structured_atomic
from .evaluation import evaluate_predicate
from .models import PredicateDefinition, Review, SkillDefinition, ValidationCase


class PredicateLibrary:
    """Keep P, the skill forest, and Gamma in one content-addressed snapshot.

    A reviewed consolidation is all-or-nothing. Predicate definitions are never
    overwritten; skill revisions live in immutable historical snapshots.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def snapshot(self, digest: str | None = None) -> dict[str, Any]:
        if digest is None:
            head = self.root / "HEAD.json"
            if not head.exists():
                return {"schema_version": 1, "revision": 0, "predicates": {}, "skills": {}, "reviews": []}
            digest = json.loads(head.read_text())["snapshot_hash"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid snapshot hash")
        state = json.loads((self.root / "snapshots" / f"{digest}.json").read_text())
        if content_hash(state) != digest:
            raise ValueError("predicate library snapshot integrity mismatch")
        return state

    @staticmethod
    def _chain(state: dict[str, Any], skill_id: str) -> list[SkillDefinition]:
        chain: list[SkillDefinition] = []
        visited = set()
        current: str | None = skill_id
        while current is not None:
            if current in visited:
                raise ValueError("skill hierarchy contains a cycle")
            visited.add(current)
            if current not in state["skills"]:
                raise ValueError(f"unknown parent or skill: {current}")
            skill = SkillDefinition.from_dict(state["skills"][current])
            chain.append(skill)
            current = skill.parent_id
        return list(reversed(chain))

    @classmethod
    def associations(cls, state: dict[str, Any], skill_id: str) -> dict[str, list[str]]:
        """Gamma(v): retain roles while sharing predicate identities."""
        result: dict[str, list[str]] = {key: [] for key in ("preconditions", "postconditions", "invariants")}
        for skill in cls._chain(state, skill_id):
            for role in result:
                result[role] = sorted(set(result[role]) | set(getattr(skill, role)))
        return result

    @classmethod
    def _validate_forest(cls, state: dict[str, Any]) -> None:
        for skill_id in state["skills"]:
            roles = cls.associations(state, skill_id)
            for predicate_id in set().union(*(set(x) for x in roles.values())):
                if predicate_id not in state["predicates"]:
                    raise ValueError(f"unknown predicate association: {predicate_id}")
            if not roles["postconditions"]:
                raise ValueError("every skill requires inherited or explicit postconditions")

    def consolidate(
        self, skill: SkillDefinition, predicates: tuple[PredicateDefinition, ...],
        validation: dict[str, tuple[ValidationCase, ...]], review: Review,
    ) -> dict[str, Any]:
        """Admit a reviewed repair and validated predicates in one transaction.

        Semantics are identified by an explicit semantic key plus exact
        expression and feedback requirements; no language-model equivalence
        decision or hardware validation is fabricated here.
        """
        evidence = []
        for artifact in review.evidence:
            path = Path(artifact).resolve(strict=True)
            if not path.is_file():
                raise ValueError("review evidence must be a regular file")
            evidence.append({"path": str(path), "sha256": sha256_file(path)})
        with self._lock():
            previous = self.snapshot()
            state = copy.deepcopy(previous)
            aliases: dict[str, str] = {}
            cases_by_id: dict[str, Any] = {}
            semantic_index = {
                PredicateDefinition.from_dict(p).semantic_hash: key
                for key, p in state["predicates"].items()
            }
            if len({p.id for p in predicates}) != len(predicates):
                raise ValueError("duplicate predicate IDs in a proposal")
            for predicate in predicates:
                payload = asdict(predicate)
                PredicateDefinition.from_dict(payload)
                if predicate.id in state["predicates"]:
                    if content_hash(state["predicates"][predicate.id]) != content_hash(payload):
                        raise ValueError("predicate identities are immutable; use a new ID for changed semantics")
                    aliases[predicate.id] = predicate.id
                    continue
                equivalent = semantic_index.get(predicate.semantic_hash)
                if equivalent is not None:
                    aliases[predicate.id] = equivalent
                    continue
                cases = validation.get(predicate.id, ())
                if any(type(c.expected) is not bool for c in cases) or {c.expected for c in cases} != {True, False}:
                    raise ValueError(f"predicate {predicate.id} requires positive and negative validation cases")
                for case in cases:
                    result = evaluate_predicate(predicate, case.frame)
                    if result.value is not case.expected:
                        raise ValueError(f"predicate validation failed: {predicate.id}: {result.reasons}")
                cases_by_id[predicate.id] = [asdict(x) for x in cases]
                aliases[predicate.id] = predicate.id
                state["predicates"][predicate.id] = payload
                semantic_index[predicate.semantic_hash] = predicate.id
            skill = replace(skill, **{
                role: tuple(aliases.get(x, x) for x in getattr(skill, role))
                for role in ("preconditions", "postconditions", "invariants")
            })
            state["skills"][skill.id] = asdict(skill)
            self._validate_forest(state)
            state["revision"] += 1
            state["parent_hash"] = content_hash(previous)
            state["reviews"].append({
                "revision": state["revision"], "skill_id": skill.id,
                "reviewer": review.reviewer, "rationale": review.rationale,
                "evidence": evidence, "validation_cases": cases_by_id,
                "aliases": aliases,
            })
            # Reject NaN, unsupported values, or invalid proposals before writing.
            json.dumps(state, allow_nan=False)
            digest = content_hash(state)
            destination = self.root / "snapshots" / f"{digest}.json"
            if destination.exists() and json.loads(destination.read_text()) != state:
                raise ValueError("snapshot collision")
            if not destination.exists():
                write_structured_atomic(destination, state)
            write_structured_atomic(self.root / "HEAD.json", {"snapshot_hash": digest})
            return {"snapshot_hash": digest, "revision": state["revision"], "aliases": aliases}

    def category_index(self, skill_id: str) -> list[str]:
        """P_b = union of Gamma(v) over the category subtree."""
        state = self.snapshot()
        self._chain(state, skill_id)
        result: set[str] = set()
        for candidate in state["skills"]:
            if skill_id in {x.id for x in self._chain(state, candidate)}:
                for refs in self.associations(state, candidate).values():
                    result.update(refs)
        return sorted(result)

    def retrieve(
        self, facts: dict[str, Any], feedback: set[str], *, root_id: str | None = None,
        exact: bool = False,
    ) -> dict[str, Any] | None:
        """Equation 6: deepest applicable skill with available feedback.

        Applicability is the conjunction of all ancestor conditions, enforcing
        specialization at retrieval even for overlapping local descriptions.
        """
        state = self.snapshot()
        if root_id is not None:
            self._chain(state, root_id)
        matches = []
        for skill_id in state["skills"]:
            if exact and skill_id != root_id:
                continue
            chain = self._chain(state, skill_id)
            if root_id is not None and root_id not in {s.id for s in chain}:
                continue
            try:
                applicable = all(evaluate(s.applicability, facts) is True for s in chain)
            except (TypeError, ValueError):
                applicable = False
            roles = self.associations(state, skill_id)
            predicate_ids = sorted(set().union(*(set(x) for x in roles.values())))
            requirements = {r for s in chain for r in s.feedback_requirements}
            requirements.update(
                r.modality for p in predicate_ids
                for r in PredicateDefinition.from_dict(state["predicates"][p]).requirements
            )
            if applicable and requirements <= feedback:
                matches.append((len(chain), skill_id, roles, predicate_ids))
        if not matches:
            return None
        _, skill_id, roles, predicate_ids = sorted(matches, key=lambda x: (-x[0], x[1]))[0]
        return {
            "snapshot_hash": content_hash(state), "skill": state["skills"][skill_id],
            "associations": roles,
            "predicates": [state["predicates"][p] for p in predicate_ids],
        }

    def verify(self) -> dict[str, Any]:
        state = self.snapshot()
        self._validate_forest(state)
        for p in state["predicates"].values():
            PredicateDefinition.from_dict(p)
        for record in state["reviews"]:
            for artifact in record["evidence"]:
                path = Path(artifact["path"])
                if not path.is_file() or sha256_file(path) != artifact["sha256"]:
                    raise ValueError(f"review evidence missing or changed: {path}")
        return {"snapshot_hash": content_hash(state), "revision": state["revision"],
                "predicates": len(state["predicates"]), "skills": len(state["skills"])}
