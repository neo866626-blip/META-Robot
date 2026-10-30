# Action-Level Predicate Library

The library stores shared action criteria P, a parent–child skill forest, and their many-to-many associations Γ. It complements the inherited knowledge applicability evaluator with persistent identities, reviewed admission, feedback contracts and execution-state transitions.

## Predicate definitions

A `PredicateDefinition` contains an immutable ID, explicit semantic key, description, data-only expression and evidence requirements. Each referenced fact must have exactly one `EvidenceRequirement` specifying its modality and maximum age.

Supported expressions are `all`, `any`, `not`, `eq`, `ne`, `exists`, `in`, `contains`, `gt`, `gte`, `lt`, `lte` and `regex`. Nested fact paths such as `signals.contact` refer to explicit observations. They do not run generated Python. Definitions are validated before admission.

`EvidenceFrame` groups observations at an action boundary. Each observation carries a value, modality, source and acquisition timestamp. Evaluation returns True, False or None, accompanied by reasons and hashes of the definition and evidence. Missing data, unavailable modalities, absent provenance, nonfinite values, expired observations and observations from before the completed action cannot establish success. The coordinator measures freshness against its own clock.

A predicate evaluates supplied physical evidence; it is not itself a visual detector. Neural detectors and robot drivers provide observations through adapters. Positive and negative cases validate that a proposed predicate produces the intended decisions on its supplied evidence; hardware validity and semantic adequacy remain part of the review.

## Coupled admission

`predicate_templates()` provides eleven candidate definitions covering visibility, localization, task-role binding, contact, closure, cloth elevation, alignment, containment, target pose, verified acquisition and release readiness. Export them with `meta-robot templates`. Templates are not automatically admitted or labeled as physically validated; configure their evidence adapters and validate them for the selected task and embodiment.

```python
library.consolidate(skill, predicates, validation_cases, review)
```

Admission checks positive and negative examples for every new predicate, existing evidence files and their hashes, reviewer information, hierarchy integrity and all referenced predicate IDs. A failed check leaves the published library unchanged. Writers use a filesystem lock; complete revisions are written as content-addressed snapshots, and the head pointer advances atomically.

Equivalent definitions reuse an existing identity when their explicit semantic key, expression and evidence contract match exactly. This deterministic check does not infer paraphrase equivalence. Changed semantics or feedback requirements need a new predicate ID and validation. Identical logic with a different modality or freshness contract remains distinct.

Skill records include a failure signature, applicability, intent, repair mechanism, feedback requirements and implementation reference. Each review binds validation artifacts to their file hashes. `verify` checks snapshot integrity, hierarchy and review artifacts; moving the library therefore requires retaining its referenced evidence files. A reviewer field records a review assertion rather than authenticating the reviewer's identity.

## Hierarchy and associations

Skills reference predicates by precondition, postcondition and invariant roles. Child skills inherit their ancestors' associations; predicates remain shared rather than being copied. Category indexing returns the union of predicate identities for a subtree. Reparenting creates a reviewed new snapshot without renaming predicates, while historical snapshots remain readable.

Applicability is evaluated conjunctively along the ancestor chain. Retrieval requires all conditions to be true and all declared feedback modalities to be available, then chooses the deepest eligible skill. Equal-depth ties are resolved by skill ID. Unsupported specialization falls back to an applicable ancestor when one exists.

## Execution and completion

`PredicateCoordinator.invoke` records the predicate vector before and after an explicitly supplied skill callable. Preconditions and invariants gate entry. Postconditions and invariants gate continuation. A false postcondition requests repair; missing evidence requests observation rather than another blind action. Local repair uses an explicit callback and a finite retry budget.

Each attempt records its library snapshot, skill ID, associations, pre/post evidence and predicate results. Runtime exceptions cannot produce success. JSONL events form a hash chain. This provides corruption detection; it is not a hardened isolation boundary or an authenticated hardware attestation.

`finish` requires nonempty terminal criteria and an explicit set of required milestones. Completion requires all criteria and milestones to be true. The host is responsible for deriving milestone assertions from its task execution and calling the gate with the complete task specification. Action-boundary invariants do not replace continuous controller-level monitoring.

## Signal evidence

`EvidenceCollector` registers operator-selected feedback callbacks and reports unavailable facts. Read failures remain unresolved. `sustained_threshold` evaluates a bounded signal window only when it has enough distinct samples and no policy-exceeding gaps. Thresholds, units, calibration, sample counts and permitted gaps must be chosen for the actual embodiment.

## Command line

```bash
python -m meta_robot --help
meta-robot --library output/predicate-demo/library inspect
meta-robot --library output/predicate-demo/library verify
meta-robot --library output/predicate-demo/library index skill.contact
meta-robot --library path/to/library consolidate proposal.json
meta-robot --library path/to/library retrieve context.json
```

A consolidation proposal has `skill`, `predicates`, `validation` and `review` objects. Validation maps predicate IDs to cases containing `frame` and `expected`. Review evidence paths are resolved relative to the proposal. A retrieval context provides `facts`, `feedback` and optionally `root_id`. Use [the executable example](../examples/predicate_loop.py) for complete definitions and evidence construction.
