# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""META-Robot library inspection, reviewed admission, and retrieval."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .action_predicates import (
    EvidenceFrame, PredicateDefinition, PredicateLibrary, Review, SkillDefinition, ValidationCase,
    predicate_templates,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meta-robot", description=__doc__)
    parser.add_argument("--library", type=Path, default=Path(".meta-robot/library"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="inspect the current coupled library")
    sub.add_parser("verify", help="verify the snapshot and review artifacts")
    sub.add_parser("templates", help="export candidate action-predicate definitions for validation")
    admit = sub.add_parser("consolidate", help="atomically admit a reviewed skill and predicates")
    admit.add_argument("proposal", type=Path)
    retrieve = sub.add_parser("retrieve", help="retrieve the deepest applicable skill and predicates")
    retrieve.add_argument("context", type=Path, help="JSON with facts and feedback")
    index = sub.add_parser("index", help="show predicates shared by a category subtree")
    index.add_argument("skill_id")
    args = parser.parse_args(argv)
    library = PredicateLibrary(args.library)
    try:
        if args.command == "templates":
            result = {"status": "candidate-templates", "predicates": [asdict(p) for p in predicate_templates()]}
        elif args.command == "inspect":
            result = library.snapshot()
        elif args.command == "verify":
            result = library.verify()
        elif args.command == "index":
            result = {"predicate_ids": library.category_index(args.skill_id)}
        elif args.command == "retrieve":
            payload = json.loads(args.context.read_text())
            result = library.retrieve(payload["facts"], set(payload["feedback"]), root_id=payload.get("root_id"))
        else:
            payload = json.loads(args.proposal.read_text())
            review = payload["review"]
            evidence = tuple(str((args.proposal.parent / p).resolve()) for p in review["evidence"])
            result = library.consolidate(
                SkillDefinition.from_dict(payload["skill"]),
                tuple(PredicateDefinition.from_dict(p) for p in payload.get("predicates", [])),
                {key: tuple(ValidationCase(EvidenceFrame.from_dict(c["frame"]), c["expected"])
                            for c in cases) for key, cases in payload.get("validation", {}).items()},
                Review(review["reviewer"], review["rationale"], evidence),
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(2, f"meta-robot: {exc}\n")
    return 0
