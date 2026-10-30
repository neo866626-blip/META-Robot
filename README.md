<div align="center">

# META-Robot

### Self Cognition and Capability Scaling in Agentic Robots

**Couple what a robot can do with how it knows an action succeeded.**

[![Tests](https://github.com/neo866626-blip/META-Robot/actions/workflows/tests.yml/badge.svg)](https://github.com/neo866626-blip/META-Robot/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/Core-Python%203.10%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/Code-Apache%202.0-blue)](LICENSE)

[Overview](#overview) · [Real-Robot Demos](#real-robot-demos) · [Quick Start](#quick-start) · [Predicate Library](docs/predicate-library.md) · [中文](README.zh-CN.md)

</div>

<p align="center"><img src="assets/meta_robot/architecture.svg" width="100%" alt="META-Robot execution loop and coupled predicate and skill libraries"></p>

## Overview

META-Robot couples reusable robot skills with action-level evaluation criteria. A skill describes **how to act or repair**; its predicates describe **what must hold, and which evidence is required to establish it**. Execution records predicate states before and after each action, uses failed conditions to guide bounded local repair, and preserves validated criteria alongside the skill hierarchy.

The framework brings together three components:

- **Predicate-guided execution.** Evaluate preconditions, postconditions and invariants at explicit action boundaries. Keep contact, gripper closure and verified acquisition distinct. Missing or stale evidence remains unknown and requests observation.
- **Coupled predicate and skill libraries.** Share predicates across skills, inherit criteria through parent–child specialization, retrieve the most specific applicable skill with available feedback, and admit reviewed updates as immutable snapshots.
- **Proprioceptive evidence.** Register task-relevant vision, joint, force, torque or gripper feedback through explicit adapters. Resolve temporal conditions from sufficiently covered signal windows.

## Real-Robot Demos

Excerpts from the project demonstration video. Click a preview to watch its clip; the [complete video](assets/meta_robot/meta-robot-full.mp4) preserves the full sequence and audio.

<table>
<tr>
<td width="33%" align="center"><a href="assets/meta_robot/instruction-following.mp4"><img src="assets/meta_robot/instruction-following.gif" alt="Instruction following on a real robot" width="100%"></a><br><b>Instruction Following</b><br>Ground the instruction in physical actions.</td>
<td width="33%" align="center"><a href="assets/meta_robot/long-horizon.mp4"><img src="assets/meta_robot/long-horizon.gif" alt="Long-horizon real-robot manipulation" width="100%"></a><br><b>Long-Horizon Tasks</b><br>Compose interactions across multiple steps.</td>
<td width="33%" align="center"><a href="assets/meta_robot/ordered-stacking.mp4"><img src="assets/meta_robot/ordered-stacking.gif" alt="Stacking cups in a specified order" width="100%"></a><br><b>Ordered Stacking</b><br>Follow task-specific ordering constraints.</td>
</tr>
<tr>
<td align="center"><a href="assets/meta_robot/towel-folding.mp4"><img src="assets/meta_robot/towel-folding.gif" alt="Bimanual manipulation of a thin towel" width="100%"></a><br><b>Thin-Object Manipulation</b><br>Grasp and manipulate a towel.</td>
<td align="center"><a href="assets/meta_robot/torque-identification.mp4"><img src="assets/meta_robot/torque-identification.gif" alt="Bottle identification using torque feedback" width="100%"></a><br><b>Torque-Based Identification</b><br>Use load evidence beyond appearance.</td>
<td align="center"><a href="assets/meta_robot/precision-insertion.mp4"><img src="assets/meta_robot/precision-insertion.gif" alt="Precision plug insertion on a real robot" width="100%"></a><br><b>Precision Insertion</b><br>Align and complete contact-rich insertion.</td>
</tr>
</table>

The demonstrations are supplied experiment footage, rather than executions of the synthetic quick-start example. [Media provenance](assets/meta_robot/media-manifest.json) records the source hash and clip boundaries.

## Quick Start

The predicate-library core runs on Linux and macOS with Python 3.10 or newer, without a GPU, model API key or simulator installation.

```bash
git clone https://github.com/neo866626-blip/META-Robot.git
cd META-Robot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m examples.predicate_loop --output output/predicate-demo
```

The example uses explicitly labeled synthetic observations. It consolidates two skills and two shared predicates, distinguishes contact from verified acquisition, repairs an unsatisfied condition, and writes a hash-linked transition trace. It never connects to hardware.

```bash
meta-robot --library output/predicate-demo/library verify
meta-robot --library output/predicate-demo/library index skill.contact
meta-robot templates
```

For LIBERO-Pro, Robosuite and BEHAVIOR-1K, use the separate [simulation setup](aspire/sim/README.md). Those stacks have their own Python, Linux, GPU, submodule and model requirements. Real-robot deployment starts with the [hardware guide](aspire/real/README.md) and [operator controls](aspire/real/AGENTS.md).

## Action-Level Predicate Library

```python
from meta_robot import PredicateDefinition, EvidenceRequirement

contact = PredicateDefinition(
    id="predicate.contact",
    semantic_key="physical-contact",
    description="Contact is supported by force feedback",
    expression={"fact": "signals.contact", "op": "eq", "value": True},
    requirements=(EvidenceRequirement("signals.contact", "force", max_age_s=0.5),),
)
```

A definition specifies its semantics, data-only condition and evidence contract. It enters the canonical library only with positive and negative validation cases and a review referencing existing evidence artifacts. Multiple skills can reuse the same predicate identity.

| Capability | Interface |
| --- | --- |
| Reviewed, atomic skill–predicate consolidation | `PredicateLibrary.consolidate` |
| Shared identities and inherited associations Γ(v) | `PredicateLibrary.associations` |
| Category-level predicate indexing | `PredicateLibrary.category_index` |
| Feedback-aware, deepest applicable skill retrieval | `PredicateLibrary.retrieve` |
| Pre/post states, finite local repair and provenance | `PredicateCoordinator.invoke` |
| Terminal conditions and declared milestones | `PredicateCoordinator.finish` |
| Registered feedback sources and temporal conditions | `EvidenceCollector`, `sustained_threshold` |

Read the [library guide](docs/predicate-library.md), [runtime integration](docs/runtime-integration.md) and [paper-to-code mapping](docs/paper-to-code.md).

## Repository Layout

```text
meta_robot/              META-Robot public API and command-line tools
  action_predicates/     Shared predicate library, skill coupling, evidence and execution
examples/                Runnable, hardware-free workflow
tests/                   Predicate-library regression tests
docs/                    Architecture, interfaces and integration guides
assets/meta_robot/       Project diagrams, real-robot clips and previews
aspire/sim/              Inherited execution, perception, simulation and knowledge infrastructure
aspire/real/             Inherited real-robot runtime and deployment guides
```

## Validation

```bash
python -m unittest discover -s tests -v
python -m unittest -q \
  aspire.sim.tests.test_knowledge \
  aspire.sim.tests.test_knowledge_cli \
  aspire.sim.tests.test_preregistration \
  aspire.sim.tests.test_knowledge_runtime \
  aspire.sim.tests.test_record_skill_promotion
```

The core tests exercise admission, semantic reuse, inheritance, retrieval, evidence freshness, bounded repair and completion gates. Full simulation benchmarks and robot experiments require their respective environments and experiment artifacts; unit-test results are not task-success measurements.

## Acknowledgments and License

META-Robot builds on [ASPIRE](https://github.com/NVlabs/ASPIRE) and the [AlanDerp development branch](https://github.com/AlanDerp/ASPIRE). The inherited execution infrastructure remains under the `aspire` namespace for compatibility; the public META-Robot API is `meta_robot`. Original copyright, attribution and third-party notices are preserved in [NOTICE](NOTICE) and [LICENSES](LICENSES/README.md). New code is licensed under Apache 2.0. The [original project documentation](README.upstream.md) remains available for provenance.
