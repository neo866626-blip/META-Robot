# Runtime Integration

Use the coordinator at explicit skill boundaries in an existing simulator or robot program. The caller owns the control policy, observation providers, repair policy and task specification.

## Connect feedback

Register callbacks for task-relevant signals. Each callback must acquire current evidence; returning a cached pre-action observation would misrepresent its acquisition time. Drivers that already provide hardware timestamps can construct `Observation` and `EvidenceFrame` directly. Use a consistent clock domain with the coordinator.

```python
from meta_robot.action_predicates import EvidenceCollector, PredicateCoordinator

collector = EvidenceCollector()
collector.register("signals.contact", "force", "wrist-sensor", read_contact)
collector.register("vision.acquired", "vision", "grasp-verifier", read_acquisition)
collector.register("signals.load_stable", "torque", "joint-driver", read_stable_load)

coordinator = PredicateCoordinator(library, trial_dir / "predicate-transitions.jsonl")
result = coordinator.invoke(
    "skill.grasp", execute_grasp, collector.collect,
    facts=task_context, feedback=collector.modalities,
    max_repairs=2, repair=build_local_repair,
)
```

Here `read_contact`, `read_acquisition`, `read_stable_load`, `execute_grasp` and `build_local_repair` are host-supplied callables. They may wrap existing `aspire.sim.cap` APIs or a real-robot adapter. Library construction and inspection do not start services or enable motion.

## Handle decisions

- `continue`: all required postconditions and action-boundary invariants are true.
- `probe-required`: acquire fresh evidence or perform a separately authorized probe, then re-evaluate.
- `precondition-failed`: do not execute the requested action; restore its entry conditions.
- `repair-required`: a postcondition failed or the action raised an exception. Use the bounded repair policy or escalate to task-level diagnosis.

The repair callback receives the full recorded attempt and returns the next action callable. Every retry reacquires evidence. The library does not automatically generate robot programs or execute arbitrary code from a predicate definition.

## Validate the whole task

After local repair, use the host's full-task execution and terminal specification. Pass terminal predicate IDs, recorded milestone assertions and the declared required milestone list to `coordinator.finish`. A completion event does not itself promote a skill: admission still requires validation cases and an explicit review with artifact references.

Keep the original trial outputs and add the predicate trace alongside them. Snapshot IDs and event hashes permit comparison against the exact reviewed criteria used during execution. No existing simulator success function, held-out partition or physical controller is overridden by this integration.
