# META-Robot Paper and Code

The implementation follows the action-level predicate and skill formulation in *META-Robot: Self Cognition and Capability Scaling in Agentic Robots*, Section 3.2 and the coupled-library consolidation algorithm. The library core is exposed through `meta_robot`; inherited execution and simulator infrastructure retains its `aspire` imports.

| Method component | Implementation | Verification |
| --- | --- | --- |
| Skill attributes: failure, applicability, intent, repair, feedback, implementation and validation | `SkillDefinition` and reviewed artifact records | Admission and integrity tests |
| Shared predicate set P and skill associations Γ(v) | `PredicateDefinition`, `PredicateLibrary.associations` | Shared identity, alias reuse and inheritance tests |
| Before/after vectors z− and z+ | `PredicateCoordinator.invoke` | Callable execution and pre/post transition tests |
| Parent–child specialization | Ancestor-conjoined applicability and reviewed skill snapshots | Hierarchy, reparenting and ancestor applicability tests |
| Subtree predicate index P_b | `PredicateLibrary.category_index` | Subtree union and stable identity tests |
| Deepest applicable skill with available feedback | `PredicateLibrary.retrieve` | Modality availability and fallback tests |
| Incremental joint consolidation | `PredicateLibrary.consolidate` | Positive/negative cases, rejection rollback and immutable snapshots |
| Action-aligned physical evidence | `EvidenceFrame`, `EvidenceCollector`, `evaluate_predicate` | Freshness, wrong modality, unavailable and pre-action evidence tests |
| Bounded local repair and task completion | `PredicateCoordinator.invoke`, `finish` | Retry budget, unresolved evidence, exceptions and finish-gate tests |
| Temporal proprioceptive criteria | `sustained_threshold` and registered adapters | Window coverage and sustained-condition tests |

The runnable example uses synthetic observations to demonstrate these interfaces. The real-robot gallery is extracted from supplied experiment footage. Reproducing paper benchmarks requires the original task programs, task splits, model settings, calibrated hardware adapters and evaluation records; the gallery and core unit tests do not substitute for those artifacts.

Candidate distillation and the selection of semantic abstractions remain the responsibility of the calling agent and reviewer. The library enforces deterministic admission and provenance rather than claiming to automatically discover perceptual criteria from an unannotated video. Existing knowledge-forest experiments under `aspire/sim/knowledge` retain their own frozen protocols and completion gates.
